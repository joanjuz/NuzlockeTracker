"""Real authenticated local API: private Soul Link events still require a bound explicit command."""
import copy
import http.client
import json
import tempfile
import threading
import unittest
from contextlib import closing
from pathlib import Path

from companion.sync import CompanionSync
from server import TrackerHTTPServer, make_handler
from tracker.demo import DemoService


class PrivateSoulConfirmationTests(unittest.TestCase):
    def test_private_death_confirmation_binds_room_runs_capture_and_timestamp(self):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        services = [DemoService(Path(directory)/str(i)/'state.json') for i in (0, 1)]
        apps = [CompanionSync(s, Path(directory)/str(i)) for i, s in enumerate(services)]
        for app in apps:
            self.addCleanup(app.close)
        status = apps[0].perform('soul_host', {'host': '127.0.0.1', 'port': 0,
                                 'name': 'Host', 'game': 'Ultra Moon 1.0'})
        apps[1].perform('soul_join', {'invite_code': status['invite_link'],
                                     'name': 'Peer', 'game': 'Ultra Moon 1.0'})
        for app in apps:
            app.perform('soul_link', {'route': 'alola:8', 'pokemon_key': '33:1000'})
        before = copy.deepcopy(services[0].snapshot()['progress'])
        services[1].mark_dead({'key': '33:1000'})
        apps[1].sync_once(force=True)
        apps[0].sync_once(force=True)
        view = apps[0].status()['room']
        remote = view['members'][1]
        self.assertFalse(remote['sharing'])
        self.assertIsNone(remote['state'])
        self.assertEqual(remote['soul']['captures']['alola:8']['status'], 'dead')
        self.assertEqual(services[0].snapshot()['progress'], before)
        context = {'protocol': 3, 'session_id': view['session_id'], 'epoch': view['epoch'],
                   'local_run_id': apps[0].soul.person['run_id'],
                   'player_id': remote['player_id'], 'run_id': remote['run_id'],
                   'route': 'alola:8', 'pokemon_key': '33:1000',
                   'recorded_at': remote['soul']['captures']['alola:8']['death_at']}
        server = TrackerHTTPServer(('127.0.0.1', 0), make_handler(services[0], 'local-csrf', apps[0]))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        def close_server():
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)
        self.addCleanup(close_server)
        def command(binding, *, key='33:1000', csrf='local-csrf', source='soullink-response'):
            with closing(http.client.HTTPConnection(*server.server_address, timeout=3)) as conn:
                conn.request('POST', '/api/command', json.dumps({'action': 'mark_dead', 'key': key,
                    'source': source, 'soullink_room': binding}),
                    {'Content-Type': 'application/json', 'X-Tracker-Token': csrf})
                response = conn.getresponse()
                response.read()
                return response.status
        self.assertEqual(command(context, csrf='wrong'), 403)
        self.assertEqual(command(context, source='manual'), 400)
        for field in ('session_id', 'epoch', 'local_run_id', 'player_id', 'run_id', 'recorded_at'):
            wrong = {**context, field: 'another-value'}
            with self.subTest(field=field):
                self.assertEqual(command(wrong), 400)
                self.assertTrue(services[0].commands.empty())
        self.assertEqual(command(context, key='33:1001'), 400)
        self.assertEqual(command(context), 202)
        queued = services[0].commands.get_nowait()
        self.assertEqual(queued['key'], '33:1000')
        self.assertEqual(queued['source'], 'soullink-response')
        self.assertEqual(services[0].snapshot()['progress'], before,
                         'Even an accepted HTTP response only queues the explicitly requested local command')
        services[1].revive({'key': '33:1000'})
        apps[1].sync_once(force=True)
        apps[0].sync_once(force=True)
        self.assertEqual(command(context), 400)
        self.assertTrue(services[0].commands.empty())
        apps[0].perform('soul_link', {'route': 'alola:8', 'pokemon_key': None})
        self.assertEqual(command(context), 400)
        apps[0].perform('leave')
        self.assertEqual(command(context), 400)
        self.assertTrue(services[0].commands.empty())


if __name__ == '__main__':
    unittest.main()
