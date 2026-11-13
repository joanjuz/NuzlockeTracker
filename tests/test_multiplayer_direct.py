"""Real isolated HTTP listeners and 2/3/4 independent app bridges on loopback."""
import copy
import http.client
import json
import tempfile
import unittest
from pathlib import Path

from companion.direct import request_json
from companion.room_direct import room_invitation, room_request
from companion.sync import CompanionSync
from tests.test_companion import Service, mon


class MultiplayerDirectTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.apps = []

    def app(self, index):
        service = Service()
        service.current['party'][0]['nickname'] = f'Jugador {index}'
        app = CompanionSync(service, Path(self.directory.name) / str(index))
        self.apps.append(app)
        self.addCleanup(app.close)
        return app

    def host(self, capacity=4):
        app = self.app(len(self.apps))
        status = app.perform('room_host', {'host': '127.0.0.1', 'port': 0, 'name': 'Host',
                                          'game': 'Ultra Sun 1.0', 'capacity': capacity})
        return app, status

    def join(self, host, index):
        invite = host.status()['invite_link']
        if not invite:
            invite = host.perform('room_invite')['invite_link']
        app = self.app(index)
        app.perform('room_join', {'invite_code': invite, 'name': f'Invitado {index}',
                                 'game': 'Ultra Sun 1.0'})
        return app

    def test_two_three_four_independent_instances_full_snapshots_and_no_local_commands(self):
        for capacity in (2, 3, 4):
            with self.subTest(capacity=capacity):
                host, _ = self.host(capacity)
                peers = [self.join(host, len(self.apps)) for _ in range(capacity - 1)]
                for app in [host, *peers]:
                    app.sync_once(force=True)
                expected = {app.multiplayer.person['player_id'] for app in [host, *peers]}
                for app in [host, *peers]:
                    status = app.status()
                    self.assertEqual({m['player_id'] for m in status['room']['members']}, expected)
                    self.assertTrue(all(m['state'] is not None for m in status['room']['members']))
                    self.assertEqual(status['protocol'], 2)
                    self.assertNotIn('NEVER_SEND', json.dumps(status))
                    self.assertIsNone(status['partner'])  # Never run v1 death notification pipeline.
                saved = copy.deepcopy(host.service.current)
                peers[-1].service.current['progress']['deaths']['33:5678'] = {'pokemon': mon(), 'recorded_at': '2026-11-13'}
                peers[-1].sync_once(force=True)
                host.sync_once(force=True)
                event = host.status()['room']['events'][-1]
                self.assertEqual(event['kind'], 'death')
                self.assertEqual(event['player_id'], peers[-1].multiplayer.person['player_id'])
                self.assertEqual(host.service.current, saved)

    def test_loss_of_current_source_then_disconnect_retains_explicitly_stale_view(self):
        host, _ = self.host()
        peer = self.join(host, 1)
        peer.service.current['stale'] = True
        peer.sync_once(force=True)
        host.sync_once(force=True)
        remote = host.status()['room']['members'][1]
        self.assertTrue(remote['online'])
        self.assertFalse(remote['source_live'])
        self.assertIsNotNone(remote['state'])
        host.perform('leave')
        peer.sync_once(force=True)
        self.assertTrue(peer.status()['error'])
        self.assertTrue(all(not m['online'] for m in peer.status()['room']['members']))
        peer.perform('leave')
        self.assertFalse(peer.multiplayer.active)

    def test_aggregate_larger_than_v1_response_limit_and_authenticated_identity(self):
        host, _ = self.host()
        host.service.current['boxes'] = {str(i): [mon() for _ in range(30)] for i in range(1, 16)}
        peers = [self.join(host, i) for i in (1, 2, 3)]
        for peer in peers:
            peer.service.current['boxes'] = copy.deepcopy(host.service.current['boxes'])
            peer.sync_once(force=True)
        host.sync_once(force=True)
        peers[0].sync_once(force=True)
        view = peers[0].status()['room']
        self.assertGreater(len(json.dumps(view).encode()), 654_096)
        self.assertEqual(len(view['members']), 4)
        self.assertTrue(all(len(m['state']['boxes']) == 15 for m in view['members']))
        peer = peers[0]
        envelope = peer.multiplayer._envelope(None)
        envelope['player_id'] = host.multiplayer.person['player_id']
        peer.multiplayer.peer.exchange(envelope)
        current = host.status()['room']['members']
        self.assertTrue(current[0]['source_live'])
        self.assertFalse(current[1]['source_live'])

    def test_directed_reconnect_same_profile_restart_revocation_and_new_run(self):
        host, _ = self.host()
        peer = self.join(host, 1)
        pid = peer.multiplayer.person['player_id']
        old_token = peer.multiplayer.peer.token
        peer.perform('leave')
        invitation = host.perform('room_invite', {'player_id': pid})['invite_link']
        restarted = CompanionSync(Service(), peer.directory)
        self.addCleanup(restarted.close)
        self.assertFalse(restarted.multiplayer.active)
        self.assertTrue(all(not m['online'] for m in restarted.multiplayer.view['members']))
        restarted.perform('room_join', {'invite_code': invitation, 'name': 'Regreso', 'game': 'Ultra Sun 1.0'})
        self.assertEqual(restarted.multiplayer.person['player_id'], pid)
        self.assertNotEqual(restarted.multiplayer.peer.token, old_token)
        host.perform('room_remove', {'player_id': pid})
        restarted.sync_once(force=True)
        self.assertTrue(restarted.status()['error'])
        restarted.perform('leave')
        previous_run = restarted.multiplayer.person['run_id']
        restarted.perform('room_new_run', {'game': 'Ultra Sun 1.0'})
        fresh = restarted.multiplayer.storage.identity('Nuevo', 'Ultra Sun 1.0')
        self.assertNotEqual(fresh['run_id'], previous_run)

    def test_protocol_rejection_auth_origin_size_rate_and_admin_isolation(self):
        host, status = self.host()
        base, secret = room_invitation(status['invite_link'])
        with self.assertRaisesRegex(ValueError, '404'):
            request_json(base, '/v1/join', secret, {'name': 'Legacy', 'game': 'Ultra Sun 1.0'})
        with self.assertRaisesRegex(ValueError, '401'):
            room_request(base, '/v2/join', 'x' * 43, {'protocol': 2})
        address, port = status['host_address'].split(':')
        for path, headers, body, code in (
                ('/api/command', {}, b'{}', 404),
                ('/v2/join', {'Origin': 'http://attacker.invalid'}, b'{}', 403),
                ('/v2/join', {'Authorization': 'Bearer ' + secret, 'Content-Length': '700000'}, b'', 413)):
            with self.subTest(path=path, code=code):
                conn = http.client.HTTPConnection(address, int(port), timeout=3)
                self.addCleanup(conn.close)
                conn.request('POST', path, body=body, headers={'Content-Type': 'application/json', **headers})
                response = conn.getresponse()
                self.assertEqual(response.status, code)
                response.read()
        peer = self.join(host, 1)
        for _ in range(9):
            peer.sync_once(force=True)
        self.assertIn('429', peer.status()['error'])
        self.assertLessEqual(len(host.multiplayer.host.rates), 5)

    def test_pair_room_mutual_exclusion_and_legacy_direct_still_works(self):
        host, _ = self.host()
        with self.assertRaises(ValueError):
            host.perform('direct_host', {'host': '127.0.0.1', 'port': 0, 'name': 'Bad', 'game': 'Ultra Sun 1.0'})
        with self.assertRaises(ValueError):
            host.perform('room_new_run', {'game': 'Ultra Sun 1.0'})
        host.perform('leave')
        status = host.perform('direct_host', {'host': '127.0.0.1', 'port': 0, 'name': 'Legacy', 'game': 'Ultra Sun 1.0'})
        with self.assertRaises(ValueError):
            host.perform('room_host', {'host': '127.0.0.1', 'port': 0, 'name': 'Bad', 'game': 'Ultra Sun 1.0'})
        peer = self.app(1)
        peer.perform('direct_join', {'invite_code': status['invite_link'], 'name': 'Legacy peer', 'game': 'Ultra Sun 1.0'})
        host.sync_once(force=True)
        self.assertEqual(host.status()['partner']['name'], 'Legacy peer')
        self.assertNotIn('room', host.status())


if __name__ == '__main__':
    unittest.main()
