"""All supported games use the same private companion transports."""
import json
import tempfile
import unittest
from pathlib import Path
from companion.snapshot import snapshot, viewer_state
from companion.sync import CompanionSync
from companion.direct import identity, partner
from tracker.profiles import PROFILES
from tests.test_companion import Service, state

class CompanionGameTests(unittest.TestCase):
    def test_all_supported_games_share_and_restore_generation_boundaries(self):
        for game, profile in PROFILES.items():
            with self.subTest(game=game):
                current = state(game)
                last = 31 if profile.generation == 6 else 32
                highest = 721 if profile.generation == 6 else 807
                current['party'][0]['species_id'] = highest
                current['boxes'] = {str(n): [None] * 30 for n in range(1, last + 1)}
                result = snapshot(current)
                self.assertEqual(result['party'][0]['species_id'], highest)
                self.assertEqual(len(viewer_state(result)['boxes']), last)
                self.assertNotIn('NEVER_SEND', json.dumps(result))
                current['boxes'][str(last + 1)] = [None] * 30
                with self.assertRaises(ValueError): snapshot(current)
                del current['boxes'][str(last + 1)]
                current['party'][0]['species_id'] = highest + 1
                with self.assertRaises(ValueError): snapshot(current)

    def test_all_supported_games_can_configure_cloud_transport(self):
        for game in PROFILES:
            with self.subTest(game=game), tempfile.TemporaryDirectory() as directory:
                calls = []
                def transport(url, method='GET', payload=None, **kwargs):
                    calls.append(payload)
                    return {'pair_id':'test', 'token':'private-token', 'invite_code':'a'*32}
                sync = CompanionSync(Service(), directory, transport)
                self.addCleanup(sync.close)
                result = sync.perform('create', {'name':'Jugador', 'game':game, 'setup_key':'test-setup-key-long-enough'})
                self.assertTrue(result['configured'])
                self.assertEqual(calls[-1]['game'], game)
                self.assertNotIn('private-token', json.dumps(result))

    def test_gen6_and_gen7_peers_exchange_sanitized_full_pc(self):
        for game, profile in PROFILES.items():
            with self.subTest(game=game), tempfile.TemporaryDirectory() as directory:
                own, other = Service(), Service()
                own.current = state(game)
                count = 31 if profile.generation == 6 else 32
                own.current['boxes'] = {str(n): [None]*30 for n in range(1,count+1)}
                own.current['boxes'][str(count)][0] = dict(own.current['party'][0], nickname='Ultima caja')
                host = CompanionSync(own, Path(directory)/'host')
                peer = CompanionSync(other, Path(directory)/'peer')
                try:
                    opened = host.perform('direct_host', {'host':'127.0.0.1','port':0,'name':'Host','game':game})
                    joined = peer.perform('direct_join', {'invite_code':opened['invite_code'], 'name':'Peer', 'game':other.current['game']})
                    remote = joined['partner']['state']
                    self.assertEqual(remote['game'], game)
                    self.assertEqual(remote['boxes'][str(count)][0]['nickname'], 'Ultima caja')
                    self.assertNotIn('NEVER_SEND', json.dumps(remote))
                    host.sync_once()
                    self.assertEqual(host.status()['partner']['state']['game'], other.current['game'])
                finally:
                    peer.close()
                    host.close()

    def test_unknown_games_and_mismatched_member_game_still_rejected(self):
        for game in ('Unknown', None, [], {}):
            with self.subTest(game=game), self.assertRaises(ValueError): identity('Jugador', game)
            with self.subTest(game=game), self.assertRaises(ValueError): snapshot(state(game))
            with self.subTest(game=game), self.assertRaises(ValueError): viewer_state({'schema_version':1,'game':game})
        with self.assertRaises(ValueError): snapshot(state('Unknown'))
        with self.assertRaises(ValueError): viewer_state({'schema_version':1, 'game':'Unknown'})
        shared = snapshot(state())
        with self.assertRaises(ValueError):
            partner({'name':'Jugador','game':'Pokémon X 1.0','state':shared,'updated_at':1})
