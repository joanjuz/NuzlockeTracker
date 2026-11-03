"""OBS: conjuntos de sprites por subcarpeta, iconos de objetos propios y cementerio."""
import base64
import io
import json
import tempfile
import threading
import unittest
from pathlib import Path

from PIL import Image

from tracker import custom_sprites
from tracker.item_sprites import ItemSprites
from tracker.layout_export import BLANK_PNG, PartyLayoutExporter
from tracker.overlay import DEFAULT, OverlayManager, validated_settings
from tracker.service import TrackerService


def png(color, size=4):
    out = io.BytesIO()
    Image.new('RGBA', (size, size), color).save(out, format='PNG')
    return out.getvalue()


RED, BLUE, GREEN = png((250, 0, 0, 255)), png((0, 0, 250, 255)), png((0, 250, 0, 255))


class FakeService:
    def __init__(self, party=None, progress=None):
        self.party = party or [None] * 6
        self.progress = progress or {'deaths': {}}
        self.condition = threading.Condition()

    def snapshot(self):
        return {'party': self.party, 'progress': self.progress, 'stale': False}


class SpriteSetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.custom = self.root / 'sprites_personalizados'
        (self.custom / 'HD').mkdir(parents=True)
        (self.custom / 'Pixel Art').mkdir()
        (self.custom / 'objetos').mkdir()
        (self.custom / '.oculta').mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def test_sets_are_real_subfolders_excluding_items_and_invalid_names(self):
        self.assertEqual(custom_sprites.list_sets(self.custom), ['HD', 'Pixel Art'])
        for bad in ('', '../x', 'objetos', 'OBJETOS', ' HD', 'a/b', 'x' * 41, None, 3):
            self.assertFalse(custom_sprites.valid_set_name(bad), bad)
        self.assertIsNone(custom_sprites.set_directory(self.custom, '..'))

    def test_selected_set_wins_and_root_is_the_fallback(self):
        (self.custom / '25.png').write_bytes(RED)
        (self.custom / 'HD' / '25.png').write_bytes(BLUE)
        (self.custom / '4.png').write_bytes(GREEN)  # only in root
        chosen = {'value': 'HD'}
        exporter = PartyLayoutExporter(FakeService(), self.root / 'layout', cache_dir=self.root / 'cache',
                                       custom_dir=self.custom, sprite_set=lambda: chosen['value'])
        self.addCleanup(exporter.close)
        pika = {'species_id': 25, 'form': 0}
        self.assertEqual(exporter.custom_media(pika, 25)[0], BLUE)
        self.assertEqual(exporter.custom_media({'species_id': 4, 'form': 0}, 4)[0], GREEN)
        chosen['value'] = ''
        self.assertEqual(exporter.custom_media(pika, 25)[0], RED)
        chosen['value'] = 'NoExiste'
        self.assertEqual(exporter.custom_media(pika, 25)[0], RED)

    def test_settings_validate_and_require_an_existing_set(self):
        self.assertEqual(validated_settings({**DEFAULT, 'sprite_set': 'HD'})['sprite_set'], 'HD')
        for bad in ('../HD', 'objetos', 5):
            with self.assertRaises(ValueError):
                validated_settings({**DEFAULT, 'sprite_set': bad})
        service = TrackerService(self.root / 'runtime' / 'state.json')
        manager = OverlayManager(service, self.root / 'runtime', self.root / 'layout', custom_dir=self.custom)
        self.assertEqual(manager.set_settings({**DEFAULT, 'sprite_set': 'Pixel Art'})['sprite_set'], 'Pixel Art')
        with self.assertRaises(ValueError):
            manager.set_settings({**DEFAULT, 'sprite_set': 'Fantasma'})
        self.assertEqual(manager.sprite_sets()['sets'], ['HD', 'Pixel Art'])

    def test_import_into_new_set_and_items_folder_stays_inside(self):
        service = TrackerService(self.root / 'runtime' / 'state.json')
        manager = OverlayManager(service, self.root / 'runtime', self.root / 'layout', custom_dir=self.custom)
        data = base64.b64encode(RED).decode()
        result = manager.import_sprite('25.png', data, sprite_set='Shiny')
        self.assertEqual(result['path_hint'], 'sprites_personalizados/Shiny')
        self.assertEqual((self.custom / 'Shiny' / '25.png').read_bytes(), RED)
        item = manager.import_item_sprite('Restos.png', data, sprite_set='HD')
        self.assertEqual(item['name'], 'restos.png')
        self.assertTrue((self.custom / 'HD' / 'objetos' / 'restos.png').is_file())
        for name, chosen in (('../x.png', ''), ('25.png', '../fuera'), ('25.svg', ''), ('25.png', 'objetos')):
            with self.assertRaises(ValueError):
                manager.import_sprite(name, data, sprite_set=chosen)
        self.assertFalse((self.root / 'fuera').exists())


class CustomItemIconTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.custom = root / 'sprites_personalizados'
        (self.custom / 'objetos').mkdir(parents=True)
        (self.custom / 'HD' / 'objetos').mkdir(parents=True)
        self.chosen = {'value': ''}
        self.downloads = []
        self.icons = ItemSprites(root / 'cache', downloader=lambda s: self.downloads.append(s) or BLANK_PNG,
                                 custom_root=self.custom, sprite_set=lambda: self.chosen['value'],
                                 name_lookup=lambda i: {234: 'Restos', 287: 'Pañuelo Elección'}.get(i))

    def tearDown(self):
        self.temp.cleanup()

    def test_custom_icon_by_number_english_or_spanish_name(self):
        (self.custom / 'objetos' / '234.png').write_bytes(RED)
        self.assertEqual(self.icons.icon(234), (RED, 'image/png'))
        (self.custom / 'objetos' / '234.png').unlink()
        (self.custom / 'objetos' / 'Leftovers.PNG').write_bytes(BLUE)
        self.assertEqual(self.icons.icon(234)[0], BLUE)
        (self.custom / 'objetos' / 'panuelo-eleccion.png').write_bytes(GREEN)
        self.assertEqual(self.icons.icon(287)[0], GREEN)
        self.assertEqual(self.downloads, [])

    def test_set_icon_wins_then_pokeapi_when_none(self):
        (self.custom / 'objetos' / 'restos.png').write_bytes(RED)
        (self.custom / 'HD' / 'objetos' / 'restos.png').write_bytes(BLUE)
        self.chosen['value'] = 'HD'
        self.assertEqual(self.icons.icon(234)[0], BLUE)
        self.assertEqual(self.icons.icon(220), (BLANK_PNG, 'image/png'))  # Cinta Elección: PokeAPI
        self.assertEqual(self.downloads, ['choice-band'])


class GraveyardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.service = TrackerService(self.root / 'runtime' / 'state.json')
        (self.root / 'layout').mkdir()
        self.manager = OverlayManager(self.service, self.root / 'runtime', self.root / 'layout')

    def tearDown(self):
        self.temp.cleanup()

    def kill(self, ec, nickname, when, species_id=25, level=30):
        mon = {'species_id': species_id, 'species': 'Pikachu', 'nickname': nickname, 'level': level,
               'met_location': 'Ruta 1', 'encryption_constant': ec, 'origin_version': 33,
               'checksum_valid': True, 'hp': 0, 'max_hp': 50}
        self.service.progress.data['deaths'][f'33:{ec}'] = {'pokemon': mon, 'recorded_at': when}

    def test_graveyard_is_newest_first_bounded_and_private(self):
        self.kill(1, 'Primero', '2026-01-01T00:00:00')
        self.kill(2, '<b>Segundo</b>', '2026-02-01T00:00:00', level=55)
        for i in range(70):
            self.kill(100 + i, f'M{i}', '2025-01-01T00:00:%02d' % (i % 60))
        self.service.update()
        public = self.manager.public_state()
        graveyard = public['graveyard']
        self.assertEqual(len(graveyard), 60)
        self.assertEqual([g['nickname'] for g in graveyard[:2]], ['<b>Segundo</b>', 'Primero'])
        self.assertEqual(graveyard[0]['level'], 55)
        self.assertEqual(graveyard[0]['route'], 'Ruta 1')
        raw = json.dumps(public)
        self.assertNotIn('encryption_constant', raw)
        self.assertNotIn('33:2', raw)
        self.assertEqual(self.manager.graveyard_entry(0)['nickname'], '<b>Segundo</b>')
        self.assertIsNone(self.manager.graveyard_entry(60))
        self.assertIsNone(self.manager.graveyard_entry(-1))
        rev = graveyard[1]['image_rev']
        self.assertEqual(self.manager.graveyard_entry_for(rev)['nickname'], 'Primero')
        for bad in ('../x', 'ZZZZZZZZZZZZ', '', None, graveyard[0]['image_rev'][:-1]):
            self.assertIsNone(self.manager.graveyard_entry_for(bad))

    def test_sprite_for_uses_custom_then_cache_then_downloads_without_blocking(self):
        cache = self.root / 'cache'
        cache.mkdir()
        (cache / '4.png').write_bytes(GREEN)
        calls = []
        exporter = PartyLayoutExporter(FakeService(), self.root / 'layout2', cache_dir=cache,
                                       custom_dir=self.root / 'custom', bundled=self.root / 'none',
                                       downloader=lambda i: calls.append(i) or RED)
        self.addCleanup(exporter.close)
        self.assertEqual(exporter.sprite_for({'species_id': 4, 'form': 0}), (GREEN, 'png'))
        self.assertIsNone(exporter.sprite_for({'species_id': 7, 'form': 0}))  # download scheduled
        exporter.futures[7].result(timeout=5)
        self.assertEqual(exporter.sprite_for({'species_id': 7, 'form': 0}), (RED, 'png'))
        self.assertEqual(calls, [7])


if __name__ == '__main__':
    unittest.main()


class ObsRoutesTests(unittest.TestCase):
    """HTTP: sprite sets, custom item icons and graveyard images (local and VPN)."""

    def setUp(self):
        import http.client  # noqa: F401  (used in helpers)
        from http.server import ThreadingHTTPServer
        from server import make_handler
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.custom = root / 'sprites_personalizados'
        (self.custom / 'HD').mkdir(parents=True)
        self.service = TrackerService(root / 'runtime' / 'state.json')
        (root / 'layout').mkdir()
        self.overlay = OverlayManager(self.service, root / 'runtime', root / 'layout', custom_dir=self.custom)
        self.layout = PartyLayoutExporter(self.service, root / 'layout', cache_dir=root / 'cache',
                                          custom_dir=self.custom, sprite_set=self.overlay.selected_sprite_set,
                                          downloader=lambda i: (_ for _ in ()).throw(OSError('sin red')))
        self.servers = []
        for remote in (False, True):
            server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(
                self.service, 'tok', overlay=self.overlay, remote_only=remote,
                sprite_cache=root / 'cache', layout=self.layout))
            threading.Thread(target=server.serve_forever, daemon=True).start()
            self.servers.append(server)

    def tearDown(self):
        self.service.stop.set()
        for server in self.servers:
            server.shutdown()
            server.server_close()
        self.layout.close()
        self.temp.cleanup()

    def call(self, method, path, payload=None, remote=False):
        import http.client
        conn = http.client.HTTPConnection('127.0.0.1', self.servers[remote].server_port, timeout=10)
        headers = {'X-Tracker-Token': 'tok', 'Content-Type': 'application/json'} if payload is not None else {}
        conn.request(method, path, json.dumps(payload) if payload is not None else None, headers)
        response = conn.getresponse()
        data = response.read()
        conn.close()
        return response.status, response.getheader('Content-Type'), data

    def test_sets_import_and_selection_over_http(self):
        self.assertEqual(json.loads(self.call('GET', '/api/overlay/sprite-sets')[2])['sets'], ['HD'])
        data = base64.b64encode(RED).decode()
        status, _, body = self.call('POST', '/api/overlay/sprite', {'name': '25.png', 'data': data, 'sprite_set': 'Nuevo'})
        self.assertEqual(status, 200, body)
        self.assertEqual(json.loads(self.call('GET', '/api/overlay/sprite-sets')[2])['sets'], ['HD', 'Nuevo'])
        self.assertEqual(self.call('POST', '/api/overlay/sprite', {'name': '25.png', 'data': data, 'sprite_set': '../x'})[0], 400)
        # Read-only VPN share: no listing, no uploads.
        self.assertEqual(self.call('GET', '/api/overlay/sprite-sets', remote=True)[0], 404)
        self.assertEqual(self.call('POST', '/api/overlay/item-sprite', {'name': 'restos.png', 'data': data}, remote=True)[0], 403)

    def test_custom_item_icon_is_served_with_its_type(self):
        gif = io.BytesIO()  # animated: kept as GIF (a single frame is normalised to PNG)
        frames = [Image.new('RGBA', (4, 4), color) for color in ((0, 200, 0, 255), (200, 0, 0, 255))]
        frames[0].save(gif, format='GIF', save_all=True, append_images=frames[1:], loop=0, duration=100)
        data = base64.b64encode(gif.getvalue()).decode()
        status, _, body = self.call('POST', '/api/overlay/item-sprite', {'name': 'restos.gif', 'data': data})
        self.assertEqual(status, 200, body)
        status, kind, raw = self.call('GET', '/overlay/item/234.png')
        self.assertEqual((status, kind), (200, 'image/gif'))
        self.assertEqual(raw, gif.getvalue())

    def test_graveyard_image_by_stable_id_locally_and_over_vpn(self):
        (self.custom / 'HD' / '25.png').write_bytes(BLUE)
        (self.custom / '25.png').write_bytes(RED)
        mon = {'species_id': 25, 'species': 'Pikachu', 'nickname': 'Chispa', 'form': 0,
               'encryption_constant': 5, 'origin_version': 33}
        self.service.progress.data['deaths']['33:5'] = {'pokemon': mon, 'recorded_at': '2026-01-01'}
        self.service.update()
        rev = self.overlay.public_state()['graveyard'][0]['image_rev']
        self.assertEqual(self.call('GET', f'/overlay/graveyard/{rev}')[2], RED)
        self.overlay.set_settings({**self.overlay.get_settings(), 'sprite_set': 'HD'})
        self.assertEqual(self.call('GET', f'/overlay/graveyard/{rev}', remote=True)[2], BLUE)
        self.assertEqual(self.call('GET', '/overlay/graveyard/000000000000')[0], 404)
        self.assertEqual(self.call('GET', '/overlay/graveyard/../x')[0], 404)


class ReviewFixesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.custom = self.root / 'sprites_personalizados'
        (self.custom / 'HD').mkdir(parents=True)
        self.service = TrackerService(self.root / 'runtime' / 'state.json')
        (self.root / 'layout').mkdir()
        self.manager = OverlayManager(self.service, self.root / 'runtime', self.root / 'layout', custom_dir=self.custom)

    def tearDown(self):
        self.temp.cleanup()

    def kill(self, ec, when):
        mon = {'species_id': 25, 'nickname': f'M{ec}', 'encryption_constant': ec, 'origin_version': 33}
        self.service.progress.data['deaths'][f'33:{ec}'] = {'pokemon': mon, 'recorded_at': when}

    def test_public_id_is_not_a_plain_hash_of_the_encryption_constant(self):
        import hashlib
        self.kill(1234, '2026-01-01')
        self.service.update()
        rev = self.manager.public_state()['graveyard'][0]['image_rev']
        self.assertNotEqual(rev, hashlib.sha1(b'33:1234').hexdigest()[:12])
        self.assertEqual(rev, self.manager.public_state()['graveyard'][0]['image_rev'], 'estable en la sesión')
        other = OverlayManager(self.service, self.root / 'runtime', self.root / 'layout', custom_dir=self.custom)
        self.assertNotEqual(rev, other.public_state()['graveyard'][0]['image_rev'], 'clave distinta por proceso')

    def test_oldest_order_covers_all_deaths_and_lookup_finds_any(self):
        for i in range(80):
            self.kill(i, '2026-01-01T00:%02d:%02d' % (i // 60, i % 60))
        self.service.update()
        self.manager.set_settings({**self.manager.get_settings(), 'graveyard_order': 'oldest'})
        graveyard = self.manager.public_state()['graveyard']
        self.assertEqual([g['nickname'] for g in graveyard[:2]], ['M0', 'M1'])
        self.assertEqual(self.manager.graveyard_entry_for(graveyard[0]['image_rev'])['nickname'], 'M0')

    def test_set_names_are_case_insensitive_like_windows(self):
        data = base64.b64encode(RED).decode()
        self.assertEqual(self.manager.import_sprite('25.png', data, sprite_set='hd')['path_hint'],
                         'sprites_personalizados/HD')
        self.assertEqual(custom_sprites.list_sets(self.custom), ['HD'])
        self.assertEqual(self.manager.set_settings({**DEFAULT, 'sprite_set': 'hd'})['sprite_set'], 'HD')

    def test_upload_never_follows_a_junction(self):
        import subprocess
        import sys
        if sys.platform != 'win32':
            self.skipTest('uniones de directorio solo en Windows')
        outside = self.root / 'fuera'
        outside.mkdir()
        made = subprocess.run(['cmd', '/c', 'mklink', '/J', str(self.custom / 'Union'), str(outside)],
                              capture_output=True)
        if made.returncode != 0:
            self.skipTest('no se pudo crear la unión')
        data = base64.b64encode(RED).decode()
        with self.assertRaises(ValueError):
            self.manager.import_sprite('25.png', data, sprite_set='Union')
        self.assertEqual(list(outside.iterdir()), [])
        self.assertNotIn('Union', custom_sprites.list_sets(self.custom))

    def test_read_only_share_never_triggers_graveyard_downloads(self):
        calls = []
        exporter = PartyLayoutExporter(FakeService(), self.root / 'layout2', cache_dir=self.root / 'cache',
                                       custom_dir=self.custom, bundled=self.root / 'none',
                                       downloader=lambda i: calls.append(i) or RED)
        self.addCleanup(exporter.close)
        self.assertIsNone(exporter.sprite_for({'species_id': 7, 'form': 0}, download=False))
        self.assertEqual((calls, exporter.futures), ([], {}))


class LargeSetListingTests(unittest.TestCase):
    def test_listing_is_cached_until_the_folder_changes(self):
        import os
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            for i in range(1, 300):
                (folder / f'{i:03d}.png').write_bytes(b'x')
            self.assertIn('025.png', custom_sprites.listing(folder))
            with patch('tracker.custom_sprites.os.scandir', side_effect=AssertionError('relistado')):
                self.assertIn('025.png', custom_sprites.listing(folder))  # served from cache
            (folder / 'Nuevo.PNG').write_bytes(b'x')
            os.utime(folder, ns=(folder.stat().st_atime_ns, folder.stat().st_mtime_ns + 1_000_000))
            self.assertIn('nuevo.png', custom_sprites.listing(folder))
            self.assertIsNone(custom_sprites.find_file([folder], ['999.png']))
