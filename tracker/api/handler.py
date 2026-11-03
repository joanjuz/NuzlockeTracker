"""Manejador HTTP: comprobaciones comunes + despacho por tabla de rutas.

Orden de comprobaciones (no cambiarlo sin pruebas):
GET   1. Host/Origin locales (allowed) o 403.
      2. Servidor VPN (remote_only): solo rutas con remote=True, o 404.
      3. needs_overlay sin OverlayManager -> 404 {}.
POST  1. profiles.request_lock (serializa con el cambio de partida).
      2. Servicio detenido -> 409.
      3. remote_only -> 403; Host/Origin + X-Tracker-Token o 403.
      4. Despacho por self.path SIN quitar la query (como siempre).
"""
from __future__ import annotations

import json
from contextlib import nullcontext
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlsplit

from tracker.item_sprites import ItemSprites

from . import commands, companion, overlay, profiles, state, static, update
from .context import ApiContext
from .routing import find
from .static import SpriteStore, content_security_policy

# Orden = prioridad. Los patrones no se solapan, pero la primera coincidencia gana.
ROUTES_GET = [
    *overlay.ROUTES_GET,
    *state.ROUTES_GET,
    *companion.ROUTES_GET,
    *profiles.ROUTES_GET,
    *update.ROUTES_GET,
    *static.ROUTES_GET,
]
ROUTES_POST = [
    *profiles.ROUTES_POST,
    *overlay.ROUTES_POST,
    *companion.ROUTES_POST,
    *state.ROUTES_POST,
    *commands.ROUTES_POST,
]


class TrackerRequestHandler(BaseHTTPRequestHandler):
    """Base común; make_handler() crea una subclase con su ``ctx``."""
    ctx: ApiContext
    routes_get = ROUTES_GET
    routes_post = ROUTES_POST
    # Idle or half-open sockets (also from the VPN share) must not keep a
    # handler thread alive forever. The WebSocket sets its own timeout.
    timeout = 10

    def log_message(self, *args):
        pass

    def allowed(self):
        host = f'{self.server.server_address[0]}:{self.server.server_port}'
        return self.headers.get('Host') == host and self.headers.get('Origin', f'http://{host}') == f'http://{host}'

    def reply(self, code, data, kind='application/json'):
        raw = json.dumps(data, ensure_ascii=False).encode() if kind == 'application/json' else data
        self.send_response(code)
        self.send_header('Content-Type', kind)
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Cache-Control', 'no-store')
        if kind.startswith('text/html'):
            self.send_header('Content-Security-Policy', content_security_policy(self.headers.get('Host', '')))
            self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(raw)

    def read_body(self, limit, message):
        """Cuerpo con 0 < Content-Length <= limit; si no, ValueError(message)."""
        size = int(self.headers.get('Content-Length', '0'))
        if not 0 < size <= limit:
            raise ValueError(message)
        return self.rfile.read(size)

    def read_json(self, limit, too_large, not_object):
        """Objeto JSON del cuerpo; cualquier fallo es ValueError."""
        obj = json.loads(self.read_body(limit, too_large))
        if not isinstance(obj, dict):
            raise ValueError(not_object)
        return obj

    def do_GET(self):
        if not self.allowed():
            self.reply(403, {'error': 'Origen inválido'})
            return
        found, match = find(self.routes_get, urlsplit(self.path).path)
        if self.ctx.remote_only and (found is None or not found.remote):
            self.reply(404, {'error': 'Solo lectura OBS'})
            return
        if found is None or (found.needs_overlay and self.ctx.overlay is None):
            self.reply(404, {})
            return
        found.handler(self, match)

    def do_POST(self):
        backend = self.ctx.profiles
        # Serialize profile switching with all writes. A request accepted
        # on an old keep-alive connection cannot mutate the previous run.
        with backend.request_lock if backend is not None else nullcontext():
            service = self.ctx.service
            if getattr(service, 'stop', None) is not None and service.stop.is_set():
                self.reply(409, {'error': 'La partida cambió. Actualiza la ventana.'})
                return
            self.post_current_profile()

    def post_current_profile(self):
        if self.ctx.remote_only:
            self.reply(403, {'error': 'Solo lectura OBS'})
            return
        if not self.allowed() or self.headers.get('X-Tracker-Token') != self.ctx.token:
            self.reply(403, {})
            return
        found, match = find(self.routes_post, self.path)
        if found is None or (found.needs_overlay and self.ctx.overlay is None):
            self.reply(404, {})
            return
        found.handler(self, match)


def make_handler(service, token, companion=None, profile='principal', overlay=None,
                 share=None, remote_only=False, sprite_cache=None, profiles=None,
                 updates=None, layout=None):
    sprite_dir = Path(sprite_cache) if sprite_cache is not None else None
    item_icons = None
    if sprite_dir is not None:
        catalog = getattr(service, 'catalog', None)
        item_icons = ItemSprites(
            sprite_dir, allow_download=not remote_only,
            # User icons (sprites_personalizados/[conjunto/]objetos) win over PokeAPI.
            custom_root=getattr(overlay, 'custom_dir', None),
            sprite_set=getattr(overlay, 'selected_sprite_set', None),
            name_lookup=(lambda item_id: catalog.name('items', item_id)) if catalog is not None else None)
    ctx = ApiContext(
        service=service, token=token, companion=companion, profile=profile,
        overlay=overlay, share=share, remote_only=remote_only, profiles=profiles,
        updates=updates, sprites=SpriteStore(sprite_dir), item_icons=item_icons, layout=layout)

    class Handler(TrackerRequestHandler):
        pass

    Handler.ctx = ctx
    return Handler
