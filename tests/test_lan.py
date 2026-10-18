import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from lan.client import publish_once, validate_local, validate_host
from lan.protocol import public_state, validate_submission
from lan.room import Room, make_handler


def pokemon(species=448, hp=205):
    return {'species_id': species, 'species': 'Lucario', 'nickname': 'Goty', 'level': 75,
            'hp': hp, 'max_hp': 217, 'moves': [1, 2, 3, 4], 'iv': [31] * 6,
            'met_location': 'privado', 'encryption_constant': 123}


def state(game='Ultra Sun 1.0', online=True):
    return {'game': game, 'stale': not online, 'connection': {'status': 'connected' if online else 'disconnected'},
            'battle_hp': True, 'party': [pokemon()] + [None] * 5,
            'boxes': {'1': [{'nickname': 'PRIVATE'}]}, 'progress': {'deaths': {'private': True}}}


class LanTests(unittest.TestCase):
    def test_public_state_minimal(self):
        data = public_state(state())
        self.assertEqual(data['party'][0]['hp'], 205)
        self.assertEqual(data['party'][0]['species_id'], 448)
        for banned in ('boxes', 'progress', 'moves', 'iv', 'encryption_constant', 'met_location'):
            self.assertNotIn(banned, json.dumps(data))
        self.assertEqual(data['game'], 'Ultra Sun 1.0')

    def test_offline_not_published(self):
        data = public_state(state(online=False))
        self.assertFalse(data['online'])
        self.assertEqual(data['party'], [None] * 6)

    def test_no_wrong_game(self):
        room = Room()
        with self.assertRaises(ValueError):
            room.publish('A-MOON', room.players['A-MOON']['token'], public_state(state()))
        with self.assertRaises(PermissionError):
            room.publish('A-SUN', 'bad', public_state(state()))

    def test_rejects_extra_fields_and_invalid_hp(self):
        clean = public_state(state())
        clean['party'][0]['moves'] = [1, 2, 3, 4]
        with self.assertRaises(ValueError):
            validate_submission(clean, 'Ultra Sun 1.0')
        clean['party'][0].pop('moves')
        clean['party'][0]['hp'] = 999
        with self.assertRaises(ValueError):
            validate_submission(clean, 'Ultra Sun 1.0')

    def test_client_urls_are_explicit(self):
        self.assertEqual(validate_local('http://127.0.0.1:4321/'), 'http://127.0.0.1:4321')
        for url in ('http://example.com:80/', 'http://127.0.0.1:4321/@bad', 'https://127.0.0.1:4321/'):
            with self.assertRaises(ValueError):
                validate_local(url)
        self.assertEqual(validate_host('http://192.168.1.5:8765/'), 'http://192.168.1.5:8765')
        with self.assertRaises(ValueError): validate_host('http://8.8.8.8:8765/')
        with self.assertRaises(ValueError): validate_host('http://example.com:8765/')

    def test_client_bridge_local_state_to_room(self):
        class LocalHandler(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_GET(self):
                if self.path != '/api/state':
                    self.send_error(404)
                    return
                raw = json.dumps(state(game='Ultra Moon 1.0')).encode()
                self.send_response(200)
                self.send_header('Content-Length', str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
        local = ThreadingHTTPServer(('127.0.0.1', 0), LocalHandler)
        room = Room()
        remote = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(room))
        workers = [threading.Thread(target=server.serve_forever, daemon=True) for server in (local, remote)]
        for worker in workers: worker.start()
        try:
            result = publish_once('http://127.0.0.1:' + str(local.server_port),
                                  'http://127.0.0.1:' + str(remote.server_port),
                                  'A-MOON', room.players['A-MOON']['token'], 'Compañero')
            self.assertTrue(result['online'])
            self.assertEqual(room.view()['players'][1]['name'], 'Compañero')
            self.assertEqual(room.view()['players'][1]['party'][0]['hp'], 205)
            self.assertFalse(room.view()['players'][0]['connected'])
            with self.assertRaisesRegex(ValueError, 'requiere Ultra Sun'):
                publish_once('http://127.0.0.1:' + str(local.server_port),
                             'http://127.0.0.1:' + str(remote.server_port),
                             'B-SUN', room.players['B-SUN']['token'])
        finally:
            for server in (local, remote): server.shutdown();server.server_close()
            for worker in workers: worker.join(2)

    def test_http_token_and_state(self):
        room = Room()
        server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(room))
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        base = 'http://127.0.0.1:' + str(server.server_port)
        try:
            with self.assertRaises(HTTPError) as exc:
                urlopen(base + '/api/room')
            self.assertEqual(exc.exception.code, 403)
            request = Request(base + '/api/room', headers={'Authorization': 'Bearer ' + room.viewer_token})
            with urlopen(request) as res:
                self.assertEqual(len(json.load(res)['players']), 4)
            submission = dict(public_state(state()), display_name='Jugador Sol')
            post = Request(base + '/api/player', json.dumps(submission).encode(), {
                'X-Player-Slot': 'A-SUN', 'Authorization': 'Bearer ' + room.players['A-SUN']['token'],
                'Content-Type': 'application/json'}, method='POST')
            with urlopen(post) as response:
                self.assertEqual(response.status, 200)
            with urlopen(request) as response:
                players = json.load(response)['players']
            self.assertTrue(players[0]['connected'])
            self.assertEqual(players[0]['party'][0]['hp'], 205)
            self.assertEqual(players[0]['name'], 'Jugador Sol')
            self.assertFalse(players[1]['connected'])
            bad = Request(base + '/api/player', b'{}', {
                'X-Player-Slot': 'A-SUN', 'Authorization': 'Bearer bad',
                'Content-Type': 'application/json'}, method='POST')
            with self.assertRaises(HTTPError) as exc:
                urlopen(bad)
            self.assertEqual(exc.exception.code, 403)
            client = Request(base + '/', method='GET')
            with urlopen(client) as response:
                self.assertIn(b'Soul Link', response.read())
        finally:
            server.shutdown()
            server.server_close()
            worker.join(2)


if __name__ == '__main__':
    unittest.main()
