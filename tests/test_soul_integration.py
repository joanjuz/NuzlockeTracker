"""Actual loopback applications: private sharing and reusable admission never grant run commands."""
import copy
import http.client
import json
import tempfile
import threading
import time
import unittest
from contextlib import closing
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from types import SimpleNamespace
from unittest.mock import patch

from companion.snapshot import snapshot
from companion.soul_room import soul_from_snapshot
from companion.sync import CompanionSync
from server import TrackerHTTPServer, make_handler
from tests.test_companion import Service


SECRET_MARKERS = ('PRIVATE_NICK_7c19', 'PRIVATE_ABILITY_7c19', 'PRIVATE_ITEM_7c19', 'UNSELECTED_BOX_7c19')


class SoulIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.apps = []

    def app(self, index):
        service = Service()
        service.current['progress']['deaths'] = {}
        service.current['party'][0].update(nickname=SECRET_MARKERS[0], ability=SECRET_MARKERS[1], item=SECRET_MARKERS[2])
        service.current['boxes']['1'][0].update(nickname=SECRET_MARKERS[3], encryption_constant=5678)
        app = CompanionSync(service, Path(self.directory.name) / str(index))
        self.apps.append(app)
        self.addCleanup(app.close)
        return app

    def host(self):
        app = self.app(0)
        status = app.perform('soul_host', {'host': '127.0.0.1', 'port': 0,
                                          'name': 'Anfitrión', 'game': 'Ultra Sun 1.0'})
        return app, status['invite_link']

    def join(self, invitation, index):
        app = self.app(index)
        app.perform('soul_join', {'invite_code': invitation, 'name': f'Jugador {index}', 'game': 'Ultra Sun 1.0'})
        return app

    def refresh(self, *apps):
        for app in apps:
            app.sync_once(force=True)

    def assert_no_full_markers(self, value):
        serialized = json.dumps(value, ensure_ascii=False)
        for marker in SECRET_MARKERS:
            self.assertNotIn(marker, serialized)

    def assert_caches_do_not_contain_full_data(self):
        files = list(Path(self.directory.name).rglob('*.json'))
        self.assertTrue(files, 'The test must observe actual persisted metadata')
        for path in files:
            with self.subTest(file=path.name):
                raw = path.read_text(encoding='utf-8-sig')
                for marker in SECRET_MARKERS:
                    self.assertNotIn(marker, raw)

    def test_one_common_link_populates_one_through_four_and_fifth_is_clear(self):
        host, invitation = self.host()
        self.assertIn('/soul#', invitation)
        self.assertEqual(len(host.status()['room']['members']), 1)
        peers = []
        for i in range(1, 4):
            peers.append(self.join(invitation, i))
            self.assertEqual(host.status()['invite_link'], invitation)
            self.assertEqual(len(host.status()['room']['members']), i + 1)
        fifth = self.app(4)
        with self.assertRaisesRegex(ValueError, 'llena|completa|cuatro|4'):
            fifth.perform('soul_join', {'invite_code': invitation, 'name': 'Quinto', 'game': 'Ultra Sun 1.0'})
        tokens = [peer.soul.peer.token for peer in peers]
        self.assertEqual(len(set(tokens)), 3)
        self.assertNotIn(invitation.split('#')[1], tokens)
        self.refresh(host, *peers)
        self.assertTrue(all(len(app.status()['room']['members']) == 4 for app in [host, *peers]))
        for app in [host, *peers]:
            self.assert_no_full_markers(app.status())
            for token in tokens:
                self.assertNotIn(token, json.dumps(app.status()))

    def test_each_person_can_toggle_only_own_full_view_and_caches_never_keep_it(self):
        host, invitation = self.host()
        peers = [self.join(invitation, i) for i in (1, 2, 3)]
        apps = [host, *peers]
        for app in apps:
            self.assertFalse(app.status()['own_sharing'])
        # Each player's functional phase is in its own rate window. The separate
        # real-time transport test verifies burst rejection without mocking clocks.
        now = [time.monotonic()]
        with patch('companion.soul_direct.time', SimpleNamespace(monotonic=lambda: now[0])):
            for sender in apps:
                now[0] += 2
                pid = sender.status()['player_id']
                sender.perform('soul_share', {'sharing': True})
                self.refresh(*apps)
                for receiver in apps:
                    self.assertEqual(receiver.status()['error'], '', 'Receiver refresh must succeed before checking sharing')
                    member = next(m for m in receiver.status()['room']['members'] if m['player_id'] == pid)
                    self.assertTrue(member['sharing'])
                    self.assertEqual(member['state']['party'][0]['nickname'], SECRET_MARKERS[0])
                self.assert_caches_do_not_contain_full_data()
                sender.perform('soul_share', {'sharing': False})
                self.assertEqual(sender.status()['error'], '', 'The permission change must reach the room before verifying peers')
                self.refresh(*apps)
                for receiver in apps:
                    self.assertEqual(receiver.status()['error'], '', 'Receiver refresh must succeed before checking revocation')
                    member = next(m for m in receiver.status()['room']['members'] if m['player_id'] == pid)
                    self.assertFalse(member['sharing'])
                    self.assertIsNone(member['state'])
                    self.assert_no_full_markers(receiver.status())
        self.assert_caches_do_not_contain_full_data()

    def test_private_exchange_on_actual_wire_and_host_api_contains_only_linked_minimum(self):
        host, invitation = self.host()
        peer = self.join(invitation, 1)
        captured = []
        target = urlsplit(peer.soul.peer.base)
        class RecordingProxy(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass
            def do_POST(self):
                raw = self.rfile.read(int(self.headers['Content-Length']))
                captured.append(raw)
                with closing(http.client.HTTPConnection(target.hostname, target.port, timeout=3)) as connection:
                    connection.request('POST', self.path, raw, {'Content-Type': 'application/json',
                                       'Authorization': self.headers.get('Authorization', '')})
                    response = connection.getresponse()
                    reply = response.read()
                    self.send_response(response.status)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Content-Length', str(len(reply)))
                    self.end_headers()
                    self.wfile.write(reply)
        proxy = HTTPServer(('127.0.0.1', 0), RecordingProxy)
        proxy_thread = threading.Thread(target=proxy.serve_forever, daemon=True)
        proxy_thread.start()
        def close_proxy():
            proxy.shutdown()
            proxy.server_close()
            proxy_thread.join(timeout=3)
        self.addCleanup(close_proxy)
        peer.soul.peer.base = f'http://127.0.0.1:{proxy.server_port}'
        peer.perform('soul_link', {'route': 'alola:8', 'pokemon_key': '33:1234'})
        self.refresh(peer, host)
        self.assertTrue(captured)
        for raw in captured:
            body = json.loads(raw)
            self.assertFalse(body['sharing'])
            self.assertIsNone(body['state'])
            for marker in SECRET_MARKERS:
                self.assertNotIn(marker.encode(), raw)
        api = TrackerHTTPServer(('127.0.0.1', 0), make_handler(host.service, 'csrf-local', host))
        api_thread = threading.Thread(target=api.serve_forever, daemon=True)
        api_thread.start()
        def close_api():
            api.shutdown()
            api.server_close()
            api_thread.join(timeout=3)
        self.addCleanup(close_api)
        with closing(http.client.HTTPConnection(*api.server_address, timeout=3)) as connection:
            connection.request('GET', '/api/companion')
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            data = json.loads(response.read())
        remote = data['room']['members'][1]
        self.assertIsNone(remote['state'])
        self.assertEqual(set(remote['soul']['captures']), {'alola:8'})
        capture = remote['soul']['captures']['alola:8']
        self.assertEqual(capture['key'], '33:1234')
        self.assertEqual(set(capture['pokemon']), {'species_id', 'origin_version', 'encryption_constant', 'met_location_id'})
        self.assert_no_full_markers(data)
        self.assert_caches_do_not_contain_full_data()

    def test_application_restart_reserves_slot_and_resumes_individual_identity_privately(self):
        host, invitation = self.host()
        peer = self.join(invitation, 1)
        directory = peer.directory
        identity = copy.deepcopy(peer.soul.person)
        old_token = peer.soul.peer.token
        peer.perform('soul_share', {'sharing': True})
        peer.close()  # Application shutdown is not explicit voluntary leave.
        self.assertEqual(len(host.status()['room']['members']), 2)
        restarted = CompanionSync(Service(), directory)
        self.addCleanup(restarted.close)
        self.assertFalse(restarted.soul.active)
        self.assert_no_full_markers(restarted.status())
        restarted.perform('soul_join', {'invite_code': invitation, 'name': 'Regreso', 'game': 'Ultra Sun 1.0'})
        self.assertEqual(restarted.soul.person['player_id'], identity['player_id'])
        self.assertEqual(restarted.soul.person['run_id'], identity['run_id'])
        self.assertNotEqual(restarted.soul.peer.token, old_token)
        self.assertFalse(restarted.status()['own_sharing'])
        self.assertIsNone(host.status()['room']['members'][1]['state'])
        with self.assertRaises(ValueError):
            host.soul.host.room.authenticate(old_token)
        self.assertEqual(len(host.status()['room']['members']), 2)
        self.assert_caches_do_not_contain_full_data()

    def test_leave_frees_slot_and_revoked_admission_does_not_kill_current_connections(self):
        host, invitation = self.host()
        peers = [self.join(invitation, i) for i in (1, 2, 3)]
        departed_id = peers[1].status()['player_id']
        token = peers[1].soul.peer.token
        peers[1].perform('leave')
        self.assertEqual(len(host.status()['room']['members']), 3)
        replacement = self.join(invitation, 4)
        self.assertNotEqual(replacement.status()['player_id'], departed_id)
        with self.assertRaises(ValueError):
            host.soul.host.room.authenticate(token)
        host.perform('soul_revoke')
        self.assertEqual(host.status()['invite_link'], '')
        self.refresh(peers[0], peers[2], replacement)
        self.assertTrue(all(not app.status()['error'] for app in (peers[0], peers[2], replacement)))
        with self.assertRaises(ValueError):
            self.join(invitation, 5)
        self.assertEqual(len(host.status()['room']['members']), 4)

    def test_offline_receiver_restart_cannot_recover_a_revoked_full_view(self):
        host, invitation = self.host()
        sender = self.join(invitation, 1)
        receiver = self.join(invitation, 2)
        sender.perform('soul_share', {'sharing': True})
        self.refresh(receiver)
        self.assertIsNotNone(receiver.status()['room']['members'][1]['state'])
        receiver.close()
        sender.perform('soul_share', {'sharing': False})
        restored = CompanionSync(Service(), receiver.directory)
        self.addCleanup(restored.close)
        self.assert_no_full_markers(restored.status())
        self.assertFalse(restored.soul.active)
        restored.perform('soul_join', {'invite_code': invitation, 'name': 'Regreso', 'game': 'Ultra Sun 1.0'})
        self.assertIsNone(restored.status()['room']['members'][1]['state'])
        self.assert_caches_do_not_contain_full_data()

    def test_failed_network_exchange_clears_existing_full_views(self):
        host, invitation = self.host()
        sender = self.join(invitation, 1)
        sender.perform('soul_share', {'sharing': True})
        receiver = self.join(invitation, 2)
        self.refresh(receiver)
        self.assertIsNotNone(receiver.status()['room']['members'][1]['state'])
        host.perform('leave')
        self.refresh(receiver)
        self.assertTrue(receiver.status()['error'])
        self.assertTrue(all(m['state'] is None for m in receiver.status()['room']['members']))
        self.assert_no_full_markers(receiver.status())

    def test_submillisecond_status_polling_never_extends_the_authoritative_view_lease(self):
        host, invitation = self.host()
        sender = self.join(invitation, 1)
        sender.perform('soul_share', {'sharing': True})
        receiver = self.join(invitation, 2)
        self.refresh(receiver)
        remote = receiver.soul.view['members'][1]
        self.assertIsNotNone(remote['state'])
        # Simulate a response with the full maximum allowance at one receipt.
        receiver.soul.received_at = 100.0
        remote['view_ttl_ms'] = 12000
        now = [100.0]
        with patch('companion.soul_sync.time', SimpleNamespace(monotonic=lambda: now[0])):
            for _ in range(40):
                now[0] += 0.0004
                current = receiver.status()['room']['members'][1]
                self.assertLessEqual(current['view_ttl_ms'], 12000 - int((now[0] - 100.0) * 1000))
            now[0] = 112.001
            expired = receiver.status()['room']['members'][1]
            self.assertIsNone(expired['state'])
            self.assertEqual(expired['view_ttl_ms'], 0)
            self.assertIsNone(receiver.soul.peer.view['members'][1]['state'])

    def test_failed_host_bind_preserves_saved_individual_recovery_proof(self):
        host, invitation = self.host()
        peer = self.join(invitation, 1)
        original_id = peer.soul.person['player_id']
        directory = peer.directory
        peer.close()
        recovered = CompanionSync(Service(), directory)
        self.addCleanup(recovered.close)
        credentials_before = recovered.soul.storage.credentials_path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'crear la sala'):
            recovered.perform('soul_host', {'host': '127.0.0.1', 'port': host.soul.host.server.server_port,
                                          'name': 'Intento', 'game': 'Ultra Sun 1.0'})
        self.assertFalse(recovered.soul.active)
        self.assertEqual(recovered.soul.storage.credentials_path.read_bytes(), credentials_before)
        recovered.perform('soul_join', {'invite_code': invitation, 'name': 'Regreso', 'game': 'Ultra Sun 1.0'})
        self.assertEqual(recovered.soul.person['player_id'], original_id)
        self.assertEqual(len(host.status()['room']['members']), 2)

    def test_failed_credential_save_releases_admission_then_explicit_forget_allows_fresh_join(self):
        host, invitation = self.host()
        peer = self.app(1)
        old_id = peer.soul.storage.data['player_id']
        with patch.object(peer.soul.storage, 'save_credentials', side_effect=OSError('Synthetic storage failure')):
            with self.assertRaisesRegex(ValueError, 'Salir'):
                peer.perform('soul_join', {'invite_code': invitation, 'name': 'Intento', 'game': 'Ultra Sun 1.0'})
        self.assertFalse(peer.soul.active)
        self.assertTrue(peer.status()['can_forget'])
        self.assertEqual(len(host.status()['room']['members']), 1)
        self.assert_no_full_markers(peer.status())
        peer.perform('leave')
        self.assertNotEqual(peer.soul.storage.data['player_id'], old_id)
        self.assertFalse(peer.status()['can_forget'])
        peer.perform('soul_join', {'invite_code': invitation, 'name': 'Nuevo intento', 'game': 'Ultra Sun 1.0'})
        self.assertEqual(len(host.status()['room']['members']), 2)
        self.assertEqual(host.status()['room']['members'][1]['player_id'], peer.status()['player_id'])

    def test_explicit_forget_does_not_overwrite_corrupt_or_future_identity_metadata(self):
        directory = Path(self.directory.name)/'future'
        directory.mkdir()
        path = directory/'companion-soul.json'
        content = '{"version":999,"future":{"preserve":"USER_DATA"}}'
        path.write_text(content, encoding='utf-8')
        peer = CompanionSync(Service(), directory)
        self.addCleanup(peer.close)
        self.assertTrue(peer.soul.storage.error)
        with self.assertRaises(ValueError):
            peer.perform('leave')
        self.assertEqual(path.read_text(encoding='utf-8'), content)

    def test_existing_progress_files_and_legacy_modes_are_preserved(self):
        app = self.app(0)
        app.directory.mkdir(parents=True, exist_ok=True)
        files = {'progress.json': b'{"deaths":{"33:10":{"reason":"original"}}}',
                 'game-data.json': b'{"source":"DGD_ORIGINAL_MARKER"}'}
        for name, raw in files.items():
            (app.directory/name).write_bytes(raw)
        before = copy.deepcopy(app.service.current)
        legacy = app.perform('direct_host', {'host': '127.0.0.1', 'port': 0,
                   'name': 'Anterior', 'game': 'Ultra Sun 1.0'})
        self.assertIn('/join#', legacy['invite_link'])
        with self.assertRaises(ValueError):
            app.perform('soul_host', {'host': '127.0.0.1', 'port': 0, 'name': 'Nuevo', 'game': 'Ultra Sun 1.0'})
        app.perform('leave')
        app.perform('soul_host', {'host': '127.0.0.1', 'port': 0, 'name': 'Nuevo', 'game': 'Ultra Sun 1.0'})
        app.perform('soul_share', {'sharing': True})
        app.perform('soul_share', {'sharing': False})
        app.perform('leave')
        self.assertEqual(app.service.current, before)
        for name, raw in files.items():
            self.assertEqual((app.directory/name).read_bytes(), raw)

    def test_private_link_death_remains_minimal_and_does_not_mutate_other_run(self):
        host, invitation = self.host()
        peer = self.join(invitation, 1)
        for app in (host, peer):
            app.perform('soul_link', {'route': 'alola:8', 'pokemon_key': '33:1234'})
        original = copy.deepcopy(host.service.current)
        peer.service.current['progress']['deaths']['33:1234'] = {
            'pokemon': peer.service.current['party'][0], 'recorded_at': '2026-11-13T04:00:00'}
        self.refresh(peer, host)
        status = host.status()
        capture = status['room']['members'][1]['soul']['captures']['alola:8']
        self.assertEqual(capture['status'], 'dead')
        self.assertEqual(capture['death_at'], '2026-11-13T04:00:00')
        self.assertIsNone(status['room']['members'][1]['state'])
        self.assertEqual(host.service.current, original)
        self.assert_no_full_markers(status)
        self.assert_caches_do_not_contain_full_data()

    def test_authenticated_sender_cannot_set_another_participants_sharing(self):
        host, invitation = self.host()
        sender = self.join(invitation, 1)
        other = self.join(invitation, 2)
        view = sender.status()['room']
        source = snapshot(sender.service.current)
        sender.soul.sequence += 1
        sender.soul.peer.exchange({'protocol': 3, 'session_id': view['session_id'], 'epoch': view['epoch'],
            'run_id': sender.soul.person['run_id'], 'sequence': sender.soul.sequence,
            'sharing': True, 'source_live': True, 'state': source, 'links': {},
            'soul': soul_from_snapshot(source, {}), 'player_id': other.status()['player_id']})
        members = host.status()['room']['members']
        self.assertTrue(members[1]['sharing'])
        self.assertFalse(members[2]['sharing'])
        self.assertIsNone(members[2]['state'])


if __name__ == '__main__':
    unittest.main()
