import copy
import tempfile
import unittest
from pathlib import Path

from companion.room import Room, room_view
from companion.room_links import captures, links, routes
from companion.sync import CompanionSync
from companion.snapshot import snapshot
from tests.test_companion import Service, mon, state
from tests.test_multiplayer_room import person


class CaptureLinkTests(unittest.TestCase):
    def test_catalog_aliases_party_boxes_death_trade_and_origin_isolation(self):
        game = 'Ultra Sun 1.0'
        value = snapshot(state())
        index = captures(game, value)
        self.assertEqual(index['alola:8'], {'33:1234'})  # Party/box/death deduplicate.
        value['party'] = [None] * 6
        value['boxes'] = {}
        self.assertEqual(captures(game, value)['alola:8'], {'33:1234'})
        value['progress']['deaths'] = {}
        value['progress']['route_marks'] = {'33:1234': {'kind': 'trade', 'pokemon': mon()}}
        self.assertEqual(captures(game, value)['alola:8'], {'33:1234'})
        value['progress']['origins']['33:1234'] = 'gift'
        self.assertEqual(captures(game, value), {})
        value['progress']['origins'] = {}
        value['progress']['route_marks']['33:1234']['pokemon']['origin_version'] = 24
        self.assertEqual(captures(game, value), {})
        # The backend uses every actual alias in each shipped catalog.
        for game in ('Ultra Sun 1.0', 'Pokémon X 1.0', 'Omega Ruby 1.0'):
            for alias, canonical in routes(game).items():
                self.assertEqual(routes(game)[canonical], canonical)
                self.assertIsInstance(alias, int)

    def test_only_own_capture_can_be_selected_and_later_absence_keeps_choice(self):
        host = person()
        room = Room(host, 4)
        base = {'protocol': 2, 'session_id': room.session_id, 'epoch': room.epoch,
                'run_id': host['run_id']}
        value = snapshot(state())
        def exchange(seq, choice, current=value):
            return room.exchange(host['player_id'], {**base, 'sequence': seq, 'state': current, 'links': choice})
        for choice in ({'alola:8': '33:9999'}, {'xy:8': '33:1234'}, {'alola:99999': '33:1234'}):
            with self.subTest(choice=choice), self.assertRaises(ValueError):
                exchange(1, choice)
        result = exchange(1, {'alola:8': '33:1234'})
        self.assertEqual(result['members'][0]['links'], {'alola:8': '33:1234'})
        with self.assertRaises(ValueError):
            exchange(1, {})  # Same sequence with another link is not idempotent.
        absent = copy.deepcopy(value)
        absent['party'] = [None]*6
        absent['boxes'] = {}
        absent['progress']['deaths'] = {}
        result = exchange(2, {'alola:8': '33:1234'}, absent)
        self.assertEqual(room_view(result)['members'][0]['links'], {'alola:8': '33:1234'})
        self.assertEqual(exchange(3, {}, absent)['members'][0]['links'], {})
        for bad in ([], {'alola:8': '<markup>'}, {'alola:8': True}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                links(bad, host['game'])

    def test_four_members_share_own_links_without_mutating_local_progress(self):
        with tempfile.TemporaryDirectory() as directory:
            services = [Service() for _ in range(4)]
            apps = [CompanionSync(s, Path(directory)/str(i)) for i, s in enumerate(services)]
            for app in apps:
                self.addCleanup(app.close)
            apps[0].perform('room_host', {'host': '127.0.0.1', 'port': 0,
                                         'capacity': 4, 'name': 'Host', 'game': 'Ultra Sun 1.0'})
            for i in range(1, 4):
                invitation = apps[0].status()['invite_link'] or apps[0].perform('room_invite')['invite_link']
                apps[i].perform('room_join', {'invite_code': invitation, 'name': str(i), 'game': 'Ultra Sun 1.0'})
            saved = [copy.deepcopy(s.current) for s in services]
            for app in apps:
                app.perform('room_link', {'route': 'alola:8', 'pokemon_key': '33:1234'})
            apps[1].sync_once(force=True)
            self.assertTrue(all(m['links'] == {'alola:8': '33:1234'} for m in apps[1].status()['room']['members']))
            apps[2].perform('room_link', {'route': 'alola:8', 'pokemon_key': None})
            apps[0].sync_once(force=True)
            self.assertEqual(apps[0].status()['room']['members'][2]['links'], {})
            self.assertEqual([s.current for s in services], saved)


if __name__ == '__main__':
    unittest.main()
