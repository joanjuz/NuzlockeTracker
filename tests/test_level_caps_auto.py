"""Optional automatic advance of level-cap stages: genuine level-ups only, one stage at a time."""
import json
import tempfile
import unittest
from pathlib import Path

from tracker.level_caps_auto import CONFIRM_SECONDS, LevelCapsAuto, LevelUpWatcher, party_levels
from tracker.progress import LEVEL_CAP_ACTIONS, RunProgress, validated_level_caps
from tracker.service import TrackerService

LIVE = {'status': 'connected', 'message': 'prueba'}


def mon(ec, level, nickname=None, **extra):
    return {'species_id': 25, 'species': 'Pikachu', 'nickname': nickname or f'P{ec}', 'encryption_constant': ec,
            'origin_version': 33, 'level': level, 'hp': 20, 'max_hp': 20, 'egg': False, 'checksum_valid': True,
            'moves': [0, 0, 0, 0], 'met_location_id': 8, **extra}


def party(*members):
    return list(members) + [None] * (6 - len(members))


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


class LevelUpWatcherTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.watcher = LevelUpWatcher(self.clock)

    def feed(self, cap, *members):
        self.clock.now += 1
        return self.watcher.observe(party(*members), cap)

    def test_genuine_level_up_across_the_cap_needs_a_confirming_reading(self):
        self.assertIsNone(self.feed(20, mon(1, 20), mon(2, 18)))  # baseline
        self.assertIsNone(self.feed(20, mon(1, 21), mon(2, 18)))  # seen once
        self.assertEqual(self.feed(20, mon(1, 21), mon(2, 18)),
                         {'key': '33:1', 'name': 'P1', 'from': 20, 'to': 21, 'cap': 20})
        self.assertIsNone(self.feed(20, mon(1, 21), mon(2, 18)), 'Una sola vez por subida')
        self.assertIsNone(self.feed(20, mon(1, 22), mon(2, 18)), 'Ya estaba por encima: no vuelve a cruzar')

    def test_team_already_above_the_cap_never_counts(self):
        for _ in range(4):
            self.assertIsNone(self.feed(20, mon(1, 35), mon(2, 40)))
        self.assertIsNone(self.feed(20, mon(1, 36), mon(2, 40)))
        self.assertIsNone(self.feed(20, mon(1, 36), mon(2, 40)))

    def test_level_up_below_or_up_to_the_cap_does_not_count(self):
        self.feed(20, mon(1, 18))
        self.assertIsNone(self.feed(20, mon(1, 20)))
        self.assertIsNone(self.feed(20, mon(1, 20)))

    def test_party_changes_are_not_level_ups(self):
        self.feed(20, mon(1, 20), mon(2, 10))
        # A stronger Pokémon is withdrawn from the PC, another is deposited.
        self.assertIsNone(self.feed(20, mon(1, 20), mon(3, 50)))
        self.assertIsNone(self.feed(20, mon(1, 20), mon(3, 50)))
        # Reordering the same party is fine but is not a level-up either.
        self.assertIsNone(self.feed(20, mon(3, 50), mon(1, 20)))
        # Level-up in the same reading as a swap: ignored.
        self.assertIsNone(self.feed(20, mon(1, 21), mon(4, 5)))
        self.assertIsNone(self.feed(20, mon(1, 21), mon(4, 5)))

    def test_rewind_or_unconfirmed_reading_is_dropped(self):
        self.feed(20, mon(1, 20), mon(2, 30))
        self.assertIsNone(self.feed(20, mon(1, 21), mon(2, 29)), 'Otro integrante perdió niveles: lectura de otra partida')
        self.feed(20, mon(1, 20), mon(2, 29))
        self.assertIsNone(self.feed(20, mon(1, 21), mon(2, 29)))
        self.assertIsNone(self.feed(20, mon(1, 20), mon(2, 29)), 'La subida no se confirmó')
        self.assertIsNone(self.feed(20, mon(1, 20), mon(2, 29)))

    def test_confirmation_must_be_recent_and_for_the_same_cap(self):
        self.feed(20, mon(1, 20))
        self.feed(20, mon(1, 21))
        self.clock.now += CONFIRM_SECONDS + 5
        self.assertIsNone(self.feed(20, mon(1, 21)), 'Lectura tardía: se vuelve a pedir confirmación')
        self.assertIsNotNone(self.feed(20, mon(1, 21)))
        self.watcher.reset()
        self.feed(20, mon(1, 20))
        self.feed(20, mon(1, 21))
        self.assertIsNone(self.feed(30, mon(1, 21)), 'La etapa cambió a mano entre lecturas')
        self.assertIsNone(self.feed(30, mon(1, 21)))

    def test_reset_and_missing_cap_only_set_the_baseline(self):
        self.feed(20, mon(1, 20))
        self.watcher.reset()
        self.assertIsNone(self.feed(20, mon(1, 25)), 'Primera lectura tras reconectar')
        self.assertIsNone(self.feed(20, mon(1, 25)))
        self.watcher.reset()
        self.feed(None, mon(1, 20))
        self.assertIsNone(self.feed(None, mon(1, 21)))
        self.assertIsNone(self.feed(20, mon(1, 21)), 'Sin límite vigente no queda nada pendiente')

    def test_only_valid_hatched_members_are_read(self):
        levels = party_levels([mon(1, 20), mon(2, 5, egg=True), mon(3, 5, checksum_valid=False), mon(4, 0), mon(5, 101),
                               mon(6, '7'), {'level': 5}, None, 'x'])
        self.assertEqual(levels, {'33:1': {'level': 20, 'name': 'P1'}})
        self.assertEqual(party_levels(None), {})

    def test_several_crossings_in_one_reading_give_one_result(self):
        self.feed(20, mon(1, 20), mon(2, 20))
        self.feed(20, mon(1, 21), mon(2, 22))
        self.assertEqual(self.feed(20, mon(1, 21), mon(2, 22))['key'], '33:1')
        self.assertIsNone(self.feed(20, mon(1, 21), mon(2, 22)))


class LevelCapsAutoStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'state-level-caps-auto.json'

    def test_off_by_default_and_persisted(self):
        auto = LevelCapsAuto(self.path)
        self.assertEqual(auto.view(), {'enabled': False, 'read_only': False, 'event': None})
        self.assertFalse(self.path.exists(), 'Sin activar no se escribe nada')
        self.assertTrue(auto.set_enabled(True))
        self.assertFalse(auto.set_enabled(True))
        self.assertTrue(LevelCapsAuto(self.path).enabled)
        with self.assertRaises(ValueError):
            auto.set_enabled('yes')
        auto.set_enabled(False)
        self.assertFalse(LevelCapsAuto(self.path).enabled)

    def test_damaged_or_newer_files_leave_it_off(self):
        for text in ('{', '[]', '{"format":"other","version":1,"enabled":true}',
                     '{"format":"progressive-tracker-level-caps-auto","version":1,"enabled":"true"}'):
            self.path.write_text(text, encoding='utf-8')
            self.assertFalse(LevelCapsAuto(self.path).enabled, text)
        newer = '{"format":"progressive-tracker-level-caps-auto","version":2,"enabled":true,"mode":"x"}'
        self.path.write_text(newer, encoding='utf-8')
        auto = LevelCapsAuto(self.path)
        self.assertEqual((auto.enabled, auto.read_only), (False, True))
        with self.assertRaisesRegex(ValueError, 'versión más nueva'):
            auto.set_enabled(True)
        self.assertEqual(self.path.read_text(encoding='utf-8'), newer)


class LevelCapsAutoServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.service = TrackerService(self.root / 'state.json')
        self.service.handle({'action': 'level_caps_set', 'stages': [
            {'name': 'Gimnasio 1', 'cap': 14}, {'name': 'Gimnasio 2', 'cap': 20}, {'name': 'Gimnasio 3', 'cap': 27}]})
        self.ids = [s['id'] for s in self.caps()['stages']]
        self.service.handle({'action': 'level_caps_current', 'stage': self.ids[0]})

    def caps(self):
        return self.service.snapshot()['level_caps']

    def auto(self):
        return self.service.snapshot()['level_caps_auto']

    def read(self, *members, **changes):
        self.service.update(party=party(*members), stale=False, connection=dict(LIVE), **changes)

    def enable(self):
        self.service.handle({'action': 'level_caps_auto', 'enabled': True})

    def test_disabled_by_default_and_nothing_advances(self):
        self.assertEqual(self.auto(), {'enabled': False, 'read_only': False, 'event': None})
        self.read(mon(1, 14))
        self.read(mon(1, 15))
        self.read(mon(1, 15))
        self.assertEqual(self.caps()['current'], self.ids[0])
        self.assertIsNone(self.auto()['event'])

    def test_real_level_up_advances_exactly_one_stage_saves_and_notifies(self):
        self.enable()
        self.assertTrue(self.auto()['enabled'])
        self.read(mon(1, 14, 'Chispa'), mon(2, 9))
        self.read(mon(1, 15, 'Chispa'), mon(2, 9))
        self.assertEqual(self.caps()['current'], self.ids[0], 'Aún sin confirmar')
        self.read(mon(1, 15, 'Chispa'), mon(2, 9))
        self.assertEqual(self.caps()['current'], self.ids[1])
        event = self.auto()['event']
        self.assertEqual((event['kind'], event['pokemon'], event['from_level'], event['to_level']), ('advance', 'Chispa', 14, 15))
        self.assertEqual((event['from_stage']['name'], event['to_stage']['name'], event['to_stage']['cap']),
                         ('Gimnasio 1', 'Gimnasio 2', 20))
        # Saved in the same place and shape as a manual choice.
        stored = json.loads((self.root / 'state-progress.json').read_text(encoding='utf-8'))['level_caps']
        self.assertEqual(stored['current'], self.ids[1])
        self.assertEqual(set(stored), {'version', 'stages', 'current', 'show', 'updated_at', 'removed_current'})
        self.assertEqual(validated_level_caps(stored)['current'], self.ids[1], 'El contrato de etapas no cambia')
        self.assertEqual(RunProgress(self.root / 'state-progress.json').data['level_caps']['current'], self.ids[1])
        # More readings at the same level do nothing else.
        for _ in range(3):
            self.read(mon(1, 15, 'Chispa'), mon(2, 9))
        self.assertEqual(self.caps()['current'], self.ids[1])

    def test_big_jump_advances_one_stage_only(self):
        self.enable()
        self.read(mon(1, 14))
        self.read(mon(1, 40))
        self.read(mon(1, 40))
        self.assertEqual(self.caps()['current'], self.ids[1], 'Un salto por encima de varios límites avanza solo uno')
        for _ in range(4):
            self.read(mon(1, 40))
        self.assertEqual(self.caps()['current'], self.ids[1])
        self.read(mon(1, 41))
        self.read(mon(1, 41))
        self.assertEqual(self.caps()['current'], self.ids[1], 'Ya estaba por encima del nuevo límite')

    def test_loaded_team_above_cap_old_run_reconnect_and_imports_do_not_advance(self):
        self.enable()
        # Team already above the cap when the run is opened.
        for _ in range(3):
            self.read(mon(1, 30), mon(2, 31))
        self.assertEqual(self.caps()['current'], self.ids[0])
        # Connection lost and recovered with higher levels (another save, time passed).
        self.read(mon(1, 14))
        self.service.update(stale=True, connection={'status': 'disconnected', 'message': 'x'})
        self.read(mon(1, 15))
        self.read(mon(1, 15))
        self.assertEqual(self.caps()['current'], self.ids[0], 'Reconectar no es subir de nivel')
        # Saved data shown while not connected.
        self.service.update(party=party(mon(1, 14)), stale=True)
        self.service.update(party=party(mon(1, 15)), stale=True)
        self.service.update(party=party(mon(1, 15)), stale=True)
        self.assertEqual(self.caps()['current'], self.ids[0])
        # A reading without a live connection status.
        self.service.update(party=party(mon(1, 14)), stale=False, connection={'status': 'connecting', 'message': 'x'})
        self.service.update(party=party(mon(1, 15)), stale=False, connection={'status': 'connecting', 'message': 'x'})
        self.service.update(party=party(mon(1, 15)), stale=False, connection={'status': 'connecting', 'message': 'x'})
        self.assertEqual(self.caps()['current'], self.ids[0])
        self.assertIsNone(self.auto()['event'])

    def test_restart_and_enabling_start_from_a_fresh_baseline(self):
        self.read(mon(1, 14))
        self.read(mon(1, 15))
        self.enable()
        self.read(mon(1, 15))
        self.read(mon(1, 15))
        self.assertEqual(self.caps()['current'], self.ids[0], 'Activar la opción no actúa sobre lo ya ocurrido')
        self.service.flush_state(force=True)
        again = TrackerService(self.root / 'state.json')
        self.assertTrue(again.snapshot()['level_caps_auto']['enabled'], 'La opción se conserva')
        self.assertIsNone(again.snapshot()['level_caps_auto']['event'])
        again.update(party=party(mon(1, 16)), stale=False, connection=dict(LIVE))
        again.update(party=party(mon(1, 16)), stale=False, connection=dict(LIVE))
        self.assertEqual(again.snapshot()['level_caps']['current'], self.ids[0], 'Abrir una partida no avanza')

    def test_last_stage_and_no_current_stage_do_nothing(self):
        self.enable()
        self.service.handle({'action': 'level_caps_current', 'stage': self.ids[2]})
        self.read(mon(1, 27))
        self.read(mon(1, 28))
        self.read(mon(1, 28))
        self.assertEqual(self.caps()['current'], self.ids[2])
        self.assertIsNone(self.auto()['event'])
        self.service.handle({'action': 'level_caps_current', 'stage': None})
        self.read(mon(1, 28))
        self.read(mon(1, 29))
        self.read(mon(1, 29))
        self.assertIsNone(self.caps()['current'], 'Sin etapa vigente no se elige ninguna')

    def test_decreasing_list_only_suggests(self):
        self.service.handle({'action': 'level_caps_set', 'stages': [
            {'name': 'Alto', 'cap': 30}, {'name': 'Bajo', 'cap': 12}, {'name': 'Final', 'cap': 50}]})
        ids = [s['id'] for s in self.caps()['stages']]
        self.service.handle({'action': 'level_caps_current', 'stage': ids[0]})
        self.enable()
        self.read(mon(1, 30))
        self.read(mon(1, 31))
        self.read(mon(1, 31))
        self.assertEqual(self.caps()['current'], ids[0], 'La siguiente etapa baja el límite: no se avanza sola')
        event = self.auto()['event']
        self.assertEqual((event['kind'], event['to_stage']['name']), ('suggest', 'Bajo'))
        for _ in range(3):
            self.read(mon(1, 31))
        self.assertEqual(self.caps()['current'], ids[0])
        # The user accepts by hand: the notice goes away and nothing cascades.
        self.service.handle({'action': 'level_caps_current', 'stage': ids[1]})
        self.assertIsNone(self.auto()['event'])
        self.read(mon(1, 32))
        self.read(mon(1, 32))
        self.assertEqual(self.caps()['current'], ids[1])

    def test_manual_selection_wins_and_undo_is_a_manual_choice(self):
        self.enable()
        self.read(mon(1, 14))
        self.read(mon(1, 15))
        self.read(mon(1, 15))
        self.assertEqual(self.caps()['current'], self.ids[1])
        self.service.handle({'action': 'level_caps_current', 'stage': self.ids[0]})  # undo
        self.assertEqual(self.caps()['current'], self.ids[0])
        self.assertIsNone(self.auto()['event'])
        for _ in range(3):
            self.read(mon(1, 15))
        self.assertEqual(self.caps()['current'], self.ids[0], 'Deshacer no provoca otro avance')
        # Turning it off stops everything.
        self.service.handle({'action': 'level_caps_auto', 'enabled': False})
        self.read(mon(2, 14))
        self.read(mon(2, 15))
        self.read(mon(2, 15))
        self.assertEqual(self.caps()['current'], self.ids[0])

    def test_option_is_isolated_per_game_and_run(self):
        self.enable()
        self.assertTrue((self.root / 'state-level-caps-auto.json').is_file())
        self.service.open_progress(self.service.progress_suffix('Ultra Sun 1.0'), 'Ultra Sun 1.0')
        self.assertFalse(self.service.level_caps_auto.enabled)
        other = TrackerService(self.root / 'profiles' / 'otra' / 'state.json')
        self.assertFalse(other.snapshot()['level_caps_auto']['enabled'])

    def test_command_validation(self):
        self.assertIn('level_caps_auto', LEVEL_CAP_ACTIONS)
        for bad in ({'action': 'level_caps_auto'}, {'action': 'level_caps_auto', 'enabled': 'si'},
                    {'action': 'level_caps_auto', 'enabled': 1}):
            with self.assertRaises(ValueError):
                self.service.validate_level_caps(bad)
        self.service.validate_level_caps({'action': 'level_caps_auto', 'enabled': True})
        self.assertFalse(self.auto()['enabled'], 'Validar no cambia nada')

    def test_no_memory_writes(self):
        source = (Path(__file__).resolve().parent.parent / 'tracker' / 'level_caps_auto.py').read_text(encoding='utf-8')
        for word in ('WriteProcessMemory', 'write_memory', 'reader', 'socket'):
            self.assertNotIn(word, source)


if __name__ == '__main__':
    unittest.main()
