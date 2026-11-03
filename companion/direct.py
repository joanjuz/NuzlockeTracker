"""Opt-in Soul Link transport for a trusted LAN or an encrypted private VPN.

Only this isolated server is reachable by the peer; the tracker UI/admin server
remains on loopback. Invitations and session credentials are memory-only.
"""
from __future__ import annotations

import copy
import hmac
import ipaddress
import json
import re
import secrets
import socket
import sys
import threading
import time
from email.message import Message
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import IO, Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from .snapshot import SUPPORTED_GAMES, MAX_SNAPSHOT_BYTES, JSONDict, shared_state

MAX_MESSAGE_BYTES = MAX_SNAPSHOT_BYTES + 4096
NETWORKS = tuple(ipaddress.ip_network(n) for n in
                 ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16',
                  '100.64.0.0/10', '127.0.0.0/8', '26.0.0.0/8'))  # Radmin VPN adapter range.
SECRET_RE = re.compile(r'[A-Za-z0-9_-]{43}')


def private_address(value: Any) -> str:
    try:
        address = ipaddress.IPv4Address(value)
    except (ValueError, TypeError):
        raise ValueError('Selecciona una dirección IPv4 de tu red local o VPN') from None
    if not any(address in network for network in NETWORKS):
        raise ValueError('Solo se permiten direcciones de red local, VPN privada o loopback')
    return str(address)


def identity(name: object, game: object) -> tuple[str, str]:
    if (not isinstance(name, str) or not 1 <= len(name.strip()) <= 32
            or any(ord(c) < 32 or c in '<>' for c in name)):
        raise ValueError('Escribe un nombre entre 1 y 32 caracteres')
    if not isinstance(game, str) or game not in SUPPORTED_GAMES:
        raise ValueError('Selecciona un juego compatible con el tracker')
    return name.strip(), game


def invitation(value: object) -> tuple[str, str]:
    if not isinstance(value, str) or len(value) > 200:
        raise ValueError('Invitación directa inválida')
    try:
        parts = urlsplit(value.strip())
        host = private_address(parts.hostname)
        port = parts.port
        if (parts.scheme != 'nuzlocke' or parts.path != '/join' or parts.query
                or parts.username or parts.password or not port or not SECRET_RE.fullmatch(parts.fragment)):
            raise ValueError()
    except (ValueError, TypeError):
        raise ValueError('Usa la invitación nuzlocke:// completa de tu compañero') from None
    return f'http://{host}:{port}', parts.fragment


def safe_state(data: object) -> JSONDict | None:
    # Rebuild from the shared allowlist with per-field type/range validation,
    # including nested death records and route marks.
    return shared_state(data)


def partner(data: object) -> JSONDict | None:
    if data is None:
        return None
    if not isinstance(data, dict):
        raise ValueError('Compañero inválido')
    name, game = identity(data.get('name'), data.get('game'))
    state = safe_state(data.get('state'))
    if state is not None and state['game'] != game:
        raise ValueError('La sesión no coincide con el juego del compañero')
    updated_at = data.get('updated_at')
    if state is not None and (type(updated_at) is not int or not 0 <= updated_at <= 2 ** 53):
        raise ValueError('Fecha de sesión inválida')
    return {'name': name, 'game': game, 'state': state,
            'updated_at': updated_at if state is not None else None}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req: Request, fp: IO[bytes], code: int, msg: str,
                         headers: Message, newurl: str) -> Request | None:
        return None


def request_json(base: str, path: str, secret: str, data: JSONDict) -> JSONDict:
    # Only called with a numeric, validated invitation target. Never proxy or
    # follow redirects: neither credentials nor snapshots may leave that target.
    body = json.dumps(data, ensure_ascii=False).encode('utf-8')
    if len(body) > MAX_MESSAGE_BYTES:
        raise ValueError('La sesión directa supera el tamaño permitido')
    request = Request(base + path, data=body, method='POST', headers={
        'Content-Type': 'application/json', 'Authorization': 'Bearer ' + secret})
    try:
        with build_opener(ProxyHandler({}), NoRedirect()).open(request, timeout=3) as response:
            raw = response.read(MAX_MESSAGE_BYTES + 1)
            if len(raw) > MAX_MESSAGE_BYTES:
                raise ValueError('Respuesta directa demasiado grande')
            result = json.loads(raw)
            if not isinstance(result, dict):
                raise ValueError('Respuesta directa inválida')
            return result
    except HTTPError as error:
        error.close()  # Release the socket; avoids leaked responses on retries.
        raise ValueError('Conexión directa rechazada (HTTP ' + str(error.code) + ')') from None
    except (URLError, OSError, TimeoutError):
        raise ValueError('No se pudo contactar al host; revisa la red o VPN y el firewall') from None
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        raise ValueError('Respuesta directa inválida') from None


class ExclusiveHTTPServer(HTTPServer):
    # Windows SO_REUSEADDR can let two applications share the same listening
    # address. A second host must fail instead of receiving another pair's data.
    allow_reuse_address = False
    def server_bind(self) -> None:
        if sys.platform == 'win32':
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


class DirectRequestHandler(BaseHTTPRequestHandler):
    """HTTP handler of the isolated Soul Link listener.

    Bound to one DirectHost by handler_for(). Every check (Origin/Host, route,
    constant-time secret compare, size and type limits, single-use invitation)
    runs under the host lock, in the same order as before.
    """
    server_version = 'SoulLink'
    sys_version = ''
    owner: DirectHost  # Set on the per-host subclass created by handler_for().
    body_read: bool

    def log_message(self, format: str, *args: Any) -> None:
        pass  # Never log invitation/session secrets or partner data.

    def setup(self) -> None:
        super().setup()
        self.connection.settimeout(2)
        self.body_read = False

    def finish(self) -> None:
        # A rejected request still has its body in the socket. Closing
        # with unread data makes Windows send RST, which can destroy the
        # error reply before the peer reads it: half-close and drain a
        # bounded amount first, so 403/413/415 always arrive intact.
        if not self.body_read:
            try:
                self.wfile.flush()
                self.connection.shutdown(socket.SHUT_WR)
                self.connection.settimeout(0.2)
                drained = 0
                while drained < 256_000:
                    chunk = self.connection.recv(65536)
                    if not chunk:
                        break
                    drained += len(chunk)
            except OSError:
                pass
        super().finish()

    def reply(self, code: int, value: JSONDict) -> None:
        raw = json.dumps(value, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Connection', 'close')
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self) -> None:
        owner = self.owner
        if (self.headers.get('Origin') is not None or self.headers.get('Host') != owner.address
                or self.headers.get('Transfer-Encoding') is not None):
            self.reply(403, {'error': 'Solicitud rechazada'})
            return
        if self.path not in ('/v1/join', '/v1/exchange', '/v1/leave'):
            self.reply(404, {'error': 'Ruta no disponible'})
            return
        with owner.lock:
            if not self._authorized(owner):
                self.reply(401, {'error': 'Invitación o sesión inválida'})
                return
            try:
                data = self._read_body()
                if data is not None:
                    self._dispatch(owner, data)
            except (ValueError, TypeError, KeyError, RecursionError):
                self.reply(400, {'error': 'Sesión inválida'})

    def _authorized(self, owner: DirectHost) -> bool:
        """Call with owner.lock held. Constant-time compare of the Bearer secret."""
        expected = owner.invite_secret if self.path == '/v1/join' else owner.session_secret
        if not expected:
            return False
        supplied = self.headers.get('Authorization', '')
        return hmac.compare_digest(supplied.encode('utf-8'), ('Bearer ' + expected).encode('ascii'))

    def _read_body(self) -> JSONDict | None:
        """Read one bounded JSON object; on a size/type rejection reply and return None."""
        length = self.headers.get_all('Content-Length', [])
        if len(length) != 1 or not length[0].isdigit():
            self.reply(400, {'error': 'Tamaño requerido'})
            return None
        size = int(length[0])
        if size > MAX_MESSAGE_BYTES:
            self.reply(413, {'error': 'Sesión demasiado grande'})
            return None
        if self.headers.get('Content-Type') != 'application/json':
            self.reply(415, {'error': 'JSON requerido'})
            return None
        data = json.loads(self.rfile.read(size))
        self.body_read = True
        if not isinstance(data, dict):
            raise ValueError()
        return data

    def _dispatch(self, owner: DirectHost, data: JSONDict) -> None:
        """Call with owner.lock held: apply one authenticated request."""
        if self.path == '/v1/join':
            owner.remote = partner(data)
            owner.session_secret = secrets.token_urlsafe(32)
            owner.invite_secret = None  # One invitation, one peer.
            self.reply(200, {'session': owner.session_secret, 'partner': owner.local_info()})
        elif self.path == '/v1/leave':
            owner.remote = None
            owner.session_secret = None
            # Rehosting is explicit; a used invitation never becomes valid again.
            self.reply(200, {'ok': True})
        else:
            if data.get('state') is not None:
                incoming = safe_state(data['state'])
                remote = owner.remote
                # No partner yet (remote None) is rejected like any bad session.
                if incoming is None or remote is None or incoming['game'] != remote['game']:
                    raise ValueError()
                remote['state'] = incoming
                remote['updated_at'] = int(time.time() * 1000)
            self.reply(200, {'partner': owner.local_info()})


def handler_for(owner: DirectHost) -> type[DirectRequestHandler]:
    """Handler class bound to one host (http.server instantiates a class per request)."""
    return type('Handler', (DirectRequestHandler,), {'owner': owner})


class DirectHost:
    def __init__(self, host: object, port: object, name: object, game: object) -> None:
        self.name, self.game = identity(name, game)
        address = private_address(host)
        if type(port) is not int or not 0 <= port <= 65535:
            raise ValueError('El puerto debe estar entre 1 y 65535 (0: automático)')
        self.lock = threading.RLock()
        self.invite_secret: str | None = secrets.token_urlsafe(32)
        self.session_secret: str | None = None
        self.remote: JSONDict | None = None
        self.local: JSONDict | None = None
        self.local_updated_at: int | None = None
        self.server = ExclusiveHTTPServer((address, port), handler_for(self))
        self.address = f'{address}:{self.server.server_port}'
        self.thread = threading.Thread(target=self.server.serve_forever,
                                       kwargs={'poll_interval': 0.1}, daemon=True, name='soullink-host')
        self.thread.start()

    def local_info(self) -> JSONDict:
        return {'name': self.name, 'game': self.game, 'state': self.local,
                'updated_at': self.local_updated_at}

    def status(self) -> tuple[str, JSONDict | None]:
        with self.lock:
            invite = f'nuzlocke://{self.address}/join#{self.invite_secret}' if self.invite_secret else ''
            return invite, copy.deepcopy(self.remote)

    def exchange(self, state: JSONDict | None) -> JSONDict | None:
        with self.lock:
            if state is not None:
                self.local = state
                self.local_updated_at = int(time.time() * 1000)
            return copy.deepcopy(self.remote)

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        with self.lock:
            self.invite_secret = self.session_secret = None
            self.remote = self.local = None
