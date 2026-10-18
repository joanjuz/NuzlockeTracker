"""Real loopback peers: no third-party service, no tracker administration."""
import http.client
import json
import socket
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest.mock import patch

from companion.direct import MAX_MESSAGE_BYTES, invitation, private_address, request_json
from companion.sync import CompanionSync
from tests.test_companion import Service


class DirectCompanionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.own = Service()
        self.other = Service()
        self.other.current['game'] = 'Ultra Moon 1.0'
        self.other.current['party'][0]['nickname'] = 'Luna'
        self.host = CompanionSync(self.own, Path(self.directory.name) / 'host')
        self.peer = CompanionSync(self.other, Path(self.directory.name) / 'peer')
        self.addCleanup(self.host.close)
        self.addCleanup(self.peer.close)

    def start_host(self):
        return self.host.perform('direct_host', {
            'host': '127.0.0.1', 'port': 0, 'name': 'Sol', 'game': 'Ultra Sun 1.0'})

    def join(self):
        status = self.start_host()
        return self.peer.perform('direct_join', {'invite_code': status['invite_link'],
                                 'name': 'Luna', 'game': 'Ultra Moon 1.0'})

    def test_two_applications_exchange_only_sanitized_snapshots_and_manual_deaths(self):
        joined = self.join()
        self.host.sync_once()
        self.assertEqual(joined['partner']['state']['party'][0]['nickname'], 'Goty')
        self.assertEqual(self.host.status()['partner']['state']['party'][0]['nickname'], 'Luna')
        death = self.other.current['progress']['deaths']['33:1234']
        death['source'] = 'soullink-response'
        death['pokemon']['nickname'] = 'Fallecido'
        death['credential'] = 'private-death-token'
        self.peer.sync_once()
        received = self.host.status()['partner']['state']
        self.assertEqual(received['progress']['deaths']['33:1234']['source'], 'soullink-response')
        self.assertEqual(received['progress']['deaths']['33:1234']['pokemon']['nickname'], 'Fallecido')
        self.assertNotIn('private-death-token', json.dumps(received))
        self.assertNotIn('NEVER_SEND', json.dumps(received))
        self.assertNotIn('pid', json.dumps(received))
        self.assertNotIn('session', joined)
        self.assertEqual(self.own.current['party'][0]['nickname'], 'Goty')
        self.assertEqual(self.own.current['progress']['deaths']['33:1234'].get('source'), None)
        self.assertFalse(any(Path(self.directory.name).rglob('companion-credentials.json')))

    def test_invitation_is_single_use_and_session_is_not_exposed(self):
        status = self.start_host()
        original_invite = status['invite_code']
        self.peer.perform('direct_join', {'invite_code': original_invite,
                          'name': 'Luna', 'game': 'Ultra Moon 1.0'})
        status = self.host.status()
        self.assertEqual(status['invite_code'], '')
        self.assertEqual(status['invite_link'], '')
        base, secret = invitation(original_invite)
        with self.assertRaisesRegex(ValueError, '401'):
            request_json(base, '/v1/join', secret, {'name': 'Intruso', 'game': 'Ultra Moon 1.0'})
        with self.assertRaisesRegex(ValueError, '401'):
            request_json(base, '/v1/exchange', secret, {'state': None})
        self.assertNotIn(self.peer.direct_session[1], json.dumps(status))
        self.assertEqual(status['partner']['name'], 'Luna')

    def test_explicit_leave_closes_listener_and_rejects_old_invitation(self):
        status = self.start_host()
        port = self.host.direct_host.server.server_port
        self.host.perform('leave')
        self.assertFalse(self.host.status()['configured'])
        with socket.socket() as sock:
            sock.settimeout(0.3)
            self.assertNotEqual(sock.connect_ex(('127.0.0.1', port)), 0)
        self.start_host()
        self.assertNotEqual(self.host.status()['invite_code'], status['invite_code'])

    def test_occupied_host_address_is_rejected_without_disturbing_first_pair(self):
        status = self.start_host()
        port = self.host.direct_host.server.server_port
        with self.assertRaisesRegex(ValueError, 'abrir el host'):
            self.peer.perform('direct_host', {'host': '127.0.0.1', 'port': port,
                              'name': 'Otro host', 'game': 'Ultra Moon 1.0'})
        self.assertFalse(self.peer.status()['configured'])
        self.assertIsNone(self.peer.direct_host)
        self.assertEqual(self.host.status()['invite_code'], status['invite_code'])
        joined = self.peer.perform('direct_join', {'invite_code': status['invite_code'],
                                   'name': 'Luna', 'game': 'Ultra Moon 1.0'})
        self.assertEqual(joined['partner']['name'], 'Sol')
        self.assertEqual(self.host.status()['partner']['name'], 'Luna')

    def test_joined_peer_can_leave_even_when_host_is_offline(self):
        self.join()
        self.host.close()
        status = self.peer.perform('leave')
        self.assertFalse(status['configured'])
        self.assertIsNone(status['partner'])

    def test_restart_never_opens_network_listener_or_restores_direct_secret(self):
        self.join()
        new = CompanionSync(Service(), self.host.directory)
        self.addCleanup(new.close)
        self.assertFalse(new.status()['configured'])
        self.assertIsNone(new.direct_host)

    def test_disconnected_tracker_preserves_last_good_snapshot(self):
        self.join()
        host_stamp = self.peer.status()['partner']['updated_at']
        peer_stamp = self.host.status()['partner']['updated_at']
        self.own.current['stale'] = True
        self.other.current['stale'] = True
        self.other.current['party'][0]['nickname'] = 'No enviar'
        with patch('companion.direct.time.time', return_value=2_000_000_000):
            self.host.sync_once()
            self.peer.sync_once()
        self.assertEqual(self.host.status()['partner']['state']['party'][0]['nickname'], 'Luna')
        self.assertIn('lectura actual', self.peer.status()['error'])
        self.assertEqual(self.peer.status()['partner']['updated_at'], host_stamp)
        self.assertEqual(self.host.status()['partner']['updated_at'], peer_stamp)

    def test_authentication_origin_limits_and_admin_paths_are_rejected(self):
        status = self.start_host()
        port = self.host.direct_host.server.server_port
        base, secret = invitation(status['invite_code'])
        with self.assertRaisesRegex(ValueError, '401'):
            request_json(base, '/v1/join', 'x' * 43, {})
        for path in ('/api/command', '/api/state', '/api/companion', '/../runtime/private'):
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, '404'):
                request_json(base, path, secret, {'action': 'mark_dead'})
        for headers, expected in (({'Origin': 'http://attacker.test'}, 403),
                                  ({'Content-Length': str(MAX_MESSAGE_BYTES + 1)}, 413),
                                  ({'Content-Type': 'text/plain'}, 415)):
            connection = http.client.HTTPConnection('127.0.0.1', port, timeout=3)
            defaults = {'Authorization': 'Bearer ' + secret, 'Content-Type': 'application/json'}
            defaults.update(headers)
            connection.request('POST', '/v1/join', body=b'{}', headers=defaults)
            response = connection.getresponse()
            self.assertEqual(response.status, expected)
            response.read()
            connection.close()
        self.assertIsNone(self.host.status()['partner'])

    def test_unsafe_targets_and_malformed_invites_make_no_network_requests(self):
        valid_secret = 'A' * 43
        invalid = ('http://127.0.0.1:8766/join#' + valid_secret,
                   'nuzlocke://example.com:8766/join#' + valid_secret,
                   'nuzlocke://169.254.169.254:80/join#' + valid_secret,
                   'nuzlocke://8.8.8.8:80/join#' + valid_secret,
                   'nuzlocke://user@127.0.0.1:8766/join#' + valid_secret,
                   'nuzlocke://127.0.0.1:8766/api/command#' + valid_secret,
                   'nuzlocke://127.0.0.1:8766/join?key=x#' + valid_secret,
                   'nuzlocke://[::1]:8766/join#' + valid_secret)
        with patch('companion.direct.build_opener') as opener:
            for value in invalid:
                with self.subTest(value=value), self.assertRaises(ValueError):
                    self.peer.perform('direct_join', {'invite_code': value, 'name': 'Luna', 'game': 'Ultra Moon 1.0'})
            opener.assert_not_called()

    def test_supported_vpn_ranges_and_wildcard_rejection(self):
        for address in ('26.10.20.30', '100.64.20.30', '10.0.0.2', '192.168.1.3', '172.31.1.2'):
            with self.subTest(address=address):
                self.assertEqual(private_address(address), address)
                base, secret = invitation(f'nuzlocke://{address}:8770/join#' + 'A' * 43)
                self.assertEqual(base, f'http://{address}:8770')
                self.assertEqual(secret, 'A' * 43)
        for address in ('0.0.0.0', '169.254.169.254', '172.32.0.1', '100.128.0.1'):
            with self.subTest(address=address), self.assertRaises(ValueError):
                private_address(address)

    def test_malformed_authenticated_snapshot_cannot_replace_last_valid_state(self):
        self.join()
        base, session = self.peer.direct_session
        valid = self.host.status()['partner']['state']
        malformed = ([], {'schema_version': 1, 'game': 'Ultra Moon 1.0',
                         'party': [None] * 6, 'progress': ['invalid']},
                     dict(valid, game='Ultra Sun 1.0'))
        for state in malformed:
            with self.subTest(state=state), self.assertRaisesRegex(ValueError, '400'):
                request_json(base, '/v1/exchange', session, {'state': state})
            self.assertEqual(self.host.status()['partner']['state'], valid)
        self.peer.sync_once()
        self.assertEqual(self.peer.status()['error'], '')

    def test_redirects_never_forward_credentials_or_snapshot(self):
        destination_calls = []

        class Destination(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                destination_calls.append(self.headers.get('Authorization'))
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{}')

        destination = self.start_test_server(Destination)

        class Redirect(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                self.send_response(307)
                self.send_header('Location', f'http://127.0.0.1:{destination.server_port}/steal')
                self.end_headers()

        source = self.start_test_server(Redirect)
        with self.assertRaisesRegex(ValueError, '307'):
            request_json(f'http://127.0.0.1:{source.server_port}', '/v1/exchange', 'A' * 43, {'private': 'state'})
        self.assertEqual(destination_calls, [])

    def test_oversized_peer_response_is_rejected(self):
        class Oversized(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                # Consume the request before closing on Windows; unread POST
                # bytes can reset the socket before its response is delivered.
                self.rfile.read(int(self.headers.get('Content-Length', '0')))
                self.send_response(200)
                self.send_header('Content-Length', str(MAX_MESSAGE_BYTES + 1))
                self.end_headers()
                self.wfile.write(b' ' * (MAX_MESSAGE_BYTES + 1))

        server = self.start_test_server(Oversized)
        with self.assertRaisesRegex(ValueError, 'demasiado grande'):
            request_json(f'http://127.0.0.1:{server.server_port}', '/v1/exchange', 'A' * 43, {})

    def start_test_server(self, handler):
        server = HTTPServer(('127.0.0.1', 0), handler)
        thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': 0.05}, daemon=True)
        thread.start()
        def close():
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)
        self.addCleanup(close)
        return server


if __name__ == '__main__':
    unittest.main()
