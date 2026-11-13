"""Room invariants independent of a transport or a running emulator."""
import copy
import json
import tempfile
import unittest
import uuid
from pathlib import Path

from companion.room import INVITE_SECONDS, MAX_EVENTS, MAX_SEQUENCE, Room, room_view
from companion.room_storage import RoomStorage
from companion.snapshot import snapshot
from tests.test_companion import state


def person(name='Sol', game='Ultra Sun 1.0'):
    return {'player_id': str(uuid.uuid4()), 'run_id': str(uuid.uuid4()), 'name': name, 'game': game}


class RoomTests(unittest.TestCase):
    def setUp(self):
        self.now = 100.0
        self.host = person()
        self.room = Room(self.host, 4, lambda: self.now)

    def join(self, room=None, member=None):
        room = room or self.room
        member = member or person('Luna')
        reply = room.join(room.invite(), {'protocol': 2, **member})
        return member, reply['token']

    def update(self, member, seq, value, **extra):
        return self.room.exchange(member['player_id'], {
            'protocol': 2, 'session_id': self.room.session_id, 'epoch': self.room.epoch,
            'run_id': member['run_id'], 'sequence': seq, 'state': value, **extra})

    def test_two_three_four_players_capacity_and_no_identity_reuse(self):
        for capacity in (2, 3, 4):
            with self.subTest(capacity=capacity):
                room = Room(person(), capacity)
                peers = [self.join(room) for _ in range(capacity - 1)]
                self.assertEqual(len(room.view()['members']), capacity)
                with self.assertRaises(ValueError):
                    room.invite()
                removed, token = peers[0]
                room.remove(removed['player_id'])
                with self.assertRaises(ValueError):
                    room.authenticate(token)
                fresh, _ = self.join(room)
                self.assertNotEqual(fresh['player_id'], removed['player_id'])
                self.assertNotIn(removed['player_id'], [m['player_id'] for m in room.view()['members']])

    def test_invalid_capacity_identity_game_and_duplicate_member(self):
        for capacity in (True, 1, 5, '4'):
            with self.subTest(capacity=capacity), self.assertRaises(ValueError):
                Room(person(), capacity)
        for fields in ({'name': '<script>'}, {'name': ''}, {'game': 'Unknown'},
                       {'player_id': 'arbitrary'}, {'run_id': None}):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                Room({**person(), **fields}, 4)
        peer, _ = self.join()
        invitation = self.room.invite()
        with self.assertRaises(ValueError):
            self.room.join(invitation, {'protocol': 2, **peer})
        self.assertEqual(len(self.room.members), 2)

    def test_state_copies_and_wrong_game_never_overwrite_a_member(self):
        peer, _ = self.join()
        value = snapshot(state())
        self.update(peer, 1, value)
        value['progress']['missed_routes'].append('99')
        self.assertEqual(self.room.members[peer['player_id']]['state']['progress']['missed_routes'], ['10'])
        with self.assertRaises(ValueError):
            self.update(peer, 2, snapshot(state('Ultra Moon 1.0')))
        self.assertEqual(self.room.members[peer['player_id']]['sequence'], 1)
        view = self.room.view()
        view['members'][1]['state']['party'][0]['nickname'] = 'Changed'
        self.assertEqual(self.room.members[peer['player_id']]['state']['party'][0]['nickname'], 'Goty')

    def test_invitation_expiry_consumption_revocation_and_wrong_protocol(self):
        invite = self.room.invite()
        self.now += INVITE_SECONDS
        with self.assertRaises(ValueError):
            self.room.join(invite, {'protocol': 2, **person()})
        invite = self.room.invite()
        with self.assertRaises(ValueError):
            self.room.join(invite, {'protocol': 1, **person()})
        token = self.room.join(invite, {'protocol': 2, **person()})['token']
        self.assertTrue(self.room.authenticate(token))
        with self.assertRaises(ValueError):
            self.room.join(invite, {'protocol': 2, **person()})
        invite = self.room.invite()
        self.room.revoke_invites()
        with self.assertRaises(ValueError):
            self.room.join(invite, {'protocol': 2, **person()})

    def test_duplicates_old_messages_isolation_and_allowlist(self):
        peer, _ = self.join()
        value = snapshot(state())
        self.update(peer, 1, value)
        revision = self.room.revision
        self.update(peer, 1, value)
        self.assertEqual(self.room.revision, revision)
        for fields in ({'sequence': 0}, {'run_id': str(uuid.uuid4())},
                       {'session_id': str(uuid.uuid4())}, {'epoch': str(uuid.uuid4())},
                       {'protocol': 1}, {'sequence': True}, {'sequence': MAX_SEQUENCE + 1}):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                self.update(peer, 1, value, **fields)
        changed = copy.deepcopy(value)
        changed['party'][0]['nickname'] = 'Cambio'
        with self.assertRaises(ValueError):
            self.update(peer, 1, changed)
        self.assertEqual(self.room.members[peer['player_id']]['state']['party'][0]['nickname'], 'Goty')
        value['secret'] = 'DO_NOT_SHARE'
        result = self.update(peer, 2, value)
        self.assertNotIn('DO_NOT_SHARE', json.dumps(result))
        self.assertNotIn('token', json.dumps(result))

    def test_disconnect_retains_snapshot_and_reconnect_rotates_credentials(self):
        peer, old_token = self.join()
        self.update(peer, 1, snapshot(state()))
        self.now += 20
        self.assertFalse(self.room.view()['members'][1]['online'])
        result = self.update(peer, 2, None)
        self.assertTrue(result['members'][1]['online'])
        self.assertFalse(result['members'][1]['source_live'])
        self.assertIsNotNone(result['members'][1]['state'])
        invite = self.room.invite(peer['player_id'])
        wrong = {**peer, 'run_id': str(uuid.uuid4())}
        with self.assertRaises(ValueError):
            self.room.join(invite, {'protocol': 2, **wrong})
        token = self.room.join(invite, {'protocol': 2, **peer})['token']
        with self.assertRaises(ValueError):
            self.room.authenticate(old_token)
        self.assertEqual(self.room.authenticate(token), peer['player_id'])
        self.update(peer, 1, snapshot(state()))
        self.room.leave(peer['player_id'])
        with self.assertRaises(ValueError):
            self.room.authenticate(token)
        self.assertTrue(self.room.view()['members'][1]['left'])

    def test_death_revival_missed_routes_baseline_and_bounded_events(self):
        peer, _ = self.join()
        value = snapshot(state())
        self.update(peer, 1, value)
        self.assertEqual([e['kind'] for e in self.room.events], ['joined', 'joined'])
        value['progress']['deaths'] = {}
        self.update(peer, 2, value)
        self.assertEqual(self.room.events[-1]['kind'], 'revived')
        value['progress']['deaths'] = snapshot(state())['progress']['deaths']
        value['progress']['deaths']['33:1234']['source'] = 'soullink-response'
        value['progress']['missed_routes'].append('12')
        self.update(peer, 3, value)
        self.assertEqual(self.room.events[-2]['kind'], 'death')
        self.assertTrue(self.room.events[-2]['response'])
        self.assertEqual(self.room.events[-1]['route'], '12')
        for seq in range(4, 210):
            value['progress']['deaths'] = {} if seq % 2 else snapshot(state())['progress']['deaths']
            self.update(peer, seq, value)
        self.assertEqual(len(self.room.events), MAX_EVENTS)
        self.assertEqual(room_view(self.room.view()), self.room.view())

    def test_aggregate_validation_and_offline_state(self):
        peer, _ = self.join()
        self.update(peer, 1, snapshot(state()))
        view = self.room.view()
        clean = room_view(view, offline=True)
        self.assertTrue(all(not m['online'] and not m['source_live'] for m in clean['members']))
        for mutation in (lambda x: x.update(protocol=True), lambda x: x.update(capacity=5),
                         lambda x: x['members'].append(x['members'][0]),
                         lambda x: x.update(host_id=str(uuid.uuid4())),
                         lambda x: x['events'].reverse(),
                         lambda x: x['members'][1].update(game='Pokemon X 1.5')):
            invalid = copy.deepcopy(view)
            mutation(invalid)
            with self.assertRaises(ValueError):
                room_view(invalid)


class RoomStorageTests(unittest.TestCase):
    def test_restart_identity_new_run_and_credential_free_cache(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root)
            old = directory / 'companion-credentials.json'
            old.write_text('{"token":"legacy-token"}', encoding='utf-8')
            storage = RoomStorage(directory)
            host = storage.identity('Sol', 'Ultra Sun 1.0')
            room = Room(host, 4)
            room.invite()
            storage.cache(room.view())
            restored = RoomStorage(directory)
            self.assertEqual(restored.identity('Sol', 'Ultra Sun 1.0'), host)
            self.assertFalse(restored.data['room']['members'][0]['online'])
            self.assertNotIn('token', storage.path.read_text(encoding='utf-8'))
            self.assertEqual(json.loads(old.read_text())['token'], 'legacy-token')
            restored.new_run(host['game'])
            fresh = restored.identity('Sol', host['game'])
            self.assertEqual(fresh['player_id'], host['player_id'])
            self.assertNotEqual(fresh['run_id'], host['run_id'])
            self.assertIsNone(restored.data['room'])

    def test_corrupt_future_files_are_preserved_and_never_silently_reset(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'companion-multiplayer.json'
            for content in ('{', '{"version":2}', '{"version":true}'):
                path.write_text(content, encoding='utf-8')
                storage = RoomStorage(Path(root))
                self.assertTrue(storage.error)
                with self.assertRaises(ValueError):
                    storage.identity('Sol', 'Ultra Sun 1.0')
                self.assertEqual(path.read_text(encoding='utf-8'), content)


if __name__ == '__main__':
    unittest.main()
