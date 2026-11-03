"""TrackerService.poll() split per generation, exercised with fake readers.

The characterisation tests pin the exact sequence of memory reads and the
published state so the per-generation split cannot change behaviour.
Every fake reader is read-only: there is no write method to call.
"""
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from tracker.battle import BATTLE_START, LENGTH as BATTLE_LENGTH
from tracker.battle_gen6 import candidate_pairs
from tracker.boxes import BOX_SIZE
from tracker.process_memory import DiscoveryCancelled
from tracker.profiles import PROFILES, ULTRA_MOON_10
from tracker.service import TrackerService
from test_gen6_battle import BattleMemory
from test_gen6_boxes import Gen6Memory
from test_gen6_compat import party_fixture
from test_process_memory import party_data

PARTY_LENGTH = 2914


class RecordingGen6Memory(Gen6Memory):
    """Gen6 party + PC (box 1 populated) + optional verified battle roster."""

    def __init__(self, profile, battle=False, overworld=True, **kwargs):
        super().__init__(profile, **kwargs)
        self.battle = BattleMemory(profile.name, hp=11) if battle else None
        self.overworld = overworld
        self.calls = []

    def read(self, address, length):
        self.calls.append((address, length))
        if (address, length) == (self.profile.party_address, PARTY_LENGTH):
            return self.party if self.overworld else bytes(PARTY_LENGTH)
        if self.battle is not None:
            try:
                return self.battle.read(address, length)
            except ValueError:
                pass
        return super().read(address, length)


class RecordingGen7Memory:
    """USUM party at the profile address; everything else as sparse blocks."""

    def __init__(self, blocks=None, party_address=ULTRA_MOON_10.party_address):
        self.blocks = {party_address: party_data(), **(blocks or {})}
        self.calls = []

    def read(self, address, length):
        self.calls.append((address, length))
        return self.blocks.get(address, bytes(length))

    def close(self):
        pass


def make_service(folder, game, reader):
    service = TrackerService(Path(folder) / 'state.json')
    service.factory = lambda config: reader
    service.config = {'game': game, 'mode': 'memory'}
    service.connect()
    reader.calls.clear()
    return service


class Gen6PollCharacterisationTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.profile = PROFILES['Pokémon X 1.0']

    def test_first_poll_reads_party_battle_candidates_then_box_one(self):
        memory = RecordingGen6Memory(self.profile)
        service = make_service(self.folder.name, self.profile.name, memory)
        service.poll()
        battle_bases = [b for b, _ in candidate_pairs(self.profile.name)]
        box = self.profile.box_address
        self.assertEqual(memory.calls, [
            (self.profile.party_address, PARTY_LENGTH),
            # No roster found: each candidate tried once (party shift is 0),
            # then the stored party is not trusted because state was stale.
            (battle_bases[0], 484 * 5 + 366),
            (battle_bases[1], 484 * 5 + 366),
            (box, BOX_SIZE), (box, BOX_SIZE),
        ])
        state = service.snapshot()
        self.assertEqual(state['scan'], {'active': True, 'completed': 1})
        self.assertFalse(state['stale'])
        self.assertFalse(state['battle_hp'])
        self.assertEqual(state['party'][0]['species_id'], 25)

    def test_second_poll_retries_battle_with_last_verified_party(self):
        memory = RecordingGen6Memory(self.profile)
        service = make_service(self.folder.name, self.profile.name, memory)
        service.poll()
        memory.calls.clear()
        service.poll()
        battle_bases = [b for b, _ in candidate_pairs(self.profile.name)]
        roster = 484 * 5 + 366
        box2 = self.profile.box_address + BOX_SIZE
        self.assertEqual(memory.calls, [
            (self.profile.party_address, PARTY_LENGTH),
            (battle_bases[0], roster), (battle_bases[1], roster),
            (battle_bases[0], roster), (battle_bases[1], roster),
            (box2, BOX_SIZE), (box2, BOX_SIZE),
        ])

    def test_full_scan_publishes_and_revision_increments_once_per_poll(self):
        memory = RecordingGen6Memory(self.profile)
        service = make_service(self.folder.name, self.profile.name, memory)
        revisions = []
        for _ in range(31):
            service.poll()
            revisions.append(service.snapshot()['revision'])
        self.assertEqual(revisions, list(range(revisions[0], revisions[0] + 31)))
        state = service.snapshot()
        self.assertTrue(state['box_verified'])
        self.assertEqual(state['scan'], {'active': False, 'completed': 31})
        self.assertEqual(state['connection']['message'],
                         'Gen6 experimental · equipo y 31 cajas PK6 verificadas · PS combate experimental')
        self.assertIsNone(service.gen6_probe)
        # Idle poll after the scan: steady message and no box reads.
        memory.calls.clear()
        service.poll()
        self.assertNotIn((self.profile.box_address, BOX_SIZE), memory.calls)
        self.assertEqual(service.snapshot()['connection']['message'],
                         'Gen6 experimental · equipo y cajas PK6 · PS combate experimental')

    def test_battle_hp_from_overworld_party(self):
        memory = RecordingGen6Memory(self.profile, battle=True)
        service = make_service(self.folder.name, self.profile.name, memory)
        service.poll()
        state = service.snapshot()
        self.assertTrue(state['battle_hp'])
        self.assertEqual(state['party'][0]['hp'], 11)

    def test_missing_overworld_party_uses_last_verified_party_in_battle(self):
        memory = RecordingGen6Memory(self.profile, battle=True)
        service = make_service(self.folder.name, self.profile.name, memory)
        service.poll()
        memory.overworld = False
        memory.battle.current = 4
        service.poll()
        state = service.snapshot()
        self.assertTrue(state['battle_hp'])
        self.assertEqual(state['party'][0]['hp'], 4)

    def test_missing_overworld_party_without_battle_raises(self):
        memory = RecordingGen6Memory(self.profile)
        service = make_service(self.folder.name, self.profile.name, memory)
        memory.overworld = False
        with self.assertRaisesRegex(ValueError, 'temporalmente no disponible.$'):
            service.poll()
        memory.overworld = True
        service.poll()
        memory.overworld = False
        with self.assertRaisesRegex(ValueError, 'esperando regreso'):
            service.poll()


class Gen7PollCharacterisationTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)

    def test_scan_poll_reads_party_battle_twice_then_box(self):
        memory = RecordingGen7Memory()
        service = make_service(self.folder.name, 'Ultra Moon 1.0', memory)
        service.poll()
        box = ULTRA_MOON_10.box_address
        self.assertEqual(memory.calls, [
            (ULTRA_MOON_10.party_address, PARTY_LENGTH),
            (BATTLE_START, BATTLE_LENGTH), (BATTLE_START, BATTLE_LENGTH),
            (box, BOX_SIZE), (box, BOX_SIZE),
        ])
        state = service.snapshot()
        self.assertEqual(state['scan'], {'active': True, 'completed': 1})
        self.assertEqual(state['box_status'], 'pending')
        self.assertEqual(state['connection']['message'], 'Conectado · equipo conectado; verificando cajas')

    def test_full_scan_then_selected_box_refresh(self):
        box1 = party_data()[128:360] + bytes(BOX_SIZE - 232)
        memory = RecordingGen7Memory({ULTRA_MOON_10.box_address: box1})
        service = make_service(self.folder.name, 'Ultra Moon 1.0', memory)
        for _ in range(32):
            service.poll()
        state = service.snapshot()
        self.assertTrue(state['box_verified'])
        self.assertEqual(state['box_status'], 'verified')
        self.assertEqual(state['connection']['message'], 'Conectado · equipo y 32 cajas verificadas')
        self.assertEqual(service.sun_box_base, ULTRA_MOON_10.box_address)
        memory.calls.clear()
        service.poll()
        box = ULTRA_MOON_10.box_address
        self.assertEqual(memory.calls[-2:], [(box, BOX_SIZE), (box, BOX_SIZE)])
        self.assertEqual(service.snapshot()['boxes']['1'][0]['species_id'], 637)

    def test_torn_selected_box_restarts_full_scan(self):
        box1 = party_data()[128:360] + bytes(BOX_SIZE - 232)
        memory = RecordingGen7Memory({ULTRA_MOON_10.box_address: box1})
        service = make_service(self.folder.name, 'Ultra Moon 1.0', memory)
        for _ in range(32):
            service.poll()
        flips = iter([box1, bytes(BOX_SIZE)])
        original = memory.read

        def torn(address, length):
            if address == ULTRA_MOON_10.box_address and length == BOX_SIZE:
                memory.calls.append((address, length))
                return next(flips)
            return original(address, length)

        memory.read = torn
        service.poll()
        state = service.snapshot()
        self.assertFalse(state['box_verified'])
        self.assertEqual(state['box_status'], 'invalid')
        self.assertEqual(state['scan'], {'active': True, 'completed': 0})
        self.assertEqual(service.scan_next, 1)
        self.assertEqual(state['connection']['message'],
                         'Conectado · equipo conectado; cajas pendientes de una lectura válida')

    def test_invalid_party_raises_for_gen7(self):
        memory = RecordingGen7Memory()
        service = make_service(self.folder.name, 'Ultra Moon 1.0', memory)
        memory.blocks[ULTRA_MOON_10.party_address] = b'\1' * PARTY_LENGTH
        with self.assertRaises(ValueError):
            service.poll()


class ExtractedPiecesTests(unittest.TestCase):
    """Each helper extracted from poll(), tested on its own."""

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.service = TrackerService(Path(self.folder.name) / 'state.json')

    def use(self, game, reader):
        self.service.profile = PROFILES[game]
        self.service.reader = reader

    # -- shared --------------------------------------------------------
    def test_cancel_predicate_follows_connection_generation_and_stop(self):
        cancel = self.service._cancel_predicate(self.service.connection_generation)
        self.assertFalse(cancel())
        self.service.connection_generation += 1
        self.assertTrue(cancel())
        cancel = self.service._cancel_predicate(self.service.connection_generation)
        self.service.stop.set()
        self.assertTrue(cancel())

    def test_read_party_gen6_returns_none_on_invalid_data(self):
        self.use('Pokémon X 1.0', RecordingGen6Memory(PROFILES['Pokémon X 1.0']))
        self.assertEqual(self.service._read_party()[0]['species_id'], 25)
        self.service.reader.party = b'\1' * PARTY_LENGTH
        self.assertIsNone(self.service._read_party())

    def test_read_party_gen7_propagates_value_error(self):
        memory = RecordingGen7Memory({ULTRA_MOON_10.party_address: b'\1' * PARTY_LENGTH})
        self.use('Ultra Moon 1.0', memory)
        with self.assertRaises(ValueError):
            self.service._read_party()

    def test_read_party_uses_species_limit_of_generation(self):
        self.use('Pokémon X 1.0', RecordingGen6Memory(PROFILES['Pokémon X 1.0']))
        with patch('tracker.service.decode_party', return_value=[None] * 6) as decode:
            self.service._read_party()
        self.assertEqual(decode.call_args.kwargs, {'max_species': 721})
        self.use('Ultra Moon 1.0', RecordingGen7Memory())
        with patch('tracker.service.decode_party', return_value=[None] * 6) as decode:
            self.service._read_party()
        self.assertEqual(decode.call_args.kwargs, {'max_species': 807})

    # -- Gen6 ----------------------------------------------------------
    def test_gen6_battle_party_requires_previous_party_when_overworld_missing(self):
        self.use('Pokémon X 1.0', RecordingGen6Memory(PROFILES['Pokémon X 1.0']))
        with self.assertRaisesRegex(ValueError, 'temporalmente no disponible.$'):
            self.service._gen6_battle_party(None, {'stale': True, 'party': []})

    def test_gen6_battle_party_prefers_saved_roster_when_overworld_differs(self):
        profile = PROFILES['Pokémon X 1.0']
        memory = RecordingGen6Memory(profile, battle=True)
        self.use(profile.name, memory)
        saved_party = self.service._read_party()
        memory.party = party_fixture(24, species=37, address=profile.party_address)
        other = self.service._read_party()
        party, in_battle = self.service._gen6_battle_party(
            other, {'stale': False, 'party': saved_party})
        self.assertTrue(in_battle)
        self.assertEqual(party[0]['species_id'], 25)
        self.assertEqual(party[0]['hp'], 11)

    def test_gen6_battle_party_keeps_overworld_party_outside_battle(self):
        memory = RecordingGen6Memory(PROFILES['Pokémon X 1.0'])
        self.use('Pokémon X 1.0', memory)
        party = self.service._read_party()
        result, in_battle = self.service._gen6_battle_party(party, {'stale': True})
        self.assertFalse(in_battle)
        self.assertIs(result, party)

    def test_gen6_scan_step_creates_probe_with_party_shift(self):
        profile = PROFILES['Pokémon X 1.0']
        self.use(profile.name, RecordingGen6Memory(profile))
        self.service.profile = replace(profile, party_address=profile.party_address + 0x40)
        self.service.diagnostic = {}
        self.service.scan_next = 1
        changes = self.service._gen6_scan_step({})
        self.assertEqual(changes, {'scan': {'active': True, 'completed': 1}})
        self.assertEqual(self.service.diagnostic['gen6_party_shift'], 0x40)
        self.assertEqual(self.service.gen6_probe.addresses,
                         (profile.box_address, profile.box_address + 0x40))
        self.assertEqual(self.service.scan_next, 2)

    def test_gen6_finish_without_candidate_runs_memory_search_once(self):
        profile = PROFILES['Pokémon Y 1.0']
        self.use(profile.name, RecordingGen6Memory(profile, with_box=False))
        self.service.diagnostic = {}
        found = {str(n): [None] * 30 for n in range(1, 32)}
        with patch('tracker.service.search_pc_memory',
                   return_value=(0x08C00000, found, {'searched': 1})) as search:
            self.service.scan_next = 1
            for _ in range(30):
                self.service._gen6_scan_step({})
            changes = self.service._gen6_scan_step({})
        search.assert_called_once()
        self.assertTrue(changes['box_verified'])
        self.assertEqual(self.service.profile.box_address, 0x08C00000)
        self.assertEqual(self.service.diagnostic['gen6_box_search'], {'searched': 1})
        self.assertTrue(self.service.gen6_research_done)
        self.assertEqual(self.service.scan_verified, set(range(1, 32)))

    def test_gen6_search_records_error_and_reraises_cancellation(self):
        profile = PROFILES['Pokémon Y 1.0']
        self.use(profile.name, RecordingGen6Memory(profile, with_box=False))
        self.service.diagnostic = {}
        with patch('tracker.service.search_pc_memory', side_effect=OSError('x' * 300)):
            self.assertEqual(self.service._gen6_search_pc(), (None, None))
        self.assertEqual(self.service.diagnostic['gen6_box_search'], {'error': 'x' * 120})
        with patch('tracker.service.search_pc_memory', side_effect=DiscoveryCancelled('stop')):
            with self.assertRaises(DiscoveryCancelled):
                self.service._gen6_search_pc()

    def test_gen6_unverified_finish_keeps_previous_flag(self):
        profile = PROFILES['Pokémon Y 1.0']
        self.use(profile.name, RecordingGen6Memory(profile, with_box=False))
        self.service.gen6_research_done = True
        self.service.scan_next = 1
        for _ in range(30):
            self.service._gen6_scan_step({'box_verified': True})
        changes = self.service._gen6_scan_step({'box_verified': True})
        self.assertTrue(changes['box_verified'])
        self.assertNotIn('boxes', changes)
        self.assertEqual(self.service.scan_verified, set())
        self.assertIn('cajas no verificadas', changes['connection']['message'])

    def test_gen6_idle_connection_messages(self):
        self.assertEqual(TrackerService._gen6_idle_connection({'box_verified': True})['message'],
                         'Gen6 experimental · equipo y cajas PK6 · PS combate experimental')
        self.assertEqual(TrackerService._gen6_idle_connection({})['message'],
                         'Gen6 experimental · equipo válido, cajas no verificadas')

    # -- Gen7 ----------------------------------------------------------
    def test_gen7_scan_step_probes_shifted_addresses(self):
        self.use('Ultra Moon 1.0', RecordingGen7Memory())
        self.service.profile = replace(ULTRA_MOON_10, party_address=ULTRA_MOON_10.party_address + 0x2400)
        self.service.scan_next = 1
        changes = self.service._gen7_scan_step()
        self.assertEqual(changes, {'box_verified': False, 'box_status': 'pending',
                                   'scan': {'active': True, 'completed': 1}})
        self.assertEqual(self.service.gen7_probe.addresses,
                         (ULTRA_MOON_10.box_address, ULTRA_MOON_10.box_address + 0x2400))

    def test_gen7_empty_scan_reports_pending_empty(self):
        self.use('Ultra Moon 1.0', RecordingGen7Memory())
        self.service.scan_next = 1
        for _ in range(32):
            changes = self.service._gen7_scan_step()
        self.assertEqual(changes['box_status'], 'pending_empty')
        self.assertFalse(changes['box_verified'])
        self.assertIsNone(self.service.gen7_probe)
        self.assertIsNone(self.service.scan_next)

    def test_gen7_selected_box_refresh_replaces_only_that_box(self):
        box1 = party_data()[128:360] + bytes(BOX_SIZE - 232)
        address = ULTRA_MOON_10.box_address + 2 * BOX_SIZE
        self.use('Ultra Moon 1.0', RecordingGen7Memory({address: box1}))
        self.service.sun_box_base = ULTRA_MOON_10.box_address
        other = [None] * 30
        self.service.update(boxes={'1': other})
        changes = self.service._gen7_refresh_selected_box({'selected_box': 3})
        self.assertEqual(set(changes['boxes']), {'1', '3'})
        self.assertIs(changes['boxes']['1'], self.service.state['boxes']['1'])
        self.assertEqual(changes['boxes']['3'][0]['species_id'], 637)

    def test_gen7_selected_box_cancellation_propagates(self):
        class Cancelled:
            def read(self, address, length):
                raise DiscoveryCancelled('stop')
        self.use('Ultra Moon 1.0', Cancelled())
        self.service.sun_box_base = ULTRA_MOON_10.box_address
        with self.assertRaises(DiscoveryCancelled):
            self.service._gen7_refresh_selected_box({'selected_box': 1})

    def test_gen7_connection_messages(self):
        expected = {
            'verified': 'equipo y 32 cajas verificadas',
            'pending': 'equipo conectado; verificando cajas',
            'pending_empty': 'equipo conectado; cajas pendientes (deposita un Pokémon)',
            'ambiguous': 'equipo conectado; varias copias de PC, cajas pendientes',
            'invalid': 'equipo conectado; cajas pendientes de una lectura válida',
            'unknown': 'equipo conectado; verificando cajas',
        }
        for status, text in expected.items():
            self.assertEqual(TrackerService._gen7_connection(status),
                             {'status': 'connected', 'message': 'Conectado · ' + text})

    def test_poll_dispatches_by_generation(self):
        self.use('Pokémon X 1.0', RecordingGen6Memory(PROFILES['Pokémon X 1.0']))
        with patch.object(self.service, '_poll_gen6') as gen6, patch.object(self.service, '_poll_gen7') as gen7:
            self.service.poll()
            gen6.assert_called_once()
            gen7.assert_not_called()
        self.use('Ultra Moon 1.0', RecordingGen7Memory())
        with patch.object(self.service, '_poll_gen6') as gen6, patch.object(self.service, '_poll_gen7') as gen7:
            self.service.poll()
            gen7.assert_called_once()
            gen6.assert_not_called()


if __name__ == '__main__':
    unittest.main()
