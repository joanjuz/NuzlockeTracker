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
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from .snapshot import SUPPORTED_GAMES, MAX_SNAPSHOT_BYTES, snapshot

MAX_MESSAGE_BYTES = MAX_SNAPSHOT_BYTES + 4096
NETWORKS = tuple(ipaddress.ip_network(n) for n in
                 ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16',
                  '100.64.0.0/10', '127.0.0.0/8', '26.0.0.0/8'))  # Radmin VPN adapter range.
SECRET_RE = re.compile(r'[A-Za-z0-9_-]{43}')


def private_address(value):
    try:
        address = ipaddress.IPv4Address(value)
    except (ValueError, TypeError):
        raise ValueError('Selecciona una dirección IPv4 de tu red local o VPN') from None
    if not any(address in network for network in NETWORKS):
        raise ValueError('Solo se permiten direcciones de red local, VPN privada o loopback')
    return str(address)


def identity(name, game):
    if (not isinstance(name, str) or not 1 <= len(name.strip()) <= 32
            or any(ord(c) < 32 or c in '<>' for c in name)):
        raise ValueError('Escribe un nombre entre 1 y 32 caracteres')
    if not isinstance(game, str) or game not in SUPPORTED_GAMES:
        raise ValueError('Selecciona un juego compatible con el tracker')
    return name.strip(), game


def invitation(value):
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


def safe_state(data):
    if data is None:
        return None
    if not isinstance(data, dict) or data.get('schema_version') != 1:
        raise ValueError('Sesión directa incompatible')
    # Rebuild from the shared allowlist, including nested death records.
    try:
        return snapshot(dict(data, stale=False, connection={'status': 'connected'}))
    except (TypeError, AttributeError, KeyError, RecursionError):
        raise ValueError('Sesión directa inválida') from None


def partner(data):
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
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request_json(base, path, secret, data):
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
        raise ValueError('Conexión directa rechazada (HTTP ' + str(error.code) + ')') from None
    except (URLError, OSError, TimeoutError):
        raise ValueError('No se pudo contactar al host; revisa la red o VPN y el firewall') from None
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        raise ValueError('Respuesta directa inválida') from None


class ExclusiveHTTPServer(HTTPServer):
    # Windows SO_REUSEADDR can let two applications share the same listening
    # address. A second host must fail instead of receiving another pair's data.
    allow_reuse_address = False
    def server_bind(self):
        if sys.platform == 'win32':
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


class DirectHost:
    def __init__(self, host, port, name, game):
        self.name, self.game = identity(name, game)
        host = private_address(host)
        if type(port) is not int or not 0 <= port <= 65535:
            raise ValueError('El puerto debe estar entre 1 y 65535 (0: automático)')
        self.lock = threading.RLock()
        self.invite_secret = secrets.token_urlsafe(32)
        self.session_secret = None
        self.remote = None
        self.local = None
        self.local_updated_at = None
        owner = self

        class Handler(BaseHTTPRequestHandler):
            server_version = 'SoulLink'
            sys_version = ''

            def log_message(self, *args):
                pass  # Never log invitation/session secrets or partner data.

            def setup(self):
                super().setup()
                self.connection.settimeout(2)

            def reply(self, code, value):
                raw = json.dumps(value, ensure_ascii=False).encode('utf-8')
                self.send_response(code)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(raw)))
                self.send_header('Cache-Control', 'no-store')
                self.send_header('Connection', 'close')
                self.end_headers()
                self.wfile.write(raw)

            def do_POST(self):
                if (self.headers.get('Origin') is not None or self.headers.get('Host') != owner.address
                        or self.headers.get('Transfer-Encoding') is not None):
                    self.reply(403, {'error': 'Solicitud rechazada'})
                    return
                if self.path not in ('/v1/join', '/v1/exchange', '/v1/leave'):
                    self.reply(404, {'error': 'Ruta no disponible'})
                    return
                with owner.lock:
                    expected = owner.invite_secret if self.path == '/v1/join' else owner.session_secret
                    supplied = self.headers.get('Authorization', '')
                    if not expected or not hmac.compare_digest(supplied.encode('utf-8'), ('Bearer ' + expected).encode('ascii')):
                        self.reply(401, {'error': 'Invitación o sesión inválida'})
                        return
                    try:
                        length = self.headers.get_all('Content-Length', [])
                        if len(length) != 1 or not length[0].isdigit():
                            self.reply(400, {'error': 'Tamaño requerido'})
                            return
                        size = int(length[0])
                        if size > MAX_MESSAGE_BYTES:
                            self.reply(413, {'error': 'Sesión demasiado grande'})
                            return
                        if self.headers.get('Content-Type') != 'application/json':
                            self.reply(415, {'error': 'JSON requerido'})
                            return
                        data = json.loads(self.rfile.read(size))
                        if not isinstance(data, dict):
                            raise ValueError()
                        if self.path == '/v1/join':
                            remote = partner(data)
                            owner.remote = remote
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
                                if incoming['game'] != owner.remote['game']:
                                    raise ValueError()
                                owner.remote['state'] = incoming
                                owner.remote['updated_at'] = int(time.time() * 1000)
                            self.reply(200, {'partner': owner.local_info()})
                    except (ValueError, TypeError, KeyError, RecursionError):
                        self.reply(400, {'error': 'Sesión inválida'})

        self.server = ExclusiveHTTPServer((host, port), Handler)
        self.address = f'{host}:{self.server.server_port}'
        self.thread = threading.Thread(target=self.server.serve_forever,
                                       kwargs={'poll_interval': 0.1}, daemon=True, name='soullink-host')
        self.thread.start()

    def local_info(self):
        return {'name': self.name, 'game': self.game, 'state': self.local,
                'updated_at': self.local_updated_at}

    def status(self):
        with self.lock:
            invite = f'nuzlocke://{self.address}/join#{self.invite_secret}' if self.invite_secret else ''
            return invite, copy.deepcopy(self.remote)

    def exchange(self, state):
        with self.lock:
            if state is not None:
                self.local = state
                self.local_updated_at = int(time.time() * 1000)
            return copy.deepcopy(self.remote)

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        with self.lock:
            self.invite_secret = self.session_secret = None
            self.remote = self.local = None
