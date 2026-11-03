"""Estado de la partida, referencia, diagnóstico, procesos y WebSocket.

GET:  /api/session, /api/processes, /api/state, /api/templates, /api/analysis,
      /api/routes[?game=], /api/move/<id>, /api/diagnostic, /ws
POST: /api/diagnostic/save, /api/templates
"""
from __future__ import annotations

import base64
import hashlib
import json
import struct
from urllib.parse import parse_qs, urlsplit

from tracker import __version__
from tracker.process_memory import list_emulator_instances

from .routing import exact, route

WS_GUID = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'
TEMPLATES_LIMIT = 500000


def frame(payload, opcode=1):
    raw = payload.encode() if isinstance(payload, str) else payload
    size = len(raw)
    if size < 126:
        length = bytes([size])
    elif size < 65536:
        length = b'\x7e' + struct.pack('!H', size)
    else:
        length = b'\x7f' + struct.pack('!Q', size)
    return bytes([128 | opcode]) + length + raw


# --- GET ---------------------------------------------------------------------

def session(req, _match):
    ctx = req.ctx
    service = ctx.service
    req.reply(200, {'token': ctx.token, 'version': __version__, 'profile': ctx.profile,
                    'saved_connection': service.config if service.snapshot().get('session_saved') else None})


def processes(req, _match):
    try:
        found = [{'pid': p['pid'], 'name': p.get('name', ''),
                  'title': p.get('title', ''), 'game': p.get('game_hint'),
                  'creation_time': p.get('creation_id')}
                 for p in list_emulator_instances()]
        req.reply(200, {'processes': found})
    except (OSError, RuntimeError, ValueError) as exc:
        req.reply(200, {'processes': [], 'error': str(exc)})


def state(req, _match):
    req.reply(200, req.ctx.service.snapshot())


def templates_status(req, _match):
    req.reply(200, req.ctx.service.templates.status())


def analysis(req, _match):
    req.reply(200, {k: v for k, v in req.ctx.service.reference.analysis.items() if k != 'pokemon'})


def routes(req, _match):
    # ?game= lets the Companion view load the PARTNER's catalog.
    requested = parse_qs(urlsplit(req.path).query).get('game', [None])[0]
    game = requested if isinstance(requested, str) and 0 < len(requested) <= 40 else req.ctx.fields('game')['game']
    req.reply(200, req.ctx.service.reference.routes(game))


def move(req, match):
    service = req.ctx.service
    try:
        suffix = match[1]
        if not suffix.isdigit():
            raise ValueError('ID inválido')
        req.reply(200, service.reference.move(int(suffix), service.catalog))
    except ValueError as exc:
        req.reply(404, {'error': str(exc)})


def diagnostic(req, _match):
    ctx = req.ctx
    current = ctx.fields('connection', 'game')
    layout_error = getattr(getattr(ctx.profiles, 'layout', None), 'last_error', None)
    req.reply(200, {'connection': current['connection'], 'game': current['game'],
                    'details': ctx.service.diagnostic or {}, 'layout_error': layout_error})


def websocket(req, _match):
    if req.headers.get('Upgrade', '').lower() != 'websocket' or req.headers.get('Sec-WebSocket-Version') != '13':
        req.reply(400, {})
        return
    key = req.headers.get('Sec-WebSocket-Key', '')
    try:
        if len(base64.b64decode(key, validate=True)) != 16:
            raise ValueError()
    except ValueError:
        req.reply(400, {})
        return
    accept = base64.b64encode(hashlib.sha1((key + WS_GUID).encode()).digest()).decode()
    req.send_response(101)
    req.send_header('Upgrade', 'websocket')
    req.send_header('Connection', 'Upgrade')
    req.send_header('Sec-WebSocket-Accept', accept)
    req.end_headers()
    service = req.ctx.service
    req.connection.settimeout(3)
    revision = -1
    try:
        while not service.stop.is_set():
            current = service.snapshot()
            if current['revision'] != revision:
                req.connection.sendall(frame(json.dumps(current, ensure_ascii=False)))
                revision = current['revision']
            with service.condition:
                service.condition.wait_for(
                    lambda: service.state['revision'] != revision or service.stop.is_set(), timeout=10)
            if req.ctx.current_revision() == revision:
                req.connection.sendall(frame(b'', 9))  # ping
    except OSError:
        pass
    req.close_connection = True


# --- POST --------------------------------------------------------------------

def save_diagnostic(req, _match):
    try:
        req.reply(200, {'ok': True, 'path': req.ctx.service.save_diagnostic()})
    except OSError as exc:
        req.reply(500, {'error': 'No se pudo guardar el archivo: ' + str(exc)})


def import_templates(req, _match):
    try:
        data = req.read_json(TEMPLATES_LIMIT, 'Plantilla demasiado grande', 'Plantillas inválidas')
        req.reply(200, req.ctx.service.import_templates(data.get('files')))
    except (ValueError, TypeError, UnicodeError, KeyError) as error:
        req.reply(400, {'error': str(error)})


ROUTES_GET = [
    exact('/api/session', session),
    exact('/api/processes', processes),
    exact('/api/state', state),
    exact('/api/templates', templates_status),
    exact('/api/analysis', analysis),
    exact('/api/routes', routes),
    route(r'/api/move/(.*)', move),
    exact('/api/diagnostic', diagnostic),
    exact('/ws', websocket),
]

ROUTES_POST = [
    exact('/api/diagnostic/save', save_diagnostic),
    exact('/api/templates', import_templates),
]
