"""Un hueco que falla al convertirse no debe congelar los demás ni dejar a un muerto en color."""
import tempfile
import threading
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from tracker import layout_export
from tracker.layout_export import PartyLayoutExporter


def png(color):
    out = BytesIO()
    Image.new('RGBA', (4, 4), color).save(out, format='PNG')
    return out.getvalue()


def is_gray(data):
    with Image.open(BytesIO(data)) as image:
        return all(r == g == b for r, g, b, a in image.convert('RGBA').getdata() if a)


class FakeService:
    def __init__(self, party, deaths=None):
        self.party = party
        self.deaths = deaths or {}
        self.condition = threading.Condition()

    def snapshot(self):
        return {'party': self.party, 'progress': {'deaths': self.deaths}, 'stale': False}


def mon(species, ec):
    return {'species_id': species, 'form': 0, 'origin_version': 33, 'encryption_constant': ec}


class LayoutResilienceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.cache = root / 'cache'
        self.cache.mkdir()
        (self.cache / '25.png').write_bytes(png((250, 200, 10, 255)))
        (self.cache / '4.png').write_bytes(png((240, 90, 20, 255)))
        self.root = root

    def tearDown(self):
        self.temp.cleanup()

    def exporter(self, service):
        exp = PartyLayoutExporter(service, self.root / 'layout', cache_dir=self.cache,
                                  custom_dir=self.root / 'custom',
                                  downloader=lambda ident: (_ for _ in ()).throw(OSError()))
        self.addCleanup(exp.close)
        return exp

    def test_failing_slot_does_not_block_following_slots(self):
        service = FakeService([mon(25, 1), mon(4, 2)] + [None] * 4)
        exp = self.exporter(service)
        real = exp.publish

        def flaky(index, *args, **kwargs):
            if index == 0:
                raise ValueError('conversión imposible')
            return real(index, *args, **kwargs)

        with patch.object(exp, 'publish', side_effect=flaky):
            exp.refresh()
        self.assertEqual((exp.directory / 'pokemon_2.png').read_bytes(), (self.cache / '4.png').read_bytes())
        self.assertIn('conversión imposible', exp.last_error or '')
        # A later clean cycle clears the stale diagnostic.
        exp.refresh()
        self.assertIsNone(exp.last_error)

    def test_dead_pokemon_falls_back_to_static_gray_when_animation_fails(self):
        service = FakeService([mon(25, 1)] + [None] * 5, deaths={'33:1': {}})
        exp = self.exporter(service)
        with patch.object(exp, 'custom_media', return_value=(b'GIF89a-roto', 'gif')), \
                patch.object(layout_export, 'gif_to_outputs', side_effect=ValueError('GIF enorme')):
            exp.refresh()
        self.assertTrue(is_gray((exp.directory / 'pokemon_1.png').read_bytes()))
        self.assertEqual((exp.directory / 'pokemon_1.media').read_text(encoding='ascii'), 'png')


if __name__ == '__main__':
    unittest.main()
