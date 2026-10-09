"""Animated sprite regressions: GIF/Pokédex naming, OBS slots, grayscale all frames."""
from io import BytesIO
from pathlib import Path
import tempfile
import threading
import unittest

from PIL import Image

from tracker.layout_export import (
    BLANK_PNG, PartyLayoutExporter, blank_sprite, custom_media_names,
    gif_to_outputs, validate_gif
)


def sprite_png(rgba):
    buffer = BytesIO()
    Image.new('RGBA', (8, 8), rgba).save(buffer, format='PNG')
    return buffer.getvalue()


def animated_gif():
    frames = [
        Image.new('RGBA', (8, 8), (240, 15, 30, 255)),
        Image.new('RGBA', (8, 8), (25, 230, 235, 255)),
    ]
    result = BytesIO()
    frames[0].save(result, format='GIF', save_all=True,
                   append_images=frames[1:], duration=[110, 220], loop=0,
                   disposal=2)
    return result.getvalue()


class FakeService:
    def __init__(self):
        self.party = [None] * 6
        self.deaths = {}
        self.condition = threading.Condition()

    def snapshot(self):
        return {
            'party': self.party,
            'progress': {'deaths': self.deaths},
            'stale': False,
        }


class AnimatedLayoutTests(unittest.TestCase):
    def test_source_gif_converts_to_looping_grayscale_keeping_frames(self):
        source = animated_gif()
        original_png, original_gif = gif_to_outputs(source)
        grayscale_png, grayscale_gif = gif_to_outputs(source, dead=True)
        with Image.open(BytesIO(original_gif)) as alive, \
             Image.open(BytesIO(grayscale_gif)) as dead:
            self.assertEqual(alive.n_frames, 2)
            self.assertEqual(dead.n_frames, 2)
            self.assertEqual(dead.info.get('loop'), 0)
            self.assertEqual([alive.seek(i) or alive.info.get('duration') for i in range(2)], [110, 220])
            self.assertEqual([dead.seek(i) or dead.info.get('duration') for i in range(2)], [110, 220])
            for i in range(2):
                dead.seek(i)
                r, g, b, alpha = dead.convert('RGBA').getpixel((0, 0))
                self.assertEqual((r, g), (g, b))
                self.assertEqual(alpha, 255)
            self.assertNotEqual(original_png, grayscale_png)

    def test_six_stable_gifs_and_pngs_refresh_on_swap_and_death(self):
        animated = animated_gif()
        normal = sprite_png((5, 160, 30, 255))
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            custom = root/'sprites_personalizados'
            custom.mkdir()
            (custom/'25.gif').write_bytes(animated)
            (custom/'25.png').write_bytes(sprite_png((1, 2, 3, 255)))
            cache = root/'cache'
            cache.mkdir()
            (cache/'94.png').write_bytes(normal)
            service = FakeService()
            service.party[0] = {'species_id': 25, 'origin_version':33,
                                'encryption_constant':17}
            exporter = PartyLayoutExporter(service, root/'layout',
                                            custom_dir=custom, cache_dir=cache)
            try:
                exporter.refresh()
                self.assertEqual(len(list(exporter.directory.glob('pokemon_*.png'))), 6)
                self.assertEqual(len(list(exporter.directory.glob('pokemon_*.gif'))), 6)
                target = exporter.directory/'pokemon_1.gif'
                static = exporter.directory/'pokemon_1.png'
                with Image.open(target) as source:
                    self.assertEqual(source.n_frames, 2)
                with Image.open(static) as preview:
                    self.assertEqual(preview.n_frames, 1)
                before = target.read_bytes()
                exporter.refresh()
                self.assertEqual(target.read_bytes(), before)
                service.deaths['33:17'] = {'pokemon': service.party[0]}
                exporter.refresh()
                with Image.open(target) as gray:
                    self.assertEqual(gray.n_frames, 2)
                    for i in range(2):
                        gray.seek(i)
                        r, g, b, _ = gray.convert('RGBA').getpixel((0, 0))
                        self.assertEqual(r, g)
                        self.assertEqual(g, b)
                self.assertEqual((custom/'25.gif').read_bytes(), animated)
                service.deaths.clear()
                exporter.refresh()
                with Image.open(target) as restored:
                    self.assertEqual(restored.n_frames, 2)
                    rgb = restored.convert('RGB').getpixel((0,0))
                    self.assertNotEqual(rgb[0], rgb[1])
                service.party[0] = {'species_id': 94}
                exporter.refresh()
                with Image.open(target) as single:
                    self.assertEqual(single.n_frames, 1)
                self.assertEqual(static.read_bytes(), normal)
                service.party[0] = None
                exporter.refresh()
                self.assertEqual(static.read_bytes(), BLANK_PNG)
                with Image.open(target) as empty:
                    self.assertEqual(empty.n_frames, 1)
                self.assertEqual((custom/'25.png').read_bytes(), sprite_png((1,2,3,255)))
            finally:
                exporter.close()

    def test_alola_gif_takes_priority_and_invalid_falls_back_to_png(self):
        names = custom_media_names({'species_id': 37, 'form':1}, 10103)
        self.assertEqual(names, ('37-alola.gif', '10103.gif',
                                 '37-alola.png', '10103.png'))
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root/'sprites_personalizados'
            source.mkdir()
            (source/'37-alola.png').write_bytes(sprite_png((0, 200, 150, 255)))
            (source/'37-alola.gif').write_bytes(b'GIF89aBROKEN')
            service = FakeService()
            service.party[0] = {'species_id':37, 'form':1}
            exporter = PartyLayoutExporter(service, root/'layout',
                                            custom_dir=source, cache_dir=root/'cache')
            try:
                exporter.refresh()
                with Image.open(exporter.directory/'pokemon_1.gif') as output:
                    self.assertEqual(output.n_frames, 1)
                (source/'37-alola.gif').write_bytes(animated_gif())
                exporter.refresh()
                with Image.open(exporter.directory/'pokemon_1.gif') as output:
                    self.assertEqual(output.n_frames, 2)
            finally:
                exporter.close()

    def test_reject_oversized_and_corrupt_animations(self):
        with self.assertRaises(ValueError):
            validate_gif(b'GIF89a' + b'\0' * 5000000)
        with self.assertRaises(ValueError):
            validate_gif(b'GIF89a' + b'\0' * 24)


if __name__ == '__main__':
    unittest.main()
