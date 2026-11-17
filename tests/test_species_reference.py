"""Offline species/form references and local imported-data precedence."""
import copy
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tracker.catalog import Catalog
from tracker.reference import ReferenceData
from tracker.service import TrackerService


class SpeciesReferenceTests(unittest.TestCase):
    def setUp(self):
        self.reference = ReferenceData()

    def test_offline_base_stats_are_species_form_and_generation_specific(self):
        with patch('urllib.request.urlopen', side_effect=AssertionError('No network')):
            xy = self.reference.species_reference.lookup(65, 1, 'Pokémon X 1.0')
            usum = self.reference.species_reference.lookup(65, 1, 'Ultra Moon 1.0')
            self.assertEqual(xy['base_stats']['SPD'], 95)
            self.assertEqual(usum['base_stats']['SPD'], 105)
            self.assertEqual(self.reference.species_reference.lookup(6, 0, 'Ultra Moon 1.0')['base_stats'],
                             {'HP':78, 'ATK':84, 'DEF':78, 'SPA':109, 'SPD':85, 'SPE':100})

    def test_unknown_species_form_or_game_never_reuses_normal_form(self):
        for species, form, game in [(6, 99, 'Ultra Moon 1.0'), (9999, 0, 'Ultra Moon 1.0'),
                                    (6, 0, 'Unknown'), (807, 0, 'Pokémon X 1.0')]:
            self.assertIsNone(self.reference.species_reference.lookup(species, form, game))

    def test_mega_requires_matching_stone_and_preserves_original(self):
        p = {'species_id':6, 'form':0, 'item_id':660, 'stats':{'ATQ':99}, 'max_hp':100}
        before = copy.deepcopy(p)
        x = self.reference.mega_preview(p, Catalog(), 'Ultra Moon 1.0')
        y = self.reference.mega_preview({**p, 'item_id':678}, Catalog(), 'Ultra Moon 1.0')
        self.assertEqual((x['form'], x['types'], x['base_stats']['ATK'], x['ability_id']),
                         (1, ['Fuego','Dragón'], 130, 181))
        self.assertEqual((y['form'], y['types'], y['base_stats']['SPA'], y['ability_id']),
                         (2, ['Fuego','Volador'], 159, 70))
        self.assertEqual(p, before)
        self.assertTrue(x['reference_only'])
        self.assertNotIn('stats', x)
        self.assertNotIn('max_hp', x)
        self.assertIsNone(self.reference.mega_preview({**p, 'species_id':25}, Catalog(), 'Ultra Moon 1.0'))
        self.assertIsNone(self.reference.mega_preview({**p, 'form':1}, Catalog(), 'Ultra Moon 1.0'))

    def test_oras_megas_are_not_offered_in_xy(self):
        p = {'species_id':373, 'form':0, 'item_id':769}
        self.assertIsNone(self.reference.mega_preview(p, Catalog(), 'Pokémon X 1.0'))
        self.assertEqual(self.reference.mega_preview(p, Catalog(), 'Omega Ruby 1.0')['base_stats']['ATK'], 145)

    def test_mega_uses_exact_imported_form_before_reference(self):
        row = {'types':[3,3], 'abilities':[26,26,26],
               'baseStats':{'hp':90,'attack':120,'defense':100,'specialAttack':160,'specialDefense':140,'speed':130}}
        self.reference.game_data = SimpleNamespace(species=lambda species,form,game: row if (species,form)==(6,1) else None,
                                                   ability_name=lambda ability,game: 'Levitación personalizada')
        result = self.reference.mega_preview({'species_id':6,'item_id':660}, Catalog(), 'Ultra Moon 1.0')
        self.assertEqual(result['types'], ['Veneno'])
        self.assertEqual(result['base_stats']['HP'], 90)
        self.assertEqual((result['ability_id'],result['ability']), (26,'Levitación personalizada'))
        self.assertFalse(result['reference_only'])
        self.assertEqual(result['base_stats_source'], 'Definitive Game Data')

    def test_unavailable_cache_only_removes_reference_data(self):
        from tracker.species_reference import SpeciesReference
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'cache.json'
            self.assertIsNone(SpeciesReference(path).lookup(6,0,'Ultra Moon 1.0'))
            path.write_text('{bad', encoding='utf-8')
            self.assertIsNone(SpeciesReference(path).lookup(6,0,'Ultra Moon 1.0'))

    def test_randomized_mega_ability_requires_unambiguous_evidence(self):
        mega = {'types':[9,2], 'abilities':[26,1,0],
                'baseStats':{'hp':78,'attack':130,'defense':111,'specialAttack':130,'specialDefense':85,'speed':100}}
        normal = {'abilities':[77,88,0]}
        self.reference.game_data = SimpleNamespace(species=lambda species,form,game: mega if form==1 else normal,
                                                   ability_name=lambda ability,game: f'Habilidad {ability}')
        p = {'species_id':6,'item_id':660,'ability_id':77}
        known = self.reference.mega_preview(p, Catalog(), 'Ultra Moon 1.0')
        self.assertEqual(known['ability_id'], 26)
        normal['abilities'] = [77,77,0]
        uncertain = self.reference.mega_preview(p, Catalog(), 'Ultra Moon 1.0')
        self.assertEqual(uncertain['ability_id'], 0)
        self.assertFalse(uncertain['ability_known'])
        self.assertIn('confirmar', uncertain['ability'])

    def test_refresh_uses_fallback_without_inventing_current_stats_or_nature(self):
        with tempfile.TemporaryDirectory() as folder:
            service = TrackerService(Path(folder)/'state.json')
            p = {'species_id':6, 'form':0, 'item_id':660, 'nature':'Firme', 'stats':None, 'level':None}
            result = service.refresh_template(p)
            self.assertEqual(result['base_stats']['ATK'], 84)
            self.assertIn('PKHeX', result['base_stats_source'])
            self.assertEqual(result['nature'], 'Firme')
            self.assertIsNone(result['stats'])
            self.assertIsNone(result['level'])
            self.assertEqual(result['mega_preview']['form'], 1)

    def test_csv_overrides_fallback_and_dgd_overrides_csv(self):
        with tempfile.TemporaryDirectory() as folder:
            service = TrackerService(Path(folder)/'state.json')
            service.templates.data['stats']['6'] = {'HP':1, 'ATK':2, 'DEF':3, 'SPA':4, 'SPD':5, 'SPE':6}
            self.assertEqual(service.refresh_template({'species_id':6})['base_stats']['HP'], 1)
            row = {'name':'Custom', 'types':[9,9], 'abilities':[65,65,0],
                   'baseStats':{'hp':123,'attack':124,'defense':125,'specialAttack':126,'specialDefense':127,'speed':128}}
            with patch.object(service.game_data, 'species', return_value=row):
                result = service.refresh_template({'species_id':6})
            self.assertEqual(result['base_stats']['HP'], 123)
            self.assertEqual(result['base_stats_source'], 'Definitive Game Data')

    def test_csv_without_form_does_not_claim_mega_stats(self):
        with tempfile.TemporaryDirectory() as folder:
            service = TrackerService(Path(folder)/'state.json')
            service.templates.data['stats']['6'] = {'HP':1, 'ATK':2, 'DEF':3, 'SPA':4, 'SPD':5, 'SPE':6}
            result = service.refresh_template({'species_id':6, 'form':1})
            self.assertEqual(result['base_stats']['ATK'], 130)


if __name__ == '__main__':
    unittest.main()
