"""Soul Link v3 contract: common admission, individual credentials and private views."""
import copy
import json
import unittest
import uuid

from companion.soul_room import FEATURES, SoulRoom, soul_from_snapshot, soul_view
from companion.snapshot import snapshot
from tests.test_companion import mon, state


def person(name='Anfitrión'):
    return {'player_id': str(uuid.uuid4()), 'run_id': str(uuid.uuid4()),
            'name': name, 'game': 'Ultra Sun 1.0'}


def private_fixture():
    value = state()
    value['progress']['deaths'] = {}
    value['party'][0].update(nickname='PRIVATE_NICK_7c19', ability='PRIVATE_ABILITY_7c19',
                             item='PRIVATE_ITEM_7c19')
    value['boxes']['1'][0] = {**mon(), 'encryption_constant': 5678,
                              'nickname': 'UNSELECTED_BOX_7c19'}
    return snapshot(value)


class SoulRoomTests(unittest.TestCase):
    def setUp(self):
        self.now = 100.0
        self.owner = person()
        self.room = SoulRoom(self.owner, clock=lambda: self.now)
        self.invitation = self.room.invite()

    def join(self, name='Invitado', room=None, invitation=None, identity=None):
        room = room or self.room
        identity = identity or person(name)
        answer = room.join(invitation or self.invitation,
                           {'protocol': 3, 'features': FEATURES, **identity})
        return identity, answer['token']

    def exchange(self, identity, seq=1, *, sharing=False, current=None,
                 selected=None, soul=None, **fields):
        selected = {} if selected is None else selected
        source = private_fixture() if current is None else current
        data = {'protocol': 3, 'session_id': self.room.session_id, 'epoch': self.room.epoch,
                'run_id': identity['run_id'], 'sequence': seq, 'sharing': sharing,
                'source_live': True, 'state': source if sharing else None,
                'links': selected, 'soul': soul if soul is not None else soul_from_snapshot(source, selected),
                **fields}
        return self.room.exchange(identity['player_id'], data)

    def test_one_host_then_exact_same_invite_joins_three_and_fifth_is_rejected(self):
        self.assertEqual(self.room.view()['capacity'], 4)
        self.assertEqual(len(self.room.view()['members']), 1)
        peers = [self.join(str(i)) for i in range(3)]
        self.assertEqual(len(self.room.view()['members']), 4)
        self.assertEqual(len({token for _, token in peers}), 3)
        self.assertNotIn(self.invitation, {token for _, token in peers})
        for identity, token in peers:
            self.assertEqual(self.room.authenticate(token), identity['player_id'])
        with self.assertRaises(ValueError):
            self.join('Quinto')
        self.assertEqual(len(self.room.view()['members']), 4)

    def test_common_invitation_revocation_rotation_and_join_do_not_revoke_members(self):
        first, token = self.join()
        self.room.revoke_invites()
        with self.assertRaises(ValueError):
            self.join('Después de revocar')
        self.assertEqual(self.room.authenticate(token), first['player_id'])
        fresh = self.room.invite()
        self.assertNotEqual(fresh, self.invitation)
        with self.assertRaises(ValueError):
            self.join('Enlace antiguo')
        self.join('Nuevo', invitation=fresh)
        self.join('Mismo nuevo', invitation=fresh)
        self.assertEqual(len(self.room.view()['members']), 4)

    def test_admission_secret_is_not_resume_authority_or_another_rooms_invitation(self):
        peer, token = self.join()
        other = SoulRoom(person('Otra sala'), clock=lambda: self.now)
        with self.assertRaises(ValueError):
            other.join(self.invitation, {'protocol': 3, 'features': FEATURES, **person('Intruso')})
        self.assertEqual(len(other.view()['members']), 1)
        resume = {'protocol': 3, 'features': FEATURES, 'session_id': self.room.session_id,
                  'epoch': self.room.epoch, **peer}
        with self.assertRaises(ValueError):
            self.room.resume(self.invitation, resume)
        self.assertEqual(self.room.authenticate(token), peer['player_id'])
        with self.assertRaises(ValueError):
            self.room.join(self.invitation, {'protocol': 2, 'features': FEATURES, **person('Antiguo')})
        with self.assertRaises(ValueError):
            self.room.join(self.invitation, {'protocol': 3, 'features': [], **person('Incompatible')})
        self.join('Compatible')

    def test_privacy_defaults_off_full_private_input_is_rejected_before_mutation(self):
        peer, _ = self.join()
        view = self.room.view()
        self.assertTrue(all(m['sharing'] is False and m['state'] is None for m in view['members']))
        before = copy.deepcopy(view)
        with self.assertRaises(ValueError):
            self.exchange(peer, state=private_fixture())
        self.assertEqual(self.room.view(), before)
        public = self.exchange(peer, sharing=True)
        self.assertEqual(public['members'][1]['state']['party'][0]['nickname'], 'PRIVATE_NICK_7c19')
        private = self.exchange(peer, 2, sharing=False)
        self.assertFalse(private['members'][1]['sharing'])
        self.assertIsNone(private['members'][1]['state'])
        for marker in ('PRIVATE_NICK_7c19', 'PRIVATE_ABILITY_7c19', 'PRIVATE_ITEM_7c19', 'UNSELECTED_BOX_7c19'):
            self.assertNotIn(marker, json.dumps(private))

    def test_each_authenticated_member_controls_only_own_visibility(self):
        peers = [self.join(str(i)) for i in range(3)]
        for identity, _ in peers:
            self.exchange(identity, sharing=True)
        self.exchange(self.owner, sharing=True)
        for identity in [self.owner, *(p[0] for p in peers)]:
            self.exchange(identity, 2, sharing=False)
            view = self.room.view()
            own = next(m for m in view['members'] if m['player_id'] == identity['player_id'])
            self.assertFalse(own['sharing'])
            self.assertIsNone(own['state'])
        # Claimed player_id is never authority over another player's entry.
        self.exchange(peers[0][0], 3, sharing=True, player_id=self.owner['player_id'])
        view = self.room.view()
        self.assertFalse(view['members'][0]['sharing'])
        self.assertIsNone(view['members'][0]['state'])
        self.assertTrue(view['members'][1]['sharing'])

    def test_minimal_linked_capture_death_and_revival_work_without_full_view(self):
        peer, _ = self.join()
        selected = {'alola:8': '33:1234'}
        value = private_fixture()
        first = self.exchange(peer, selected=selected, current=value)
        record = first['members'][1]['soul']['captures']['alola:8']
        self.assertEqual(record['key'], '33:1234')
        self.assertEqual(record['status'], 'alive')
        self.assertEqual(set(record['pokemon']), {'species_id', 'origin_version', 'encryption_constant', 'met_location_id'})
        value['progress']['deaths']['33:1234'] = {'pokemon': value['party'][0], 'recorded_at': '2026-11-13T01:00:00'}
        dead = self.exchange(peer, 2, selected=selected, current=value)
        record = dead['members'][1]['soul']['captures']['alola:8']
        self.assertEqual(record['status'], 'dead')
        self.assertEqual(record['death_at'], '2026-11-13T01:00:00')
        self.assertFalse(record['response'])
        self.assertIsNone(dead['members'][1]['state'])
        value['progress']['deaths'] = {}
        revived = self.exchange(peer, 3, selected=selected, current=value)
        self.assertEqual(revived['members'][1]['soul']['captures']['alola:8']['status'], 'alive')
        self.assertIsNone(revived['members'][1]['state'])
        self.assertNotIn('UNSELECTED_BOX_7c19', json.dumps(revived))

    def test_disconnect_reserves_identity_resume_requires_token_and_rotates_it(self):
        peer, token = self.join()
        self.exchange(peer, sharing=True)
        self.now += 21
        view = self.room.view()
        self.assertFalse(view['members'][1]['online'])
        self.assertIsNone(view['members'][1]['state'])
        self.assertEqual(len(view['members']), 2)
        with self.assertRaises(ValueError):
            self.join(identity=peer)
        resume = {'protocol': 3, 'features': FEATURES, 'session_id': self.room.session_id,
                  'epoch': self.room.epoch, **peer}
        with self.assertRaises(ValueError):
            self.room.resume('x' * 43, resume)
        for fields in ({'player_id': str(uuid.uuid4())}, {'run_id': str(uuid.uuid4())}, {'game': 'Ultra Moon 1.0'}):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                self.room.resume(token, {**resume, **fields})
        reply = self.room.resume(token, resume)
        self.assertNotEqual(reply['token'], token)
        self.assertEqual(self.room.authenticate(reply['token']), peer['player_id'])
        with self.assertRaises(ValueError):
            self.room.authenticate(token)
        resumed = next(m for m in self.room.view()['members'] if m['player_id'] == peer['player_id'])
        self.assertFalse(resumed['sharing'])
        self.assertIsNone(resumed['state'])

    def test_voluntary_leave_frees_slot_without_identity_inheritance(self):
        peers = [self.join(str(i)) for i in range(3)]
        departed, token = peers[1]
        self.room.leave(departed['player_id'])
        self.assertEqual(len(self.room.view()['members']), 3)
        with self.assertRaises(ValueError):
            self.room.authenticate(token)
        with self.assertRaises(ValueError):
            self.join(identity=departed)  # The common link cannot revive a retired identity.
        fresh, _ = self.join('Sustituto')
        self.assertNotEqual(fresh['player_id'], departed['player_id'])
        self.assertNotEqual(fresh['run_id'], departed['run_id'])
        self.assertEqual(len(self.room.view()['members']), 4)

    def test_sequence_room_run_protocol_and_payload_validation_are_atomic(self):
        peer, _ = self.join()
        self.exchange(peer)
        before = copy.deepcopy(self.room.view())
        self.exchange(peer)  # Identical sequence is idempotent.
        self.assertEqual(self.room.view(), before)
        for fields in ({'sequence': 0}, {'sequence': True}, {'sequence': 2**53},
                       {'protocol': 2}, {'session_id': str(uuid.uuid4())},
                       {'epoch': str(uuid.uuid4())}, {'run_id': str(uuid.uuid4())},
                       {'sharing': 'true'}, {'sharing': True}):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                self.exchange(peer, **fields)
            self.assertEqual(self.room.view(), before)
        malformed = {'captures': {'alola:8': {'key': '33:1234', 'pokemon': {'nickname': 'LEAK'}}}, 'missed_routes': []}
        with self.assertRaises(ValueError):
            self.exchange(peer, 2, soul=malformed, selected={'alola:8': '33:1234'})
        self.assertEqual(self.room.view(), before)

    def test_full_view_lease_expires_and_untrusted_private_responses_fail_closed(self):
        peer, _ = self.join()
        view = self.exchange(peer, sharing=True)
        self.assertGreater(view['members'][1]['view_ttl_ms'], 0)
        self.assertLessEqual(view['members'][1]['view_ttl_ms'], 12000)
        self.now += 11
        replay = self.exchange(peer, sharing=True)
        self.assertLessEqual(replay['members'][1]['view_ttl_ms'], 1000,
                             'An identical old message cannot renew a full-view lease')
        self.now += 2
        expired = self.room.view()
        self.assertIsNone(expired['members'][1]['state'])
        self.assertEqual(expired['members'][1]['view_ttl_ms'], 0)
        offline = soul_view(view, offline=True)
        self.assertTrue(all(m['state'] is None and m['view_ttl_ms'] == 0 for m in offline['members']))
        invalid = copy.deepcopy(view)
        invalid['members'][1]['sharing'] = False
        with self.assertRaises(ValueError):
            soul_view(invalid)

    def test_connected_member_with_stale_source_keeps_permission_but_not_full_view(self):
        peer, _ = self.join()
        self.exchange(peer, sharing=True)
        result = self.exchange(peer, 2, sharing=True, state=None, source_live=False)
        member = result['members'][1]
        self.assertTrue(member['online'])
        self.assertTrue(member['sharing'])
        self.assertFalse(member['source_live'])
        self.assertIsNone(member['state'])
        self.assertEqual(member['view_ttl_ms'], 0)

    def test_minimal_events_validate_capture_route_identity_and_strip_extra_fields(self):
        peer, _ = self.join()
        chosen = {'alola:8': '33:1234'}
        good = soul_from_snapshot(private_fixture(), chosen)
        for field, bad in (('species_id', 9999), ('origin_version', 24),
                           ('encryption_constant', 5678), ('met_location_id', 112)):
            invalid = copy.deepcopy(good)
            invalid['captures']['alola:8']['pokemon'][field] = bad
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.exchange(peer, soul=invalid, selected=chosen)
        for field, bad in (('status', 'inventado'), ('death_at', '<script>'), ('response', 'false')):
            invalid = copy.deepcopy(good)
            invalid['captures']['alola:8'][field] = bad
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.exchange(peer, soul=invalid, selected=chosen)
        invalid = copy.deepcopy(good)
        invalid['missed_routes'] = ['alola:112']
        with self.assertRaises(ValueError):
            self.exchange(peer, soul=invalid, selected=chosen)
        expanded = copy.deepcopy(good)
        expanded['captures']['alola:8']['pokemon']['nickname'] = 'STRIP_THIS_EXTRA'
        expanded['captures']['alola:8']['private_box'] = 'STRIP_THIS_EXTRA'
        result = self.exchange(peer, soul=expanded, selected=chosen)
        self.assertNotIn('STRIP_THIS_EXTRA', json.dumps(result))


if __name__ == '__main__':
    unittest.main()
