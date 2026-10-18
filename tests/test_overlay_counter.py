import base64
import io
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from tracker.overlay import DEFAULT, OverlayManager, validated_settings


class OverlayCounterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.service = SimpleNamespace(condition=threading.Condition(), state={
            'party': [], 'progress': {'deaths': {'a': {}}, 'death_count': 4},
            'stale': False,
        })
        self.manager = OverlayManager(self.service, self.root, self.root/'layout')

    def test_counter_settings_persist_and_validate(self):
        settings = {**DEFAULT, 'counter_mode': 'lives', 'counter_total': 10,
                    'counter_lost': 'hide', 'counter_in_composition': True,
                    'counter_custom_icon': True, 'counter_icon_size': 48}
        self.manager.set_settings(settings)
        again = OverlayManager(self.service, self.root, self.root/'layout')
        self.assertEqual(again.get_settings(), settings)
        self.assertEqual(validated_settings({})['counter_mode'], 'off')
        for name, value in [('counter_total', 0), ('counter_total', 101),
                            ('counter_total', True), ('counter_icon_size', 11),
                            ('counter_icon_size', 257), ('counter_mode', 'both'),
                            ('counter_lost', 'remove'), ('counter_in_composition', 1),
                            ('counter_custom_icon', 'true')]:
            with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                validated_settings({name: value})
        for total in (1, 100):
            self.assertEqual(validated_settings({'counter_total': total})['counter_total'], total)

    def test_durable_death_count_and_legacy_fallback(self):
        public = self.manager.public_state()
        self.assertEqual(public['death_count'], 4)
        self.assertNotIn('progress', public)
        self.assertNotIn('a', public)
        # Reviving without decrement keeps a death despite an empty cemetery.
        self.service.state['progress']['deaths'] = {}
        self.assertEqual(self.manager.public_state()['death_count'], 4)
        for invalid in (None, -1, True, '4'):
            self.service.state['progress'] = {'deaths': {'a': {}, 'b': {}}, 'death_count': invalid}
            self.assertEqual(self.manager.public_state()['death_count'], 2)
        self.service.state['progress']['death_count'] = 0
        self.assertEqual(self.manager.public_state()['death_count'], 0)
        # Legacy snapshot services use the same semantics as the locked path.
        legacy = SimpleNamespace(snapshot=lambda: self.service.state)
        self.assertEqual(OverlayManager(legacy, self.root, self.root).public_state()['death_count'], 0)

    def test_counter_icon_round_trip_and_invalid_upload_preserves_icon(self):
        self.assertIsNone(self.manager.counter_icon_bytes())
        self.assertEqual(self.manager.counter_icon_version(), '0')
        output = io.BytesIO()
        Image.new('RGBA', (32, 32), (5, 50, 90, 128)).save(output, format='PNG')
        data = base64.b64encode(output.getvalue()).decode()
        info = self.manager.import_counter_icon(data)
        self.assertEqual((info['kind'], info['width'], info['height']), ('counter', 32, 32))
        saved = self.manager.counter_icon_bytes()
        self.assertNotEqual(self.manager.counter_icon_version(), '0')
        with Image.open(io.BytesIO(saved)) as image:
            self.assertEqual(image.getpixel((0, 0)), (5, 50, 90, 128))
        again = OverlayManager(self.service, self.root, self.root/'layout')
        self.assertEqual(again.counter_icon_bytes(), saved)
        for invalid in ('!!', base64.b64encode(b'<svg/>').decode(), None):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                self.manager.import_counter_icon(invalid)
            self.assertEqual(self.manager.counter_icon_bytes(), saved)
        animated = io.BytesIO()
        Image.new('RGBA', (8, 8), 'red').save(animated, format='PNG', save_all=True,
            append_images=[Image.new('RGBA', (8, 8), 'blue')], duration=100, loop=0)
        with self.assertRaises(ValueError):
            self.manager.import_counter_icon(base64.b64encode(animated.getvalue()).decode())
        self.assertEqual(self.manager.counter_icon_bytes(), saved)


if __name__ == '__main__':
    unittest.main()
