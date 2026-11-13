"""Individual authenticated connections behind a reusable admission invitation."""
from __future__ import annotations

import hmac
import json
import socket
import time
from typing import cast
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, Request, build_opener

from .direct import (DirectHost, DirectRequestHandler, MAX_MESSAGE_BYTES, NoRedirect,
                     SECRET_RE, invitation, private_address)
from .room import MAX_ROOM_BYTES
from .soul_room import FEATURES, MAX_SOUL_BYTES, PROTOCOL, SoulRoom, soul_view
from .snapshot import JSONDict, safe_text

MAX_REQUEST_BYTES = MAX_MESSAGE_BYTES + MAX_SOUL_BYTES


def default_host() -> str:
    try:
        addresses = socket.gethostbyname_ex(socket.gethostname())[2]
    except OSError:
        addresses = []
    for address in addresses:
        try:
            if not address.startswith('127.'):
                return private_address(address)
        except ValueError:
            continue
    return '127.0.0.1'


def soul_invitation(value: object) -> tuple[str, str]:
    if not isinstance(value, str) or len(value) > 200:
        raise ValueError('Pega la invitación completa de Soul Link')
    parts = urlsplit(value.strip())
    if parts.path != '/soul':
        raise ValueError('Esta invitación usa una conexión anterior; abre las opciones avanzadas')
    return invitation(parts._replace(path='/join').geturl())


def soul_request(base: str, path: str, secret: str, data: JSONDict) -> JSONDict:
    raw = json.dumps(data, ensure_ascii=False, separators=(',', ':')).encode()
    if len(raw) > MAX_REQUEST_BYTES:
        raise ValueError('Los datos de Soul Link superan el tamaño permitido')
    request = Request(base + path, data=raw, method='POST', headers={
        'Content-Type': 'application/json', 'Authorization': 'Bearer ' + secret})
    try:
        with build_opener(ProxyHandler({}), NoRedirect()).open(request, timeout=3) as response:
            body = response.read(MAX_ROOM_BYTES + 1)
            if len(body) > MAX_ROOM_BYTES:
                raise ValueError('Respuesta de sala demasiado grande')
            result = json.loads(body)
            if not isinstance(result, dict):
                raise ValueError('Respuesta de sala inválida')
            return result
    except HTTPError as error:
        try:
            details = json.loads(error.read(1024)).get('error')
            message = details if safe_text(details, 200) else 'La sala rechazó la conexión'
        except (ValueError, AttributeError, RecursionError):
            message = 'La sala rechazó la conexión'
        finally:
            error.close()
        raise ValueError(message + f' (HTTP {error.code})') from None
    except (URLError, TimeoutError, OSError):
        raise ValueError('No se pudo contactar la sala; revisa la red local o VPN') from None
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        raise ValueError('Respuesta de sala inválida') from None


class SoulHandler(DirectRequestHandler):
    paths = ('/v3/join', '/v3/resume', '/v3/exchange', '/v3/leave')
    message_limit = MAX_REQUEST_BYTES
    secret = ''
    player_id = ''

    def _authorized(self, owner: DirectHost) -> bool:
        host = cast(SoulHost, owner)
        supplied = self.headers.get('Authorization', '')
        if not supplied.startswith('Bearer ') or SECRET_RE.fullmatch(supplied[7:]) is None:
            return False
        self.secret = supplied[7:]
        if self.path == '/v3/join':
            return bool(host.room.common_invite and hmac.compare_digest(self.secret, host.room.common_invite))
        try:
            self.player_id = host.room.authenticate(self.secret)
            return True
        except ValueError:
            return False

    def _dispatch(self, owner: DirectHost, data: JSONDict) -> None:
        host = cast(SoulHost, owner)
        host.rates = {k: v for k, v in host.rates.items() if k == 'invite' or k in host.room.members}
        key = 'invite' if self.path == '/v3/join' else self.player_id
        now = time.monotonic()
        start, count = host.rates.get(key, (now, 0))
        if now - start >= 1:
            start, count = now, 0
        host.rates[key] = (start, count + 1)
        if count >= 8:
            self.reply(429, {'error': 'Espera un momento antes de volver a intentar'})
            return
        try:
            if self.path == '/v3/join':
                result = host.room.join(self.secret, data)
            elif self.path == '/v3/resume':
                result = host.room.resume(self.secret, data)
            else:
                view = host.room.exchange(self.player_id, data)
                if self.path == '/v3/leave':
                    host.room.leave(self.player_id)
                    view = host.room.view()
                result = {'room': view}
            self.reply(200, result)
        except ValueError as error:
            message = str(error)
            self.reply(409, {'error': message if safe_text(message, 200) else 'La sala rechazó los datos'})


class SoulHost(DirectHost):
    handler_type = SoulHandler

    def __init__(self, host: object, port: object, person: JSONDict) -> None:
        self.room = SoulRoom(person)
        self.rates: dict[str, tuple[float, int]] = {}
        super().__init__(host, port, person['name'], person['game'])
        self.invite_secret = self.session_secret = None

    def link(self) -> str:
        with self.lock:
            return f'nuzlocke://{self.address}/soul#{self.room.common_invite}' if self.room.common_invite else ''

    def room_status(self) -> JSONDict:
        with self.lock:
            return self.room.view()

    def local_exchange(self, data: JSONDict) -> JSONDict:
        with self.lock:
            return self.room.exchange(self.room.host_id, data)

    def close(self) -> None:
        super().close()
        with self.lock:
            self.room.tokens.clear()
            self.room.revoke_invites()
            for member in self.room.members.values():
                member['state'] = None


class SoulPeer:
    def __init__(self, invite: object, person: JSONDict, saved: JSONDict | None = None) -> None:
        self.base, secret = soul_invitation(invite)
        data = {'protocol': PROTOCOL, 'features': list(FEATURES), **person}
        if saved and saved.get('base') == self.base and all(saved.get(k) == person[k] for k in ('player_id', 'run_id', 'game')):
            data.update(session_id=saved['session_id'], epoch=saved['epoch'])
            response = soul_request(self.base, '/v3/resume', saved['token'], data)
        else:
            response = soul_request(self.base, '/v3/join', secret, data)
        token = response.get('token')
        if not isinstance(token, str) or SECRET_RE.fullmatch(token) is None:
            raise ValueError('Credencial individual inválida')
        view = soul_view(response.get('room'))
        if saved and data.get('session_id') and (view['session_id'] != saved['session_id'] or view['epoch'] != saved['epoch']):
            raise ValueError('La sala guardada cambió; sal de la conexión anterior')
        if not any(all(m[k] == person[k] for k in ('player_id', 'run_id', 'game')) for m in view['members']):
            raise ValueError('Tu participación no aparece en la sala')
        self.token, self.view = token, view

    def exchange(self, data: JSONDict, *, leave: bool = False) -> JSONDict:
        response = soul_request(self.base, '/v3/leave' if leave else '/v3/exchange', self.token, data)
        view = soul_view(response.get('room'))
        if view['session_id'] != self.view['session_id'] or view['epoch'] != self.view['epoch'] or view['revision'] < self.view['revision']:
            raise ValueError('La respuesta pertenece a otra sala o es antigua')
        self.view = view
        return view
