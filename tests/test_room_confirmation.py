"""Authenticated local API rejects room confirmations bound to another run."""
import copy
from contextlib import closing
import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path

from companion.sync import CompanionSync
from server import TrackerHTTPServer, make_handler
from tracker.demo import DemoService


class RoomConfirmationTests(unittest.TestCase):
    def test_http_confirmation_requires_current_room_run_link_and_remote_death(self):
        with tempfile.TemporaryDirectory() as root:
            services = [DemoService(Path(root)/str(i)/'state.json') for i in (0, 1)]
            apps = [CompanionSync(s, Path(root)/str(i)) for i, s in enumerate(services)]
            for app in apps:
                self.addCleanup(app.close)
            status = apps[0].perform('room_host', {'host': '127.0.0.1', 'port': 0,
                        'capacity': 2, 'name': 'Host', 'game': 'Ultra Moon 1.0'})
            apps[1].perform('room_join', {'invite_code': status['invite_link'], 'name': 'Peer', 'game': 'Ultra Moon 1.0'})
            for app in apps:
                app.perform('room_link', {'route': 'alola:8', 'pokemon_key': '33:1000'})
            services[1].mark_dead({'key': '33:1000'})
            apps[1].sync_once(force=True)
            apps[0].sync_once(force=True)
            view = apps[0].status()['room']
            context = {'session_id': view['session_id'], 'epoch': view['epoch'],
                       'local_run_id': apps[0].multiplayer.person['run_id'],
                       'player_id': view['members'][1]['player_id'], 'run_id': view['members'][1]['run_id'],
                       'route': 'alola:8', 'pokemon_key': '33:1000',
                       'recorded_at': view['members'][1]['state']['progress']['deaths']['33:1000']['recorded_at']}
            server = TrackerHTTPServer(('127.0.0.1', 0), make_handler(services[0], 'local-csrf', apps[0]))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            def close_server():
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)
            self.addCleanup(close_server)
            def command(binding, key='33:1000', csrf='local-csrf'):
                with closing(http.client.HTTPConnection(*server.server_address, timeout=3)) as conn:
                    conn.request('POST', '/api/command', json.dumps({'action': 'mark_dead', 'key': key,
                        'source': 'soullink-response', 'soullink_room': binding}),
                        {'Content-Type': 'application/json', 'X-Tracker-Token': csrf})
                    response = conn.getresponse()
                    response.read()
                    return response.status
            self.assertEqual(command(context, csrf='wrong'), 403)
            for field in ('session_id', 'epoch', 'local_run_id', 'player_id', 'run_id', 'recorded_at'):
                wrong = copy.deepcopy(context)
                wrong[field] = 'another-value'
                with self.subTest(field=field):
                    self.assertEqual(command(wrong), 400)
                    self.assertTrue(services[0].commands.empty())
            self.assertEqual(command(context, key='33:1001'), 400)
            self.assertEqual(command(context), 202)
            queued = services[0].commands.get_nowait()
            self.assertEqual(queued['key'], '33:1000')
            self.assertEqual(queued['source'], 'soullink-response')
            self.assertNotIn('33:1000', services[0].snapshot()['progress']['deaths'])
            services[1].revive({'key': '33:1000'})
            apps[1].sync_once(force=True)
            apps[0].sync_once(force=True)
            self.assertEqual(command(context), 400)
            apps[0].perform('leave')
            self.assertEqual(command(context), 400)
            self.assertTrue(services[0].commands.empty())


if __name__ == '__main__':
    unittest.main()
