"""OBS: objeto equipado, Pokémon muertos y ajustes nuevos sin romper configuraciones previas."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from tracker.overlay import DEFAULT, OverlayManager, validated_settings
from tracker.service import TrackerService


def mon(**extra):
    base = {'species_id': 25, 'nickname': 'Chispa', 'species': 'Pikachu', 'hp': 30, 'max_hp': 100,
            'encryption_constant': 125, 'origin_version': 33, 'item_id': 0, 'item': 'Ningún'}
    base.update(extra)
    return base


class OverlayItemTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.service = TrackerService(root / 'runtime' / 'state.json')
        (root / 'layout').mkdir()
        self.manager = OverlayManager(self.service, root / 'runtime', root / 'layout')

    def tearDown(self):
        self.temp.cleanup()

    def test_public_state_includes_held_item_name(self):
        self.service.update(party=[mon(item_id=234, item='Restos'), mon(encryption_constant=9)] + [None] * 4,
                            stale=False)
        party = self.manager.public_state()['party']
        self.assertEqual(party[0]['item'], 'Restos')
        # item_id 0 («Ningún») no debe mostrarse como objeto.
        self.assertEqual(party[1]['item'], '')
        self.assertNotIn('item', party[2])

    def test_item_name_is_bounded_text(self):
        self.service.update(party=[mon(item_id=5, item='X' * 200)] + [None] * 5, stale=False)
        self.assertEqual(len(self.manager.public_state()['party'][0]['item']), 40)
        self.service.update(party=[mon(item_id=5, item=None)] + [None] * 5, stale=False)
        self.assertEqual(self.manager.public_state()['party'][0]['item'], '')

    def test_new_item_settings_validated(self):
        ok = validated_settings({**DEFAULT, 'items_in_composition': True, 'item_size': 18,
                                 'item_color': '#112233'})
        self.assertTrue(ok['items_in_composition'])
        self.assertEqual(validated_settings({**DEFAULT, 'item_display': 'both', 'item_icon_size': 48})['item_display'], 'both')
        for bad in ({'items_in_composition': 'si'}, {'item_size': 2}, {'item_size': 99},
                    {'item_color': 'red'}, {'item_display': 'html'}, {'item_icon_size': 4},
                    {'item_icon_size': 500}):
            with self.assertRaises(ValueError):
                validated_settings({**DEFAULT, **bad})

    def test_settings_saved_before_items_still_load(self):
        old = {k: v for k, v in copy.deepcopy(DEFAULT).items()
               if k not in ('items_in_composition', 'item_size', 'item_color', 'item_display', 'item_icon_size')}
        clean = validated_settings(old)
        self.assertFalse(clean['items_in_composition'])
        self.manager.path.parent.mkdir(parents=True, exist_ok=True)
        self.manager.path.write_text(json.dumps(old), encoding='utf-8')
        reloaded = OverlayManager(self.service, self.manager.runtime, self.manager.layout)
        self.assertEqual(reloaded.get_settings()['item_size'], DEFAULT['item_size'])


if __name__ == '__main__':
    unittest.main()
