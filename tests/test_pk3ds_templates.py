import json
import tempfile
import unittest
from pathlib import Path

from tracker.catalog import Catalog
from tracker.service import TrackerService
from tracker.templates import TemplateManager, moves_csv, stats_csv, evolutions_csv


MOVE_CSV = """# pk3DS template notes
# Blank cells retain original ROM values
Move,Type,Category,Power,Accuracy,PP,Priority,BattlePatch,Notes
79,,Status,,70,,,,Somnifero modified
15,Grass,Physical,70,100,,,,
171,,,,,,,,Special ROM patch required
"""
STAT_CSV = "Entry,Pokemon,HP,ATK,DEF,SPA,SPD,SPE,Notes\n,Slaking,130,130,100,90,65,85,\n"
EVO_CSV = """Source,Target,Method,Level,Argument,Form,ItemName,AltItemName
64,65,Level,37,,-1,,
79,199,UsedItem,,84,-1,Water Stone,Piedra Agua
75,76,Level,37,,-1,,
75,76,Level,39,,1,,
61,186,19,,221,-1,King's Rock,Roca del Rey
61,186,20,,221,-1,King's Rock,Roca del Rey
"""


class TemplateTests(unittest.TestCase):
    def test_sparse_moves_and_known_stats(self):
        moves = moves_csv(MOVE_CSV)
        self.assertEqual(moves['79']['accuracy'], 70)
        self.assertEqual(moves['79']['category'], 'Estado')
        self.assertNotIn('power', moves['79'])
        self.assertEqual(moves['15']['type'], 'Planta')
        self.assertEqual(moves['15']['power'], 70)
        self.assertEqual(stats_csv(STAT_CSV, Catalog())['289']['HP'], 130)

    def test_evolution_alternatives_and_vanilla_baseline(self):
        with tempfile.TemporaryDirectory() as folder:
            mgr = TemplateManager(Path(folder) / 'pk3ds-templates.json')
            self.assertEqual(mgr.evolutions(1)[0]['target'], 2)
            self.assertIn('nivel 16', mgr.evolutions(1)[0]['method'])
            mgr.import_csv({'evolutions': EVO_CSV})
            self.assertEqual(mgr.evolutions(64)[0]['target'], 65)
            self.assertEqual(mgr.evolutions(64)[0]['method'], 'Subir de nivel al nivel 37')
            targets = {e['target'] for e in mgr.evolutions(79)}
            self.assertEqual(targets, {80, 199})  # Preserve unedited Slowbro branch.
            new = next(x for x in mgr.evolutions(79) if x['target'] == 199)
            self.assertIn('Piedra Agua', new['method'])
            self.assertEqual(new['source'], 'pk3DS Progressive')
            self.assertEqual(len(mgr.evolutions(61)), 2)
            self.assertEqual(mgr.evolutions(75, 0)[0]['method'], 'Subir de nivel al nivel 37')
            self.assertEqual(mgr.evolutions(75, 1)[0]['method'], 'Subir de nivel al nivel 39')

    def test_template_persistence_and_atomic_invalid(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'template.json'
            mgr = TemplateManager(path)
            mgr.import_csv({'moves': MOVE_CSV, 'stats': STAT_CSV, 'evolutions': EVO_CSV})
            original = path.read_bytes()
            with self.assertRaises(ValueError):
                mgr.import_csv({'moves': 'Move,Power,PP\n15,900,10\n'})
            self.assertEqual(path.read_bytes(), original)
            self.assertIn('15', TemplateManager(path).data['moves'])
            self.assertIn('289', TemplateManager(path).data['stats'])
            with self.assertRaises(ValueError):
                mgr.import_csv({'unknown': 'data'})

    def test_live_metadata_update_keeps_hp_and_base_stats_separate(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'state.json'
            svc = TrackerService(path)
            poke = {'species_id': 289, 'nickname': 'Slaking', 'form': 0,
                    'moves': [15, 79, 0, 0], 'level': 40, 'hp': 19,
                    'max_hp': 180, 'origin_version': 33, 'encryption_constant': 55}
            svc.update(party=[poke]+[None]*5, stale=True)
            svc.import_templates({'moves': MOVE_CSV, 'stats': STAT_CSV, 'evolutions': EVO_CSV})
            mon = svc.snapshot()['party'][0]
            self.assertEqual(mon['hp'], 19)
            self.assertEqual(mon['max_hp'], 180)
            self.assertEqual(mon['base_stats']['HP'], 130)
            self.assertEqual(mon['analysis_moves'][0]['power'], 70)
            self.assertEqual(mon['analysis_moves'][1]['accuracy'], 70)
            self.assertEqual(svc.reference.move(15, svc.catalog)['type'], 'Planta')
            self.assertTrue(svc.snapshot()['templates']['loaded'])
            restarted = TrackerService(path)
            self.assertTrue(restarted.templates.status()['loaded'])

    def test_connection_reopens_same_profile_and_isolated_partner_session(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path_a = root / 'runtime' / 'state.json'
            path_b = root / 'runtime' / 'profiles' / 'second' / 'state.json'
            first = TrackerService(path_a, connector_factory=lambda options: object())
            first.config = {'game': 'Ultra Moon 1.0', 'mode': 'memory', 'pid': 4242,
                            'port': 24689, '_connection_generation': 8}
            first.connect()
            session = json.loads((path_a.parent / 'session-profile.json').read_text())
            self.assertNotIn('_connection_generation', session['connection'])
            self.assertEqual(session['connection']['pid'], 4242)
            loaded = TrackerService(path_a)
            self.assertEqual(loaded.config['game'], 'Ultra Moon 1.0')
            self.assertEqual(loaded.config['pid'], 4242)
            self.assertTrue(loaded.snapshot()['session_saved'])
            other = TrackerService(path_b)
            self.assertIsNone(other.config)
            self.assertFalse(other.snapshot()['session_saved'])
            with self.assertRaises(ValueError):
                first.valid_connection({'game': 'Ultra Moon 1.0', 'mode': 'memory', 'pid': -4})
            first.import_templates({'moves': MOVE_CSV})
            self.assertFalse(other.templates.status()['loaded'])


if __name__ == '__main__':
    unittest.main()
