"""POST /api/command: valida cada orden y la encola para el hilo de memoria.

La validación ocurre aquí, antes de encolar, para que una orden inválida
responda 400 al momento en lugar de fallar en silencio en el worker.
"""
from __future__ import annotations

import json

from tracker.progress import LEVEL_CAP_ACTIONS

from .routing import exact

COMMAND_LIMIT = 4096
# Only a full level-caps list (up to 64 stages) may be larger than COMMAND_LIMIT.
LEVEL_CAPS_LIMIT = 32768
ACTIONS = ('connect', 'disconnect', 'box', 'scan', 'cancel', 'demo', 'route_miss', 'revive',
           'mark_dead', 'set_origin', 'mark_route', 'clear_route_mark', 'route_trade',
           'save_session', *LEVEL_CAP_ACTIONS)
DEMO_SCENARIOS = ('normal', 'damage', 'empty', 'stale', 'long')


def validate_command(service, cmd):
    """Lanza ValueError/AttributeError/TypeError si ``cmd`` no es válido."""
    action = cmd.get('action')
    if action not in ACTIONS:
        raise ValueError('Acción inválida')
    if action == 'revive':
        service.validate_revive(cmd)
    if action == 'mark_dead':
        service.validate_mark_dead(cmd)
    if action == 'route_miss':
        service.validate_route_miss(cmd)
    if action == 'route_trade':
        service.validate_route_trade(cmd)
    if action == 'set_origin':
        service.validate_set_origin(cmd)
    if action == 'mark_route':
        service.validate_route_mark(cmd)
    if action in LEVEL_CAP_ACTIONS:
        service.validate_level_caps(cmd)
    if action == 'clear_route_mark':
        service.validate_route_mark(cmd, undo=True)
    if action == 'demo' and (not service.snapshot().get('demo') or cmd.get('scenario') not in DEMO_SCENARIOS):
        raise ValueError('Escenario de demostración inválido')
    if action == 'connect':
        from tracker.profiles import PROFILES
        if cmd.get('game', 'Ultra Moon 1.0') not in PROFILES:
            raise ValueError('Juego no compatible')
        if cmd.get('mode') not in ('memory', 'gdb'):
            raise ValueError('Conector inválido')
        if cmd.get('pid') is not None and (type(cmd['pid']) is not int or cmd['pid'] <= 0):
            raise ValueError('PID inválido')
        if type(cmd.get('port', 24689)) is not int or not 1 <= cmd.get('port', 24689) <= 65535:
            raise ValueError('Puerto inválido')
    if action == 'box' and (type(cmd.get('number')) is not int or
                            not 1 <= cmd['number'] <= (31 if service.profile.generation == 6 else 32)):
        raise ValueError('Caja inválida para este juego')
    return action


def command(req, _match):
    service = req.ctx.service
    try:
        # Sin comprobación de «objeto JSON»: un JSON que no es objeto falla
        # en cmd.get() con AttributeError -> 400, como siempre.
        body = req.read_body(LEVEL_CAPS_LIMIT, 'Tamaño inválido')
        cmd = json.loads(body)
        if len(body) > COMMAND_LIMIT and cmd.get('action') != 'level_caps_set':
            raise ValueError('Tamaño inválido')
        action = validate_command(service, cmd)
        if 'soullink_room' in cmd:
            if action != 'mark_dead' or cmd.get('source') != 'soullink-response' or req.ctx.companion is None:
                raise ValueError('Confirmación de sala inválida')
            req.ctx.companion.multiplayer.validate_confirmation(cmd['soullink_room'], cmd.get('key'))
        if action in ('connect', 'disconnect'):
            cmd['_connection_generation'] = service.request_connection_change()
        service.commands.put(cmd)
        req.reply(202, {'ok': True})
    except (ValueError, AttributeError, TypeError) as exc:
        req.reply(400, {'error': str(exc)})


ROUTES_POST = [exact('/api/command', command)]
