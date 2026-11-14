"""Archivos estáticos de la interfaz, cabecera CSP y sprites de Pokémon.

Rutas GET:
  /, /app.js, /style.css, ... (STATIC_FILES; solo /fonts/Oxanium.ttf va a la VPN)
  /soullink/sprite/<id>.png  sprite resuelto en el servidor (cache + descarga)
  /sprites/<id>.png          sprites incluidos en data/sprites, sin descargas
"""
from __future__ import annotations

import re
import threading
import time
from pathlib import Path

from tracker.layout_export import fetch_sprite, validate_png

from .context import ROOT
from .routing import exact, route


def content_security_policy(host):
    """Defense in depth against injected markup: no inline scripts or on…=
    handlers, no third-party scripts. 'unsafe-eval' stays because the
    pywebview bridge builds its API functions with new Function()."""
    ws = f' ws://{host}' if re.fullmatch(r'[0-9a-zA-Z.:\[\]-]{1,80}', host or '') else ''
    return ("default-src 'self'; script-src 'self' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob: https://raw.githubusercontent.com; font-src 'self' data:; "
            f"connect-src 'self'{ws}; frame-src 'self'; object-src 'none'; base-uri 'none'; "
            "form-action 'self'; frame-ancestors 'self'")


def serve_file(req, name, kind):
    req.reply(200, (ROOT / name).read_bytes(), kind)


def file_routes(files, remote=(), **options):
    """Una ruta exacta por archivo de ``files`` ({url: (ruta relativa, MIME)})."""
    def handler_for(name, kind):
        return lambda req, _match: serve_file(req, name, kind)
    return [exact(url, handler_for(name, kind), remote=url in remote, **options)
            for url, (name, kind) in files.items()]


STATIC_FILES = {
    '/fonts/Oxanium.ttf': ('web/fonts/Oxanium.ttf', 'font/ttf'),
    '/': ('web/index.html', 'text/html; charset=utf-8'),
    '/app.js': ('web/app.js', 'text/javascript; charset=utf-8'),
    '/analysis.js': ('web/analysis.js', 'text/javascript; charset=utf-8'),
    '/soul.js': ('web/soul.js', 'text/javascript; charset=utf-8'),
    '/room.js': ('web/room.js', 'text/javascript; charset=utf-8'),
    '/companion.js': ('web/companion.js', 'text/javascript; charset=utf-8'),
    '/companion.css': ('web/companion.css', 'text/css; charset=utf-8'),
    '/theme.js': ('web/theme.js', 'text/javascript; charset=utf-8'),
    '/style.css': ('web/style.css', 'text/css; charset=utf-8'),
    '/empty-pokemon.svg': ('web/empty-pokemon.svg', 'image/svg+xml'),
    '/app-icon.png': ('web/app-icon.png', 'image/png'),
}
# Main UI split into classic scripts (web/app/), loaded in this order by index.html.
APP_SCRIPTS = ('helpers', 'profiles', 'team', 'detail', 'boxes', 'dead', 'routes', 'progress', 'stage-lists', 'caps-proposal',
               'analysis-view', 'connection', 'shell', 'companion-loader', 'update-notice')
STATIC_FILES.update({f'/app/{name}.js': (f'web/app/{name}.js', 'text/javascript; charset=utf-8')
                     for name in APP_SCRIPTS})


class SpriteStore:
    """Los avisos Soul Link pueden referirse a un Pokémon guardado en cajas.

    Resolver sprites en el servidor evita depender del acceso GitHub/WebView2
    de cada cliente y guarda lo descargado para uso sin conexión posterior.
    """
    RETRY_SECONDS = 45

    def __init__(self, cache_dir=None):
        self.cache_dir = Path(cache_dir) if cache_dir is not None else None
        self.retry = {}
        self.lock = threading.Lock()

    def png(self, ident):
        candidates = [ROOT / 'data' / 'sprites' / f'{ident}.png']
        if self.cache_dir is not None:
            candidates.insert(0, self.cache_dir / f'{ident}.png')
        for path in candidates:
            try:
                if path.is_file():
                    return validate_png(path.read_bytes())
            except (OSError, ValueError):
                continue
        with self.lock:
            if time.monotonic() < self.retry.get(ident, 0):
                return None
        try:
            raw = fetch_sprite(ident)
        except (OSError, ValueError):
            with self.lock:
                self.retry[ident] = time.monotonic() + self.RETRY_SECONDS
            return None
        if self.cache_dir is not None:
            try:
                self.cache_dir.mkdir(parents=True, exist_ok=True)
                path = self.cache_dir / f'{ident}.png'
                tmp = self.cache_dir / f'.{ident}.{threading.get_ident()}.tmp'
                try:
                    tmp.write_bytes(raw)
                    tmp.replace(path)
                finally:
                    tmp.unlink(missing_ok=True)
            except OSError:
                pass  # Mostrarlo aunque el cache no sea escribible.
        return raw


def soullink_sprite(req, match):
    # An <img> on any external website could otherwise make the tracker
    # download thousands of sprites. Browsers mark those cross-site.
    if req.headers.get('Sec-Fetch-Site', 'same-origin') not in ('same-origin', 'none'):
        req.reply(403, {'error': 'Origen inválido'})
        return
    if 1 <= int(match[1]) <= 10115:
        raw = req.ctx.sprites.png(int(match[1]))
        if raw is not None:
            req.reply(200, raw, 'image/png')
            return
    req.reply(404, {})


def bundled_sprite(req, match):
    # La galería general conserva su ruta habitual: no disparar
    # cientos de descargas al abrir todas las cajas del tracker.
    name = match[1]
    if name.removesuffix('.png').isdigit() and name.endswith('.png'):
        file = ROOT / 'data' / 'sprites' / name
        if file.is_file():
            req.reply(200, file.read_bytes(), 'image/png')
            return
    req.reply(404, {})


ROUTES_GET = [
    *file_routes(STATIC_FILES, remote={'/fonts/Oxanium.ttf'}),
    route(r'/soullink/sprite/([1-9][0-9]{0,4})\.png', soullink_sprite),
    route(r'/sprites/(.*)', bundled_sprite),
]
