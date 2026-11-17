"""Real Chromium geometry checks with isolated API/media fixtures (E2E=1).

No tracker runtime, profiles, emulator, or external image service is used.
These checks exercise browser-source rendering; they are not an OBS native test.
"""
from __future__ import annotations

import copy
import io
import json
import os
import threading
import unittest
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from tracker.overlay.settings import DEFAULT

try:
    from PIL import Image
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = Path(os.environ.get('E2E_ARTIFACTS') or ROOT / 'build/e2e-artifacts')


class QuietWebHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass


@unittest.skipUnless(os.environ.get('E2E') == '1' and sync_playwright,
                     'Requires E2E=1, Playwright Chromium and Pillow')
class OverlayGeometryBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0),
                                        partial(QuietWebHandler, directory=str(ROOT / 'web')))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f'http://127.0.0.1:{cls.server.server_port}'
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch()
        cls.media = {}
        for label, size, fmt in [('small', (32, 32), 'PNG'), ('hd', (256, 256), 'PNG'),
                                 ('wide', (256, 32), 'PNG'), ('gif', (64, 128), 'GIF'),
                                 ('webp', (128, 48), 'WEBP')]:
            image = Image.new('RGBA', size, '#ff4080')
            out = io.BytesIO()
            if fmt == 'GIF':
                image.save(out, format=fmt, save_all=True,
                           append_images=[Image.new('RGBA', size, '#40a0ff')], duration=80, loop=0)
            else:
                image.save(out, format=fmt)
            cls.media[label] = (out.getvalue(), 'image/' + fmt.lower())

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)

    def setUp(self):
        self.settings = copy.deepcopy(DEFAULT)
        self.settings.update(items_in_composition=True, info_in_composition=True,
                             counter_in_composition=True, counter_mode='deaths',
                             item_display='both', graveyard_max=30, frame_enabled=True)
        self.state = {'party': [dict(slot=n, present=True, species_id=25, nickname=f'Mon {n}',
                                    image_rev='small', image_format='png', item='Piedra', item_id=1,
                                    hp=40, max_hp=100, percent=40, types=['Eléctrico'],
                                    level=50, gender=0, shiny=False, dead=False)
                                for n in range(1, 7)],
                      'death_count': 1, 'graveyard': [], 'graveyard_total': 0,
                      'stats': {'captures': 6, 'alive': 5, 'deaths': 1, 'missed': 0}}
        self.context = self.browser.new_context(viewport={'width': 1280, 'height': 720})
        self.page = self.context.new_page()
        self.errors = []
        self.page.on('pageerror', lambda error: self.errors.append(str(error)))
        self.page.route('**/overlay/**', self.route_media)
        self.page.route('**/api/overlay/**', self.route_api)

    def tearDown(self):
        ARTIFACTS.mkdir(parents=True, exist_ok=True)
        self.page.screenshot(path=str(ARTIFACTS / (self._testMethodName + '.png')))
        self.context.close()
        self.assertEqual(self.errors, [], 'Uncaught browser errors')

    def route_api(self, route):
        payload = self.settings if urlsplit(route.request.url).path.endswith('settings') else self.state
        route.fulfill(status=200, content_type='application/json', body=json.dumps(payload))

    def route_media(self, route):
        label = next((name for name in self.media if name in route.request.url), 'small')
        body, mime = self.media[label]
        route.fulfill(status=200, content_type=mime, body=body)

    def open_source(self, query):
        # This page intentionally polls every 500 ms, so networkidle is not a
        # readiness condition. Wait for its rendered layer instead.
        self.page.goto(self.base + '/overlay.html?' + query, wait_until='domcontentloaded')
        self.page.wait_for_function("document.querySelector('#overlay').children.length > 0")
        self.settle()

    def settle(self):
        self.page.evaluate('() => document.fonts.ready')
        self.page.evaluate('() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))')

    def refresh(self, settings=False):
        path = '/api/overlay/settings' if settings else '/api/overlay/public'
        with self.page.expect_response(lambda response: urlsplit(response.url).path == path):
            pass  # The real overlay polling loop performs the next request.
        self.settle()

    def bounds(self):
        return self.page.evaluate("""() => [...document.querySelectorAll(
          '#overlay,.overlay-layer,.overlay-slot,.overlay-counter,.overlay-stats,.overlay-graveyard,.grave-card')]
          .map(el => {const r=el.getBoundingClientRect(); return [r.x,r.y,r.width,r.height]})""")

    def test_source_geometry_survives_media_content_and_border_changes(self):
        sources = ['layer=all', *('layer=' + layer for layer in
                   ['sprites', 'names', 'hp', 'items', 'info', 'counter', 'stats']),
                   *('layer=all&slot=' + str(n) for n in range(1, 7)),
                   'layer=all&slot=3&preset=Geometry']
        for source in sources:
            with self.subTest(source=source):
                self.settings.update(frame_enabled=True, frame_width=2)
                self.open_source(source)
                expected = self.bounds()
                self.assertNotEqual(self.page.locator('#overlay').evaluate(
                    "e => getComputedStyle(e,'::after').boxShadow"), 'none')
                for label in self.media:
                    for mon in self.state['party']:
                        mon.update(image_rev=label, image_format=label if label in ('gif', 'webp') else 'png',
                                   nickname='Nombre muy largo ' * 5, item='Objeto largo ' * 6,
                                   types=['Eléctrico', 'Volador'], shiny=True)
                    self.refresh()
                    if self.page.locator('.overlay-image').count():
                        self.page.wait_for_function("""label => [...document.querySelectorAll('.overlay-image')]
                            .every(e => e.complete && e.naturalWidth > 0 && e.src.includes(label))""", arg=label)
                        self.assertEqual(self.page.locator('.overlay-image').first.evaluate(
                            'e => getComputedStyle(e).objectFit'), 'contain')
                    self.assertEqual(self.bounds(), expected, (source, label))
                for mon in self.state['party']:
                    mon.update(present=False, item='', item_id=0, dead=True)
                self.state['death_count'] = 99999
                self.state['stats'].update(captures=99999, alive=0)
                self.refresh()
                self.assertEqual(self.bounds(), expected, (source, 'absent'))
                self.settings.update(frame_enabled=False, frame_width=8, frame_radius=40)
                self.refresh(settings=True)
                self.assertEqual(self.page.locator('#overlay').evaluate(
                    "e => getComputedStyle(e,'::after').boxShadow"), 'none')
                self.assertEqual(self.bounds(), expected, (source, 'border'))
                transparent = self.page.evaluate("""() => ['html','body'].map(s =>
                    getComputedStyle(document.querySelector(s)).backgroundColor)""")
                self.assertEqual(transparent, ['rgba(0, 0, 0, 0)'] * 2)
                self.page.set_viewport_size({'width': 480, 'height': 360})
                self.settle()
                self.assertEqual(self.bounds(), expected, (source, 'small viewport'))
                self.page.set_viewport_size({'width': 1280, 'height': 720})
                for n, mon in enumerate(self.state['party'], 1):
                    mon.update(present=True, nickname=f'Mon {n}', item='Piedra', item_id=1, dead=False)

    def test_graveyard_four_layouts_reserve_positions_for_one_to_thirty_deaths(self):
        for mode in ['horizontal', 'vertical', 'grid', 'custom']:
            with self.subTest(mode=mode):
                self.settings.update(graveyard_layout=mode, graveyard_columns=5, graveyard_max=30,
                                     graveyard_gap=9, frame_enabled=True)
                self.state['graveyard'] = []
                self.open_source('layer=graveyard&preset=Geometry')
                outer = self.bounds()[0]
                first = None
                for count in [1, 6, 12, 30]:
                    self.state['graveyard'] = [dict(image_rev='small-' + str(n), nickname=f'Caído {n}',
                        species='Pikachu', level=50, route='Ruta 1') for n in range(count)]
                    self.state['graveyard_total'] = count
                    self.refresh()
                    self.assertEqual(self.page.locator('.grave-card').count(), count)
                    self.assertEqual(self.bounds()[0], outer, (mode, count, 'reserved extent'))
                    cards = self.page.locator('.grave-card').evaluate_all("""els => els.map(e => {
                        const r=e.getBoundingClientRect();return [r.x,r.y,r.width,r.height]})""")
                    first = first or cards[0]
                    self.assertEqual(cards[0], first, (mode, count, 'first anchor'))
                    if count > 1 and mode == 'horizontal':
                        self.assertEqual(len({r[1] for r in cards}), 1)
                    if count > 1 and mode == 'vertical':
                        self.assertEqual(len({r[0] for r in cards}), 1)
                    if count == 30 and mode == 'custom':
                        self.assertEqual(len({r[0] for r in cards}), 5)
                    if count > 1 and mode == 'grid':
                        self.assertGreater(len({r[0] for r in cards}), 1)
                    before = self.bounds()
                    for record in self.state['graveyard']:
                        record.update(image_rev='wide-' + record['image_rev'],
                                      nickname='Nombre extenso ' * 8, route='Una ruta larga ' * 8)
                    self.refresh()
                    self.assertEqual(self.bounds(), before, (mode, count, 'changed sprites/text'))
                self.settings['frame_enabled'] = False
                before = self.bounds()
                self.refresh(settings=True)
                self.assertEqual(self.bounds(), before, (mode, 'hidden borders'))

    def test_animation_polling_and_dead_mega_states_keep_sprite_frames(self):
        self.settings.update(slot_frame=True, show_empty=True)
        for mon in self.state['party']:
            mon.update(image_rev='gif', image_format='gif')
        media_requests = []
        self.page.on('request', lambda request: media_requests.append(request.url)
                     if '/overlay/media/' in request.url else None)
        self.open_source('layer=sprites&preset=Geometry')
        self.page.wait_for_function("""() => [...document.querySelectorAll('.overlay-image')]
            .every(e => e.complete && e.naturalHeight === 128)""")
        before = self.bounds()
        requests_before = len(media_requests)
        self.assertEqual(requests_before, 6)
        self.refresh()
        self.refresh()
        self.assertEqual(len(media_requests), requests_before, 'Polling must not restart GIF playback')
        for style in ['gray', 'hide', 'tombstone']:
            self.settings['death_style'] = style
            for mon in self.state['party']:
                mon.update(dead=True, species_id=6, types=['Fuego', 'Volador'],
                           image_rev='hd-mega', image_format='png')
            self.refresh(settings=True)
            self.assertEqual(self.bounds(), before, style)
            self.assertEqual(self.page.locator('.overlay-slot.dead').count(), 6)
        for mon in self.state['party']:
            mon['present'] = False
        self.refresh()
        self.assertEqual(self.bounds(), before, 'Empty slots with visible reserved frames')


if __name__ == '__main__':
    unittest.main()
