"""Read-only LAN Soul Link room: no access to Lime3DS processes or local tracker files."""
from __future__ import annotations

import argparse
import hmac
import json
import secrets

import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from .protocol import SLOTS, validate_submission

BASE = Path(__file__).resolve().parent.parent
MAX_BODY = 8192
STALE_AFTER = 12.0


class Room:
    def __init__(self):
        self.viewer_token = secrets.token_urlsafe(20)
        self.players = {slot: {'token': secrets.token_urlsafe(24), 'name': slot,
                               'data': None, 'updated': 0.0} for slot in SLOTS}
        self.lock = threading.Lock()

    def publish(self, slot, token, payload):
        if slot not in self.players or not hmac.compare_digest(self.players[slot]['token'], token):
            raise PermissionError('Token de jugador invalido')
        clean = validate_submission(payload, SLOTS[slot][1])
        display_name = payload.get('display_name', slot)
        with self.lock:
            # Reject racing replay updates; the clients send at a modest cadence.
            self.players[slot]['name'] = display_name
            self.players[slot]['data'] = clean
            self.players[slot]['updated'] = time.monotonic()

    def view(self):
        now = time.monotonic()
        with self.lock:
            players = []
            for slot, player in self.players.items():
                recent = now - player['updated'] <= STALE_AFTER
                data = player['data'] if recent else None
                players.append({'slot': slot, 'team': SLOTS[slot][0], 'name': player['name'],
                                'game': SLOTS[slot][1], 'connected': bool(data and data['online']),
                                'last_seen': recent and player['updated'] > 0,
                                'party': data['party'] if data and data['online'] else [None] * 6,
                                'battle_hp': bool(data and data['battle_hp'])})
        return {'schema_version': 1, 'mode': 'soul-link-2v2-lan', 'players': players}


def make_handler(room):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            # Suppress URLs, credentials, and visitor identifiers from logs.
            pass

        def reply(self, status, body, kind='application/json; charset=utf-8'):
            raw = json.dumps(body, ensure_ascii=False).encode('utf-8') if kind.startswith('application/json') else body
            self.send_response(status)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy', "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' https://raw.githubusercontent.com; connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
            self.end_headers()
            try:
                self.wfile.write(raw)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def authorized(self, provided, expected):
            return isinstance(provided, str) and hmac.compare_digest(provided, 'Bearer ' + expected)

        def do_GET(self):
            path = urlsplit(self.path).path
            if path == '/api/room':
                if not self.authorized(self.headers.get('Authorization'), room.viewer_token):
                    self.reply(403, {'error': 'Acceso denegado'})
                else:
                    self.reply(200, room.view())
                return
            files = {'/': ('web/lan.html', 'text/html; charset=utf-8'),
                     '/lan.js': ('web/lan.js', 'text/javascript; charset=utf-8'),
                     '/lan.css': ('web/lan.css', 'text/css; charset=utf-8')}
            if path in files:
                file, kind = files[path]
                self.reply(200, (BASE / file).read_bytes(), kind)
            else:
                self.reply(404, {'error': 'No encontrado'})

        def do_POST(self):
            if urlsplit(self.path).path != '/api/player':
                self.reply(404, {'error': 'No encontrado'})
                return
            length = self.headers.get('Content-Length', '')
            if self.headers.get('Content-Type', '').split(';')[0].strip().lower() != 'application/json' or not length.isdigit() or not 0 < int(length) <= MAX_BODY:
                self.reply(400, {'error': 'Solicitud invalida'})
                return
            slot = self.headers.get('X-Player-Slot', '')
            if slot not in room.players or not self.authorized(self.headers.get('Authorization'), room.players[slot]['token']):
                self.reply(403, {'error': 'Acceso denegado'})
                return
            try:
                payload = json.loads(self.rfile.read(int(length)))
                room.publish(slot, room.players[slot]['token'], payload)
            except (ValueError, TypeError, UnicodeError):
                self.reply(400, {'error': 'Datos invalidos'})
                return
            self.reply(200, {'ok': True})
    return Handler


def print_invites(room, port):
    print('\n=== SOUL LINK 2v2 - SALA LAN ===')
    print('IP del anfitrion: consulta ipconfig (IPv4 Wi-Fi/Ethernet). Puerto:', port)
    print('Enlace del espectador: http://IP_DEL_ANFITRION:' + str(port) + '/#' + room.viewer_token)
    print('Comparte este enlace SOLO con personas autorizadas.')
    print('Claves individuales para jugadores (NO subas capturas de esta consola):')
    for slot, info in room.players.items():
        print('  ' + slot + ' (' + SLOTS[slot][1] + ') -> ' + info['token'])
    print('\nSala funcionando; Ctrl+C para cerrar. Solo para red local confiable.\n')


def main():
    parser = argparse.ArgumentParser(description='Servidor de sala local Soul Link 2v2')
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error('Usa un puerto entre 1024 y 65535')
    room = Room()
    server = ThreadingHTTPServer(('0.0.0.0', args.port), make_handler(room))
    print_invites(room, server.server_port)
    try:
        server.serve_forever(poll_interval=.2)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
