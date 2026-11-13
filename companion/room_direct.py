"""Opt-in room protocol on the existing isolated LAN/VPN HTTP listener."""
from __future__ import annotations

import hmac
import time
from typing import cast
from urllib.parse import urlsplit

from .direct import DirectHost, DirectRequestHandler, SECRET_RE, invitation, request_json
from .room import MAX_ROOM_BYTES, Room, room_view
from .snapshot import JSONDict


def room_invitation(value: object) -> tuple[str, str]:
    if not isinstance(value, str) or len(value) > 200:
        raise ValueError('Invitación de sala inválida')
    parts = urlsplit(value.strip())
    if parts.path != '/room':
        raise ValueError('Usa una invitación de sala v2')
    return invitation(parts._replace(path='/join').geturl())


def room_request(base: str, path: str, secret: str, data: JSONDict) -> JSONDict:
    return request_json(base, path, secret, data, response_limit=MAX_ROOM_BYTES)


class RoomRequestHandler(DirectRequestHandler):
    paths = ('/v2/join', '/v2/exchange', '/v2/leave')
    player_id = ''
    secret = ''

    def _authorized(self, owner: DirectHost) -> bool:
        host = cast(RoomHost, owner)
        supplied = self.headers.get('Authorization', '')
        if not supplied.startswith('Bearer '):
            return False
        secret = supplied[7:]
        if SECRET_RE.fullmatch(secret) is None:
            return False
        self.secret = secret
        if self.path == '/v2/join':
            return any(hmac.compare_digest(token, secret) for token in host.room.invites)
        try:
            self.player_id = host.room.authenticate(secret)
        except ValueError:
            return False
        return True

    def _dispatch(self, owner: DirectHost, data: JSONDict) -> None:
        host = cast(RoomHost, owner)
        # Only authenticated identities get rate-limit buckets (at most five).
        host.rates = {k: v for k, v in host.rates.items() if k == 'invite' or k in host.room.members}
        key = self.player_id if self.path != '/v2/join' else 'invite'
        now = time.monotonic()
        start, count = host.rates.get(key, (now, 0))
        if now - start >= 1:
            start, count = now, 0
        host.rates[key] = (start, count + 1)
        if count >= 8:
            self.reply(429, {'error': 'Demasiadas solicitudes; vuelve a intentar'})
            return
        if self.path == '/v2/join':
            if data.get('features') != ['capture-links-v1']:
                self.reply(409, {'error': 'Versiones de sala incompatibles; actualiza ambos Trackers'})
                return
            self.reply(200, host.room.join(self.secret, data))
        else:
            # Check envelope even on leave: a stale incarnation cannot revoke
            # a membership after the host or the guest has changed run.
            view = host.room.exchange(self.player_id, data)
            if self.path == '/v2/leave':
                host.room.leave(self.player_id)
                view = host.room.view()
            self.reply(200, {'room': view})


class RoomHost(DirectHost):
    handler_type = RoomRequestHandler

    def __init__(self, address: object, port: object, person: JSONDict, capacity: int) -> None:
        self.room = Room(person, capacity)
        self.rates: dict[str, tuple[float, int]] = {}
        super().__init__(address, port, person['name'], person['game'])
        # v1 secrets are not used by the v2 handler.
        self.invite_secret = self.session_secret = None
        self.link = ''
        self.new_invitation()

    def new_invitation(self, pid: str | None = None) -> str:
        with self.lock:
            secret = self.room.invite(pid)
            self.link = f'nuzlocke://{self.address}/room#{secret}'
            return self.link

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
            self.link = ''


class RoomPeer:
    def __init__(self, invite: object, person: JSONDict) -> None:
        self.base, secret = room_invitation(invite)
        response = room_request(self.base, '/v2/join', secret, {'protocol': 2, 'features': ['capture-links-v1'], **person})
        token = response.get('token')
        if not isinstance(token, str) or SECRET_RE.fullmatch(token) is None:
            raise ValueError('Credencial de sala inválida')
        self.token = token
        self.view = room_view(response.get('room'))
        if 'capture-links-v1' not in self.view['features']:
            try:
                room_request(self.base, '/v2/leave', token, {'protocol': 2,
                    'session_id': self.view['session_id'], 'epoch': self.view['epoch'],
                    'run_id': person['run_id'], 'sequence': 1, 'state': None})
            except ValueError:
                pass
            raise ValueError('El host no admite grupos de captura; actualiza ambos Trackers')
        if not any(m['player_id'] == person['player_id'] and m['run_id'] == person['run_id']
                   and m['game'] == person['game'] for m in self.view['members']):
            raise ValueError('Jugador ausente en la sala')

    def exchange(self, data: JSONDict, *, leave: bool = False) -> JSONDict:
        response = room_request(self.base, '/v2/leave' if leave else '/v2/exchange', self.token, data)
        view = room_view(response.get('room'))
        if view['session_id'] != self.view['session_id'] or view['epoch'] != self.view['epoch']:
            raise ValueError('La sala ha cambiado; solicita otra invitación')
        if view['revision'] < self.view['revision']:
            raise ValueError('Respuesta de sala antigua')
        self.view = view
        return view
