"""Iconos de objetos para OBS: tabla local, caché y descargas acotadas."""
import http.client
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

from server import make_handler
from tracker.item_sprites import ItemSprites
from tracker.layout_export import blank_sprite
from tracker.overlay import OverlayManager
from tracker.service import TrackerService

PNG = blank_sprite(24)


class ItemSpriteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.calls = []

        def downloader(slug):
            self.calls.append(slug)
            if slug == 'missing-item':
                raise OSError('404')
            return PNG
        self.sprites = ItemSprites(Path(self.temp.name) / 'cache', downloader=downloader)

    def tearDown(self):
        self.temp.cleanup()

    def test_real_items_resolve_to_pokeapi_names(self):
        self.assertEqual(self.sprites.slug(234), 'leftovers')       # Restos
        self.assertEqual(self.sprites.slug(287), 'choice-scarf')    # Pañuelo Elección
        self.assertEqual(self.sprites.slug(776), 'normalium-z--held')
        self.assertEqual(self.sprites.slug(234, generation=6), 'leftovers')
        for bad in (0, -1, 99999, '234', None, True):
            self.assertIsNone(self.sprites.slug(bad))

    def test_download_once_then_serve_from_cache(self):
        self.assertEqual(self.sprites.png(234), PNG)
        self.assertEqual(self.sprites.png(234), PNG)
        self.assertEqual(self.calls, ['leftovers'])
        self.assertTrue((Path(self.temp.name) / 'cache' / 'items' / 'leftovers.png').is_file())

    def test_failed_download_is_not_retried_immediately(self):
        self.sprites.mapping['1999'] = 'missing-item'
        self.assertIsNone(self.sprites.png(1999))
        self.assertIsNone(self.sprites.png(1999))
        self.assertEqual(self.calls, ['missing-item'])

    def test_missing_icon_does_not_pause_other_downloads(self):
        from urllib.error import HTTPError
        def downloader(slug):
            self.calls.append(slug)
            if slug == 'leftovers':
                raise HTTPError('u', 404, 'Not Found', {}, None)
            return PNG
        self.sprites.downloader = downloader
        self.assertIsNone(self.sprites.png(234))
        self.assertEqual(self.sprites.png(287), PNG)

    def test_network_failure_pauses_all_downloads(self):
        def offline(slug):
            self.calls.append(slug)
            raise OSError('sin red')
        self.sprites.downloader = offline
        self.assertIsNone(self.sprites.png(234))
        self.assertIsNone(self.sprites.png(287))
        self.assertEqual(self.calls, ['leftovers'])

    def test_read_only_share_serves_cache_but_never_downloads(self):
        remote = ItemSprites(Path(self.temp.name) / 'cache', downloader=lambda s: self.calls.append(s) or PNG,
                             allow_download=False)
        self.assertIsNone(remote.png(234))
        self.assertEqual(self.calls, [])
        self.sprites.png(234)  # local overlay fills the cache
        self.assertEqual(remote.png(234), PNG)

    def test_unknown_item_never_downloads(self):
        self.assertIsNone(self.sprites.png(0))
        self.assertEqual(self.calls, [])


class OverlayItemIconRouteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        cache = root / 'sprite-cache'
        (cache / 'items').mkdir(parents=True)
        (cache / 'items' / 'leftovers.png').write_bytes(PNG)
        self.service = TrackerService(root / 'runtime' / 'state.json')
        (root / 'layout').mkdir()
        overlay = OverlayManager(self.service, root / 'runtime', root / 'layout')
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(
            self.service, 'tok', overlay=overlay, sprite_cache=cache))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.service.stop.set()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def get(self, path):
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=10)
        conn.request('GET', path)
        response = conn.getresponse()
        data = response.read()
        conn.close()
        return response.status, response.getheader('Content-Type'), data

    def test_cached_icon_is_served_and_bad_ids_are_404(self):
        status, kind, data = self.get('/overlay/item/234.png')
        self.assertEqual((status, kind, data), (200, 'image/png', PNG))
        for path in ('/overlay/item/0.png', '/overlay/item/abc.png', '/overlay/item/../x.png',
                     '/overlay/item/234.gif'):
            self.assertEqual(self.get(path)[0], 404, path)

    def test_public_state_carries_item_id_for_the_icon(self):
        mon = {'species_id': 25, 'nickname': 'Chispa', 'hp': 1, 'max_hp': 2, 'encryption_constant': 1,
               'origin_version': 33, 'item_id': 234, 'item': 'Restos'}
        self.service.update(party=[mon] + [None] * 5, stale=False)
        status, _, data = self.get('/api/overlay/public')
        import json
        slot = json.loads(data)['party'][0]
        self.assertEqual((slot['item'], slot['item_id']), ('Restos', 234))


if __name__ == '__main__':
    unittest.main()
