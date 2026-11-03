"""OBS 1.2: perfiles de configuración, exportar/importar, estilo de muerte, marco, datos y estadísticas."""
import base64
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PIL import Image

from tracker import custom_sprites
from tracker.desktop_export import DesktopExportApi
from tracker.overlay import DEFAULT, OverlayManager, validated_settings
from tracker.overlay import settings as overlay_settings
from tracker.overlay.assets import BUILTIN_TOMBSTONE
from tracker.service import TrackerService


def png(color, size=(4, 4)):
    out = io.BytesIO()
    Image.new('RGBA', size, color).save(out, format='PNG')
    return out.getvalue()


RED, BLUE = png((250, 0, 0, 255)), png((0, 0, 250, 255))


def b64(raw):
    return base64.b64encode(raw).decode()


class Base(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.custom = self.root / 'sprites_personalizados'
        (self.custom / 'HD').mkdir(parents=True)
        self.service = TrackerService(self.root / 'runtime' / 'state.json')
        (self.root / 'layout').mkdir()
        self.overlay = OverlayManager(self.service, self.root / 'runtime', self.root / 'layout', custom_dir=self.custom)

    def tearDown(self):
        self.temp.cleanup()


class SettingsTests(unittest.TestCase):
    def test_every_setting_has_exactly_one_rule(self):
        self.assertEqual(overlay_settings.RULED, overlay_settings.ALLOWED)

    def test_new_settings_are_validated_and_old_configs_still_load(self):
        ok = validated_settings({**DEFAULT, 'death_style': 'tombstone', 'death_animation': 'shake',
                                 'info_size': 20, 'stats_direction': 'column', 'slot_frame': True})
        self.assertEqual((ok['death_style'], ok['stats_direction']), ('tombstone', 'column'))
        for bad in ({'death_style': 'explode'}, {'death_animation': 'spin'}, {'info_size': 2},
                    {'stats_size': 500}, {'slot_frame': 'si'}, {'stats_direction': 'grid'}):
            with self.assertRaises(ValueError):
                validated_settings({**DEFAULT, **bad})
        old = {k: v for k, v in DEFAULT.items() if not k.startswith(('death_', 'info_', 'stats_', 'slot_frame'))}
        self.assertEqual(validated_settings(old)['death_style'], 'gray')


class PresetTests(Base):
    def test_save_apply_delete_and_case_insensitive_rename(self):
        self.overlay.set_settings({**DEFAULT, 'gap': 40})
        self.overlay.preset_action('save', 'Combate')
        self.overlay.set_settings({**DEFAULT, 'gap': 5})
        result = self.overlay.preset_action('apply', 'Combate')
        self.assertEqual(result['settings']['gap'], 40)
        self.overlay.preset_action('save', 'COMBATE')
        self.assertEqual(self.overlay.presets_status()['presets'], [{'name': 'COMBATE'}])
        self.overlay.preset_action('delete', 'COMBATE')
        self.assertEqual(self.overlay.presets_status()['presets'], [])
        for action, name in (('save', '../x'), ('save', ''), ('save', 'x' * 41), ('apply', 'Nada'),
                             ('delete', 'Nada'), ('explode', 'Combate')):
            with self.assertRaises(ValueError):
                self.overlay.preset_action(action, name)

    def test_damaged_presets_file_never_blocks(self):
        self.overlay.presets.path.parent.mkdir(parents=True, exist_ok=True)
        self.overlay.presets.path.write_text(json.dumps({'Bueno': DEFAULT, 'Malo': {'gap': 9999}, '../x': DEFAULT}))
        self.assertEqual(self.overlay.presets_status()['presets'], [{'name': 'Bueno'}])
        self.overlay.presets.path.write_text('{roto')
        self.assertEqual(self.overlay.presets_status()['presets'], [])

    def test_public_settings_for_a_pinned_preset(self):
        self.overlay.set_settings({**DEFAULT, 'gap': 33})
        self.overlay.preset_action('save', 'Final')
        self.overlay.set_settings({**DEFAULT, 'gap': 1})
        self.assertEqual(self.overlay.public_settings('Final')['gap'], 33)
        self.assertIn('death_image_version', self.overlay.public_settings('Final'))
        self.assertIsNone(self.overlay.public_settings('No existe'))
        self.assertEqual(self.overlay.public_settings()['gap'], 1)


class ExportImportTests(Base):
    def test_round_trip_with_images_fonts_and_presets(self):
        self.overlay._import_png('slot', b64(RED))
        self.overlay._import_png('fill', b64(BLUE))
        self.overlay.import_font('Mia.ttf', b64(b'\x00\x01\x00\x00' + b'x' * 20))
        self.overlay.set_settings({**DEFAULT, 'gap': 21, 'font_file': 'Mia.ttf', 'sprite_set': 'HD', 'slot_frame': True})
        self.overlay.preset_action('save', 'Mi estilo')
        bundle = json.loads(json.dumps(self.overlay.export_bundle()))  # survives JSON
        other_root = self.root / 'otro'
        other = OverlayManager(self.service, other_root / 'runtime', self.root / 'layout', custom_dir=other_root / 'sp')
        result = other.import_bundle(bundle)
        self.assertEqual(result['settings']['gap'], 21)
        self.assertEqual(result['settings']['font_file'], 'Mia.ttf')
        self.assertEqual(result['settings']['sprite_set'], '', 'the set does not exist there')
        self.assertEqual(result['presets'], [{'name': 'Mi estilo'}])
        self.assertIsNotNone(other.slot_frame_bytes())
        self.assertIsNotNone(other.hp_image_bytes('fill'))

    def test_invalid_bundle_changes_nothing(self):
        self.overlay.set_settings({**DEFAULT, 'gap': 7})
        good = self.overlay.export_bundle()
        for bad in (None, {}, {**good, 'format': 'otro'}, {**good, 'settings': {'gap': 9999}},
                    {**good, 'images': {'../x': b64(RED)}}, {**good, 'presets': {'../x': DEFAULT}}):
            with self.assertRaises((ValueError, TypeError)):
                self.overlay.import_bundle(copy.deepcopy(bad))
        self.assertEqual(self.overlay.get_settings()['gap'], 7)


class DeathImageAndFrameTests(Base):
    def test_builtin_then_custom_tombstone_per_set(self):
        builtin = self.overlay.death_image()
        if BUILTIN_TOMBSTONE.exists():
            self.assertEqual(builtin[1], 'image/svg+xml')
        self.assertEqual(self.overlay.death_image_version(), 'builtin')
        (self.custom / 'lapida.png').write_bytes(RED)
        custom_sprites.clear_listing_cache()
        self.assertEqual(self.overlay.death_image(), (RED, 'image/png'))
        (self.custom / 'HD' / 'Lapida.PNG').write_bytes(BLUE)
        self.overlay.set_settings({**DEFAULT, 'sprite_set': 'HD'})
        custom_sprites.clear_listing_cache()
        self.assertEqual(self.overlay.death_image()[0], BLUE)
        self.assertNotEqual(self.overlay.death_image_version(), 'builtin')

    def test_slot_frame_import_and_bytes(self):
        self.assertIsNone(self.overlay.slot_frame_bytes())
        self.assertEqual(self.overlay.slot_frame_version(), '0')
        self.overlay.import_hp_image('slot', b64(RED))
        self.assertTrue(self.overlay.slot_frame_bytes().startswith(b'\x89PNG'))
        self.assertIsNone(self.overlay.hp_image_bytes('slot'), 'not served through the HP-bar route')
        with self.assertRaises(ValueError):
            self.overlay.import_hp_image('../x', b64(RED))


class PublicStateTests(Base):
    def test_info_fields_and_stats(self):
        mon = {'species_id': 25, 'nickname': 'Chispa', 'hp': 0, 'max_hp': 50, 'level': 33,
               'types': ['Eléctrico', 'Volador', 'Extra'], 'shiny': True, 'gender': 1,
               'encryption_constant': 1, 'origin_version': 33, 'checksum_valid': True}
        alive = {**mon, 'hp': 20, 'encryption_constant': 2, 'shiny': 'yes', 'gender': 7, 'level': 500}
        self.service.progress.data['encounters'] = {'a': {}, 'b': {}, 'c': {}}
        self.service.progress.data['missed_routes'] = ['10', '11']
        self.service.update(party=[mon, alive] + [None] * 4, stale=False)
        public = self.overlay.public_state()
        first, second = public['party'][:2]
        self.assertEqual((first['level'], first['types'], first['shiny'], first['gender']),
                         (33, ['Eléctrico', 'Volador'], True, 1))
        self.assertEqual((second['level'], second['shiny'], second['gender']), (None, False, None))
        self.assertEqual(public['stats'], {'captures': 3, 'deaths': 1, 'alive': 1, 'missed': 2})
        raw = json.dumps(public)
        self.assertNotIn('encryption_constant', raw)


class VariantFolderTests(unittest.TestCase):
    def test_shiny_and_female_folders_come_first_with_fallback(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for folder in ('Home/shiny', 'Home/female', 'Smogon/Hembra', 'shiny'):
                (root / folder).mkdir(parents=True)
            names = lambda mon, s='Home': [p.relative_to(root).as_posix() for p in custom_sprites.sprite_dirs(root, s, mon)]
            self.assertEqual(names({'shiny': True}), ['Home/shiny', 'Home', 'shiny', '.'])
            self.assertEqual(names({'gender': 1}), ['Home/female', 'Home', '.'])
            self.assertEqual(names({'gender': 1}, 'Smogon'), ['Smogon/Hembra', 'Smogon', '.'])
            self.assertEqual(names({'shiny': False, 'gender': 0}), ['Home', '.'])


class DesktopObsExportTests(Base):
    def test_native_dialog_saves_the_obs_bundle(self):
        window = MagicMock()
        target = self.root / 'mi_obs.json'
        window.create_file_dialog.return_value = [str(target)]
        api = DesktopExportApi(self.service, window, overlay=self.overlay)
        with patch.dict('sys.modules', {'webview': MagicMock()}):
            self.assertTrue(api.save_export('obs')['saved'])
        self.assertEqual(json.loads(target.read_text(encoding='utf-8'))['format'], 'progressive-tracker-obs')
        self.assertIn('error', DesktopExportApi(self.service, window).save_export('obs'))


if __name__ == '__main__':
    unittest.main()


class ReviewFixTests(Base):
    def test_import_is_atomic_when_a_later_image_is_corrupt(self):
        self.overlay._import_png('fill', b64(BLUE))
        before = self.overlay.hp_image_bytes('fill')
        bundle = self.overlay.export_bundle()
        bundle['fonts'] = {'Evil.ttf': b64(b'\x00\x01\x00\x00' + b'x' * 20)}
        bundle['images'] = {'fill': b64(RED), 'slot': b64(b'no es un png')}
        with self.assertRaises(ValueError):
            self.overlay.import_bundle(bundle)
        self.assertEqual(self.overlay.hp_image_bytes('fill'), before, 'previous image kept')
        self.assertNotIn('Evil.ttf', self.overlay.available_fonts())
        self.assertIsNone(self.overlay.slot_frame_bytes())

    def test_preset_names_are_case_insensitive_and_imports_reject_duplicates(self):
        self.overlay.preset_action('save', 'Combate')
        self.overlay.preset_action('save', 'combate')  # rename, old OBS links keep working
        self.assertIsNotNone(self.overlay.public_settings('COMBATE'))
        self.overlay.preset_action('delete', 'COMBATE')
        bundle = self.overlay.export_bundle()
        for presets in ({'A': DEFAULT, 'a': DEFAULT}, {f'P{i}': DEFAULT for i in range(31)}):
            with self.assertRaises(ValueError):
                self.overlay.import_bundle({**bundle, 'presets': presets})

    def test_export_always_fits_and_reports_what_was_left_out(self):
        from tracker.overlay import presets as presets_module
        self.overlay._import_png('fill', b64(RED))
        self.overlay.import_font('Grande.ttf', b64(b'\x00\x01\x00\x00' + b'x' * 50))
        budget = len(b64(self.overlay.hp_image_bytes('fill'))) + 10  # the image fits, the font does not
        with patch.object(presets_module, 'EXPORT_BUDGET', budget), \
                patch('tracker.overlay.manager.EXPORT_BUDGET', budget):
            bundle = self.overlay.export_bundle()
        self.assertIn('fill', bundle['images'])
        self.assertIn('Grande.ttf', bundle['omitted'])
        self.assertLessEqual(sum(len(v) for v in {**bundle['images'], **bundle['fonts']}.values()), budget)

    def test_variant_folders_of_the_root_are_not_sets(self):
        for name in ('shiny', 'female', 'Hembra'):
            (self.custom / name).mkdir()
        self.assertEqual(custom_sprites.list_sets(self.custom), ['HD'])

    def test_pinned_preset_decides_graveyard_order(self):
        for ec, when in ((1, '2026-01-01'), (2, '2026-02-01')):
            mon = {'species_id': 25, 'nickname': f'M{ec}', 'encryption_constant': ec, 'origin_version': 33}
            self.service.progress.data['deaths'][f'33:{ec}'] = {'pokemon': mon, 'recorded_at': when}
        self.service.update()
        self.overlay.set_settings({**DEFAULT, 'graveyard_order': 'oldest'})
        self.overlay.preset_action('save', 'Antiguos')
        self.overlay.set_settings({**DEFAULT, 'graveyard_order': 'recent'})
        self.assertEqual(self.overlay.public_state()['graveyard'][0]['nickname'], 'M2')
        self.assertEqual(self.overlay.public_state('Antiguos')['graveyard'][0]['nickname'], 'M1')
        self.assertEqual(self.overlay.public_state('No existe')['graveyard'][0]['nickname'], 'M2')
