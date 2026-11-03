"""Rutas del overlay de OBS y de su editor (/overlay*, /api/overlay/*).

Todas llevan ``needs_overlay=True`` (404 ``{}`` sin OverlayManager). Las que
OBS necesita a través de la VPN llevan ``remote=True``; el servidor remoto
(``server.RemoteOverlayShare``) rechaza cualquier otra con 404.

Cómo añadir una ruta
--------------------
1. Escribe ``def mi_ruta(req, match)``: ``req.ctx.overlay`` es el
   OverlayManager, ``match`` el resultado de ``re.fullmatch`` (grupos de la URL)
   y ``req.reply(código, datos, tipo_mime)`` responde. Para POST usa
   ``req.read_json(límite_en_bytes, msg_grande, msg_invalido)``.
2. Regístrala en ``ROUTES_GET`` o ``ROUTES_POST`` con ``route()`` (regex) o
   ``exact()`` (literal). Las POST ya exigen token, mismo origen y
   ``profiles.request_lock``; las GET ya exigen Host/Origin locales.
3. Añade una prueba HTTP en tests/ (ver tests/test_overlay.py).

Rutas de conjuntos, iconos propios y cementerio:
  * GET  /api/overlay/sprite-sets: conjuntos (subcarpetas) disponibles; solo local.
  * GET  /overlay/graveyard/<id de 12 hex>: sprite de un Pokémon caído por su
    id público (HMAC por proceso). Por la VPN solo sirve sprites ya guardados.
  * POST /api/overlay/item-sprite: importa un icono de objeto propio.
"""
from __future__ import annotations

import re

from tracker.custom_sprites import MEDIA_TYPES
from tracker.overlay import DEFAULT
from tracker.profiles import GEN6_GAMES

from .routing import exact, route
from .static import file_routes

IMAGE_LIMIT = 10850000   # sprite, barra de PS e icono del contador
FONT_LIMIT = 4300000
SETTINGS_LIMIT = 8192
SHARE_LIMIT = 256

FONT_TYPES = {'ttf': 'font/ttf', 'otf': 'font/otf', 'woff': 'font/woff', 'woff2': 'font/woff2'}

OVERLAY_FILES = {
    '/overlay': ('web/overlay.html', 'text/html; charset=utf-8'),
    '/overlay/editor': ('web/overlay-editor.html', 'text/html; charset=utf-8'),
    '/overlay.js': ('web/overlay.js', 'text/javascript; charset=utf-8'),
    '/overlay.css': ('web/overlay.css', 'text/css; charset=utf-8'),
    '/overlay-editor.js': ('web/overlay-editor.js', 'text/javascript; charset=utf-8'),
    '/overlay-editor.css': ('web/overlay-editor.css', 'text/css; charset=utf-8'),
}
REMOTE_OVERLAY_FILES = {'/overlay', '/overlay.js', '/overlay.css'}


def _png_or_404(req, raw, kind='image/png'):
    if raw is None:
        req.reply(404, {})
    else:
        req.reply(200, raw, kind)


# --- GET ---------------------------------------------------------------------

def share_status(req, _match):
    if req.ctx.share is None or req.ctx.remote_only:
        req.reply(404, {})
        return
    req.reply(200, req.ctx.share.status())


def public_state(req, _match):
    req.reply(200, req.ctx.overlay.public_state())


def settings(req, _match):
    overlay = req.ctx.overlay
    config = overlay.get_settings()
    config['hp_asset_versions'] = overlay.hp_asset_versions()
    config['counter_icon_version'] = overlay.counter_icon_version()
    req.reply(200, config)


def defaults(req, _match):
    req.reply(200, DEFAULT)


def fonts(req, _match):
    req.reply(200, req.ctx.overlay.available_fonts())


def font_file(req, match):
    name = match[1]
    raw = req.ctx.overlay.font_bytes(name)
    if raw is None:
        req.reply(404, {})
        return
    req.reply(200, raw, FONT_TYPES.get(name.rsplit('.', 1)[-1], 'application/octet-stream'))


def counter_icon(req, _match):
    _png_or_404(req, req.ctx.overlay.counter_icon_bytes())


def hp_image(req, match):
    valid = re.fullmatch(r'(fill|frame)\.png', match[1])
    _png_or_404(req, req.ctx.overlay.hp_image_bytes(valid[1]) if valid else None)


def item_icon(req, match):
    valid = re.fullmatch(r'([1-9][0-9]{0,3})\.png', match[1])
    icon = None
    if valid and req.ctx.item_icons is not None:
        game = req.ctx.fields('game').get('game')
        icon = req.ctx.item_icons.icon(int(valid[1]), 6 if game in GEN6_GAMES else 7)
    if icon is None:
        req.reply(404, {})
    else:
        req.reply(200, icon[0], icon[1])  # custom icons may be GIF/WebP


def sprite_sets(req, _match):
    req.reply(200, req.ctx.overlay.sprite_sets())


def graveyard_image(req, match):
    """Sprite of a fallen Pokémon by its stable public id (image_rev)."""
    layout = req.ctx.layout
    mon = req.ctx.overlay.graveyard_entry_for(match[1]) if layout is not None else None
    media = layout.sprite_for(mon, download=not req.ctx.remote_only) if mon is not None else None
    if media is None:
        req.reply(404, {})  # unknown, or still downloading: the overlay retries
        return
    raw, kind = media
    req.reply(200, raw, MEDIA_TYPES.get(kind, 'image/png'))


def pokemon_media(req, match):
    valid = re.fullmatch(r'([1-6])\.(gif|png|webp)', match[1])
    if not valid:
        req.reply(404, {})
        return
    _png_or_404(req, req.ctx.overlay.image_bytes(int(valid[1]), valid[2]), 'image/' + valid[2])


# --- POST --------------------------------------------------------------------

def configure_share(req, _match):
    if req.ctx.share is None:
        req.reply(404, {})
        return
    try:
        data = req.read_json(SHARE_LIMIT, 'Solicitud demasiado grande', 'Solicitud incorrecta')
        req.reply(200, req.ctx.share.configure(data.get('enabled'), data.get('ip', '')))
    except (ValueError, TypeError, OSError) as exc:
        req.reply(400, {'error': str(exc)})


def overlay_import(limit, action):
    """POST JSON de overlay: ``action(overlay, obj)`` devuelve la respuesta."""
    def handler(req, _match):
        try:
            obj = req.read_json(limit, 'Solicitud de overlay demasiado grande', 'JSON inválido')
            req.reply(200, action(req.ctx.overlay, obj))
        except (ValueError, TypeError, UnicodeError) as exc:
            req.reply(400, {'error': str(exc)})
    return handler


# Patrones amplios a propósito (p. ej. /overlay/item/(.*)): la validación fina
# ocurre en la función y así una URL mal formada sigue respondiendo 404 {} y
# no «Solo lectura OBS» en la VPN, igual que antes de la tabla de rutas.
ROUTES_GET = [
    exact('/api/overlay/share', share_status, needs_overlay=True),
    exact('/api/overlay/public', public_state, remote=True, needs_overlay=True),
    exact('/api/overlay/settings', settings, remote=True, needs_overlay=True),
    exact('/api/overlay/defaults', defaults, needs_overlay=True),
    exact('/api/overlay/fonts', fonts, needs_overlay=True),
    route(r'/overlay/font/(.*)', font_file, remote=True, needs_overlay=True),
    exact('/overlay/counter-icon.png', counter_icon, remote=True, needs_overlay=True),
    route(r'/overlay/hp-image/(.*)', hp_image, remote=True, needs_overlay=True),
    route(r'/overlay/item/(.*)', item_icon, remote=True, needs_overlay=True),
    route(r'/overlay/media/pokemon_(.*)', pokemon_media, remote=True, needs_overlay=True),
    exact('/api/overlay/sprite-sets', sprite_sets, needs_overlay=True),
    route(r'/overlay/graveyard/([0-9a-f]{12})', graveyard_image, remote=True, needs_overlay=True),
    # Nuevas rutas GET de overlay aquí (ver docstring del módulo).
    *file_routes(OVERLAY_FILES, remote=REMOTE_OVERLAY_FILES, needs_overlay=True),
]

ROUTES_POST = [
    exact('/api/overlay/share', configure_share),
    exact('/api/overlay/settings', overlay_import(
        SETTINGS_LIMIT, lambda overlay, obj: overlay.set_settings(obj)), needs_overlay=True),
    exact('/api/overlay/font', overlay_import(
        FONT_LIMIT, lambda overlay, obj: overlay.import_font(obj.get('name'), obj.get('data'))),
        needs_overlay=True),
    exact('/api/overlay/hp-image', overlay_import(
        IMAGE_LIMIT, lambda overlay, obj: overlay.import_hp_image(obj.get('kind'), obj.get('data'))),
        needs_overlay=True),
    exact('/api/overlay/sprite', overlay_import(
        IMAGE_LIMIT, lambda overlay, obj: overlay.import_sprite(
            obj.get('name'), obj.get('data'), obj.get('sprite_set') or '')),
        needs_overlay=True),
    exact('/api/overlay/item-sprite', overlay_import(
        IMAGE_LIMIT, lambda overlay, obj: overlay.import_item_sprite(
            obj.get('name'), obj.get('data'), obj.get('sprite_set') or '')),
        needs_overlay=True),
    exact('/api/overlay/counter-icon', overlay_import(
        IMAGE_LIMIT, lambda overlay, obj: overlay.import_counter_icon(obj.get('data'))),
        needs_overlay=True),
    # Nuevas rutas POST de overlay aquí (ver docstring del módulo).
]
