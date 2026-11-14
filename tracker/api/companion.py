"""Soul Link: estado y acciones del Companion (GET/POST /api/companion)."""
from __future__ import annotations

from .routing import exact

COMPANION_LIMIT = 4096
ACTIONS = ('create', 'join', 'refresh', 'leave', 'direct_host', 'direct_join',
           'room_host', 'room_join', 'room_invite', 'room_revoke', 'room_remove', 'room_new_run', 'room_link', 'soul_host', 'soul_join', 'soul_share', 'soul_invite',
           'soul_revoke', 'soul_remove', 'soul_link', 'soul_new_run')


def status(req, _match):
    if req.ctx.companion is None:
        req.reply(404, {'error': 'Sin sincronización'})
        return
    req.reply(200, req.ctx.companion.status())


def perform(req, _match):
    companion = req.ctx.companion
    if companion is None:
        req.reply(404, {'error': 'Sin sincronización'})
        return
    try:
        cmd = req.read_json(COMPANION_LIMIT, 'Solicitud demasiado grande', 'JSON incorrecto')
        action = cmd.get('action')
        if action not in ACTIONS:
            raise ValueError('Acción inválida')
        req.reply(200, companion.perform(action, cmd))
    except (ValueError, TypeError) as exc:
        req.reply(400, {'error': str(exc)})


ROUTES_GET = [exact('/api/companion', status)]
ROUTES_POST = [exact('/api/companion', perform)]
