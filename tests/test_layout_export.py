"""Layout PNG update contract for OBS: stable slots, empty transparency, cached sprite."""
import tempfile
import time
import unittest
from pathlib import Path
from io import BytesIO
from PIL import Image
from unittest.mock import patch
import threading

from tracker.layout_export import (
    BLANK_PNG, PartyLayoutExporter, blank_sprite, layout_directory, sprite_id, validate_png
)
from desktop import automatic_profile


class FakeService:
    def __init__(self, party=None):
        self.party = list(party or [None] * 6)
        self.condition = threading.Condition()

    def snapshot(self):
        return {'party': self.party, 'stale': False}


class LayoutTests(unittest.TestCase):
    def test_six_png_slots_exist_immediately_even_if_party_empty(self):
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root) / 'layout'
            exp = PartyLayoutExporter(FakeService(), folder,
                                      cache_dir=Path(root)/'cache')
            try:
                self.assertEqual(sorted(p.name for p in folder.glob('pokemon_*.png')),
                                 [f'pokemon_{n}.png' for n in range(1, 7)])
                self.assertTrue(all((folder/f'pokemon_{n}.png').read_bytes() == BLANK_PNG
                                    for n in range(1, 7)))
                self.assertEqual(len(validate_png(BLANK_PNG)), len(BLANK_PNG))
            finally:
                exp.close()

    def test_swap_replaces_only_target_position_and_disconnect_keeps_last(self):
        first = {'species_id': 94, 'form': 0}
        second = {'species_id': 151, 'form': 0}
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root)
            cache = folder / 'cache'
            cache.mkdir()
            spr_94, spr_151 = blank_sprite(4), blank_sprite(6)
            (cache/'94.png').write_bytes(spr_94)
            (cache/'151.png').write_bytes(spr_151)
            service = FakeService([first, None, None, None, None, None])
            exporter = PartyLayoutExporter(service, folder/'layout', cache_dir=cache)
            try:
                exporter.refresh()
                self.assertEqual((exporter.directory/'pokemon_1.png').read_bytes(), spr_94)
                service.party[0] = second
                exporter.refresh()
                self.assertEqual((exporter.directory/'pokemon_1.png').read_bytes(), spr_151)
                # With emulator disconnected, service retains its last party.
                service.stale = True
                exporter.refresh()
                self.assertEqual((exporter.directory/'pokemon_1.png').read_bytes(), spr_151)
                service.party[0] = None
                exporter.refresh()
                self.assertEqual((exporter.directory/'pokemon_1.png').read_bytes(), BLANK_PNG)
            finally:
                exporter.close()

    def test_alola_sprite_and_async_download(self):
        self.assertEqual(sprite_id({'species_id':37,'form':1}),10103)
        self.assertEqual(sprite_id({'species_id':38,'form':1}),10104)
        self.assertEqual(sprite_id({'species_id':38,'form':0}),38)
        self.assertIsNone(sprite_id({'species_id':38,'egg':True}))
        with tempfile.TemporaryDirectory() as root:
            service = FakeService([{'species_id':37,'form':1}]+[None]*5)
            seen = []
            def download(ident):
                seen.append(ident)
                return blank_sprite(12)
            exp = PartyLayoutExporter(service, Path(root)/'layout',
                                      cache_dir=Path(root)/'cache', downloader=download)
            try:
                exp.refresh()
                self.assertEqual((exp.directory/'pokemon_1.png').read_bytes(), BLANK_PNG)
                for _ in range(100):
                    exp.refresh()
                    if (exp.directory/'pokemon_1.png').read_bytes() != BLANK_PNG:
                        break
                    time.sleep(.02)
                self.assertEqual(seen, [10103])
                self.assertEqual((exp.directory/'pokemon_1.png').read_bytes(),blank_sprite(12))
                self.assertTrue((Path(root)/'cache'/'10103.png').is_file())
            finally:
                exp.close()

    def test_custom_png_precedence_live_replacement_and_gray_on_death(self):
        from tracker.layout_export import grayscale_png
        def png(color):
            src = Image.new('RGBA', (2, 2), color)
            data = BytesIO()
            src.save(data, format='PNG')
            return data.getvalue()
        custom_red = png((240, 40, 10, 128))
        custom_blue = png((20, 40, 220, 128))
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            custom_dir = folder / 'sprites_personalizados'
            custom_dir.mkdir()
            cache = folder / 'cache'
            cache.mkdir()
            normal = png((10, 220, 10, 255))
            (cache/'25.png').write_bytes(normal)
            mon = {'species_id':25, 'form':0, 'origin_version':33,
                   'encryption_constant':8123}
            service = FakeService([mon]+[None]*5)
            service.progress = {'deaths': {}}
            original_snapshot = service.snapshot
            service.snapshot = lambda: {**original_snapshot(),
                                        'progress': service.progress}
            exporter = PartyLayoutExporter(
                service, folder/'layout', cache_dir=cache, custom_dir=custom_dir)
            target = exporter.directory/'pokemon_1.png'
            try:
                exporter.refresh()
                self.assertEqual(target.read_bytes(), normal)
                custom = custom_dir/'25.png'
                custom.write_bytes(custom_red)
                exporter.refresh()
                self.assertEqual(target.read_bytes(), custom_red)
                service.progress['deaths']['33:8123'] = {'pokemon': mon}
                exporter.refresh()
                gray_data = target.read_bytes()
                self.assertEqual(gray_data, grayscale_png(custom_red))
                with Image.open(BytesIO(gray_data)) as gray:
                    r, g, b, a = gray.getpixel((0,0))
                    self.assertEqual(r, g)
                    self.assertEqual(g, b)
                    self.assertEqual(a, 128)
                self.assertEqual(custom.read_bytes(), custom_red)
                custom.write_bytes(custom_blue)
                exporter.refresh()
                self.assertEqual(target.read_bytes(), grayscale_png(custom_blue))
                del service.progress['deaths']['33:8123']
                exporter.refresh()
                self.assertEqual(target.read_bytes(), custom_blue)
                custom.unlink()
                exporter.refresh()
                self.assertEqual(target.read_bytes(), normal)
            finally:
                exporter.close()

    def test_alola_filename_and_fallback_without_network(self):
        from tracker.layout_export import custom_names
        mon = {'species_id':37, 'form':1}
        self.assertEqual(custom_names(mon, 10103),
                         ('37-alola.png', '10103.png'))
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            custom = folder / 'sprites_personalizados'
            custom.mkdir()
            png = blank_sprite(13)
            (custom/'10103.png').write_bytes(png)
            service = FakeService([mon]+[None]*5)
            exp = PartyLayoutExporter(service, folder/'layout',
                                      custom_dir=custom, cache_dir=folder/'cache')
            try:
                exp.refresh()
                self.assertEqual((exp.directory/'pokemon_1.png').read_bytes(),png)
                (custom/'37-alola.png').write_bytes(blank_sprite(14))
                exp.refresh()
                self.assertEqual((exp.directory/'pokemon_1.png').read_bytes(),blank_sprite(14))
            finally:
                exp.close()

    def test_layout_is_near_exe_and_profiles_never_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            exe = Path(temp)/'PokemonTracker.exe'
            root = layout_directory(Path(temp)/'user',executable=exe,frozen=True)
            second = layout_directory(Path(temp)/'user','segundo-jugador',
                                      executable=exe,frozen=True)
            self.assertEqual(root,(Path(temp)/'layout').resolve())
            self.assertEqual(second,root/'perfil_2')

    def test_second_window_automatically_uses_existing_profile(self):
        calls=[]
        def locking(home,profile):
            calls.append(profile)
            if profile=='principal':
                raise RuntimeError('Primera ventana abierta')
            return 'other-lock'
        with patch('desktop.acquire_profile_lock',side_effect=locking):
            self.assertEqual(automatic_profile('/tmp'),('segundo-jugador','other-lock'))
        self.assertEqual(calls,['principal','segundo-jugador'])


if __name__ == '__main__':
    unittest.main()
