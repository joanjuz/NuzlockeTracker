"""Browser end-to-end checks against `server.py --demo` (Playwright, sync API).

Opt-in: runs only with E2E=1 and Playwright installed (requirements-e2e.txt plus
`python -m playwright install chromium`). Otherwise every test is skipped so the
normal `python -m unittest discover -s tests` stays fast.

    E2E=1 python -m unittest discover -s tests/e2e -v

Selectors use DOM ids, data-tab attributes and roles from web/index.html and the
DOM built at runtime, never script file names (the frontend is split into
web/app/*.js). A screenshot per test and the server log are written to
E2E_ARTIFACTS (default build/e2e-artifacts, ignored by git).
"""
from __future__ import annotations

import os
import re
import signal
import subprocess
import sys
import threading
import time
import unittest
from pathlib import Path
from urllib.parse import urlsplit

try:
    from playwright.sync_api import expect, sync_playwright
except ImportError:  # Optional dependency: the suite is skipped below.
    sync_playwright = None
    expect = None

ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = Path(os.environ.get('E2E_ARTIFACTS') or ROOT / 'build' / 'e2e-artifacts')
ENABLED = os.environ.get('E2E') == '1' and sync_playwright is not None
SKIP_REASON = ('E2E desactivado: instala requirements-e2e.txt y ejecuta con E2E=1'
               if sync_playwright is None else 'E2E desactivado: define E2E=1')
URL_LINE = re.compile(r'Tracker local: (http://127\.0\.0\.1:\d+/)')
SERVER_START_TIMEOUT = 45.0
UI_TIMEOUT_MS = 15_000

# The demo has no profile manager, so /api/profiles answers 404 by design.
KNOWN_404_PATHS = frozenset({'/api/profiles'})

# Navigation tab -> (title shown in #title, view section id).
TABS = {
    'party': ('Equipo actual', 'party-view'),
    'boxes': ('Tus cajas', 'boxes-view'),
    'places': ('Rutas', 'places-view'),
    'progress': ('Progreso', 'progress-view'),
    'dead': ('Muertos', 'dead-view'),
    'analysis': ('Análisis del equipo', 'analysis-view'),
    'overlay': ('Diseñar overlay para OBS', 'overlay-view'),
    'connection': ('Conexión', 'connection-view'),
}

# Records every CSP violation, including those the console does not print.
CSP_PROBE = """
window.__cspViolations = [];
document.addEventListener('securitypolicyviolation', event => {
  window.__cspViolations.push(event.violatedDirective + ' ' + (event.blockedURI || ''));
});
"""


class DemoServer:
    """`python -u server.py --demo --no-browser` on a port chosen by the OS."""

    def __init__(self, log_path: Path):
        self.log_path = log_path
        self.lines: list[str] = []
        self.url: str | None = None
        self._ready = threading.Event()
        env = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONUTF8='1')
        self.process = subprocess.Popen(
            [sys.executable, '-u', 'server.py', '--demo', '--no-browser'],
            cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        self._reader = threading.Thread(target=self._drain, daemon=True)
        self._reader.start()

    def _drain(self) -> None:
        # Keep reading until EOF so a full pipe never blocks the server.
        assert self.process.stdout is not None
        for raw in self.process.stdout:
            line = raw.decode('utf-8', 'replace').rstrip()
            self.lines.append(line)
            match = URL_LINE.search(line)
            if match and self.url is None:
                self.url = match[1]
                self._ready.set()
        self._ready.set()

    def wait_ready(self, timeout: float) -> str:
        self._ready.wait(timeout)
        if self.url is None:
            raise RuntimeError('server.py --demo no anunció su URL:\n' + '\n'.join(self.lines[-40:]))
        return self.url

    def stop(self) -> None:
        if self.process.poll() is None:
            # SIGINT lets the demo flush its state; Windows has no SIGINT for
            # a child without a console group, so terminate there.
            if os.name == 'posix':
                self.process.send_signal(signal.SIGINT)
            else:
                self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=10)
        self._reader.join(timeout=5)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_path.write_text('\n'.join(self.lines) + '\n', encoding='utf-8')


@unittest.skipUnless(ENABLED, SKIP_REASON)
class DemoBrowserTests(unittest.TestCase):
    server: DemoServer
    base_url: str

    @classmethod
    def setUpClass(cls) -> None:
        ARTIFACTS.mkdir(parents=True, exist_ok=True)
        cls.server = DemoServer(ARTIFACTS / 'server.log')
        try:
            cls.base_url = cls.server.wait_ready(SERVER_START_TIMEOUT)
            expect.set_options(timeout=UI_TIMEOUT_MS)
            cls.playwright = sync_playwright().start()
            cls.browser = cls.playwright.chromium.launch()
        except BaseException:
            cls.server.stop()
            if getattr(cls, 'playwright', None):
                cls.playwright.stop()
            raise

    @classmethod
    def tearDownClass(cls) -> None:
        try:
            cls.browser.close()
            cls.playwright.stop()
        finally:
            cls.server.stop()

    def setUp(self) -> None:
        self.console_errors: list[str] = []
        self.csp_messages: list[str] = []
        self.http_errors: list[str] = []
        self.context = self.browser.new_context(viewport={'width': 1366, 'height': 900}, locale='es-ES')
        self.context.add_init_script(CSP_PROBE)
        self.context.set_default_timeout(UI_TIMEOUT_MS)
        self.page = self.context.new_page()
        self.page.on('console', self._on_console)
        self.page.on('pageerror', lambda error: self.console_errors.append(f'pageerror: {error}'))
        self.page.on('response', self._on_response)

    def tearDown(self) -> None:
        name = self.id().rsplit('.', 1)[-1]
        # Browser-side errors explain most UI timeouts: keep them in the log.
        for line in self.console_errors + self.csp_messages + self.http_errors:
            print(f'[{name}] {line}', file=sys.stderr)
        try:
            self.page.screenshot(path=str(ARTIFACTS / f'{name}.png'), full_page=True)
        except Exception as error:  # Screenshot is evidence only, never the failure cause.
            print(f'No se pudo guardar la captura {name}: {error}', file=sys.stderr)
        self.context.close()

    # -- listeners ---------------------------------------------------------
    @staticmethod
    def _known(url: str) -> bool:
        return urlsplit(url).path in KNOWN_404_PATHS

    def _on_console(self, message) -> None:
        text = message.text
        if 'Content Security Policy' in text:
            self.csp_messages.append(text)
        if message.type != 'error':
            return
        location = (message.location or {}).get('url', '')
        if '404' in text and self._known(location):
            return
        self.console_errors.append(f'{text} @ {location}')

    def _on_response(self, response) -> None:
        if response.status >= 400 and not (response.status == 404 and self._known(response.url)):
            self.http_errors.append(f'{response.status} {response.url}')

    # -- helpers -----------------------------------------------------------
    def assert_clean(self) -> None:
        violations = self.page.evaluate('window.__cspViolations || []')
        self.assertEqual(self.csp_messages + violations, [], 'Violaciones de Content-Security-Policy')
        self.assertEqual(self.console_errors, [], 'Errores en la consola del navegador')
        self.assertEqual(self.http_errors, [], 'Respuestas HTTP con error')

    def open_tracker(self) -> None:
        self.page.goto(self.base_url, wait_until='domcontentloaded')
        cards = self.page.locator('#party > article.card')
        expect(cards).to_have_count(6)
        # The demo starts with a full team: no card stays in the empty state.
        expect(self.page.locator('#party > article.card.empty')).to_have_count(0)

    def open_tab(self, tab: str) -> None:
        title, view = TABS[tab]
        button = self.page.locator(f'#section-nav button[data-tab="{tab}"]')
        button.click()
        expect(button).to_have_attribute('aria-current', 'page')
        expect(self.page.locator(f'#{view}')).to_be_visible()
        expect(self.page.locator('#title')).to_have_text(title)
        for other_tab, (_, other_view) in TABS.items():
            if other_tab != tab:
                expect(self.page.locator(f'#{other_view}')).to_be_hidden()

    # -- tests -------------------------------------------------------------
    def test_party_cards_render_without_console_errors(self) -> None:
        self.open_tracker()
        cards = self.page.locator('#party > article.card')
        for index in range(6):
            card = cards.nth(index)
            expect(card).to_have_attribute('role', 'button')
            expect(card.locator('.hp-track')).to_have_count(1)
            expect(card.locator('.moves .move')).not_to_have_count(0)
        self.page.wait_for_load_state('networkidle')
        self.assert_clean()

    def test_every_section_opens_with_content(self) -> None:
        self.open_tracker()

        self.open_tab('boxes')
        expect(self.page.locator('#boxes > *').first).to_be_visible()

        # Living Dex is a mode of the boxes view, toggled by its checkbox.
        self.page.locator('#living-dex').check()
        expect(self.page.locator('#boxes')).to_have_class(re.compile(r'\bliving-dex-grid\b'))
        expect(self.page.locator('#living-dex-status')).to_be_visible()
        expect(self.page.locator('#living-dex-status')).to_contain_text('Living Dex')
        expect(self.page.locator('#boxes > *').first).to_be_visible()
        self.page.locator('#living-dex').uncheck()

        self.open_tab('places')
        expect(self.page.locator('#places > *').first).to_be_visible()

        self.open_tab('dead')
        # Either dead Pokémon or the "no deaths" message, never an empty grid.
        expect(self.page.locator('#dead > *').first).to_be_visible()

        self.open_tab('analysis')
        expect(self.page.locator('#analysis-content > *').first).to_be_visible()

        self.open_tab('overlay')
        frame = self.page.locator('#overlay-editor-frame')
        expect(frame).to_have_attribute('src', '/overlay/editor')
        expect(self.page.frame_locator('#overlay-editor-frame').locator('body > *').first).to_be_visible()

        self.open_tab('connection')
        expect(self.page.locator('#demo-tools')).to_be_visible()
        expect(self.page.locator('#connect')).to_be_visible()

        self.open_tab('party')
        self.page.wait_for_load_state('networkidle')
        self.assert_clean()

    def test_detail_dialog_opens_and_closes_with_keyboard(self) -> None:
        self.open_tracker()
        dialog = self.page.locator('#detail')
        first_card = self.page.locator('#party > article.card').first

        first_card.focus()
        self.page.keyboard.press('Enter')
        expect(dialog).to_be_visible()
        self.assertTrue(dialog.evaluate('node => node.open'))
        expect(self.page.locator('#detail-content > *').first).to_be_visible()
        self.page.keyboard.press('Escape')
        expect(dialog).to_be_hidden()

        # Space activates the card too (role="button"), and the close button
        # is reachable and operable from the keyboard.
        self.page.locator('#party > article.card').nth(1).focus()
        self.page.keyboard.press(' ')
        expect(dialog).to_be_visible()
        self.page.locator('#close-detail').focus()
        self.page.keyboard.press('Enter')
        expect(dialog).to_be_hidden()
        self.assert_clean()

    def test_obs_overlay_has_six_sprites_on_transparent_background(self) -> None:
        self.page.goto(self.base_url + 'overlay?layer=all', wait_until='domcontentloaded')
        sprites = self.page.locator('#overlay section.overlay-layer[data-layer="sprites"] .overlay-slot img.overlay-image')
        expect(sprites).to_have_count(6)
        for index in range(6):
            expect(sprites.nth(index)).to_have_attribute('data-src', re.compile(r'^/overlay/media/pokemon_[1-6]\.'))
        backgrounds = self.page.evaluate(
            '[getComputedStyle(document.documentElement).backgroundColor,'
            ' getComputedStyle(document.body).backgroundColor,'
            ' getComputedStyle(document.body).backgroundImage]')
        self.assertEqual(backgrounds, ['rgba(0, 0, 0, 0)', 'rgba(0, 0, 0, 0)', 'none'])
        # Wait for sprite files so a missing image shows up as an HTTP error.
        deadline = time.monotonic() + UI_TIMEOUT_MS / 1000
        while time.monotonic() < deadline and not self.page.evaluate(
                "[...document.querySelectorAll('img.overlay-image')].every(i => i.complete)"):
            self.page.wait_for_timeout(200)
        self.assert_clean()


    def post_command(self, payload: str) -> int:
        """POST /api/command from the page, with the session token the UI already holds."""
        return self.page.evaluate("""async payload => (await fetch('/api/command', {method: 'POST',
            headers: {'Content-Type': 'application/json', 'X-Tracker-Token': token}, body: payload})).status""", payload)

    def reset_level_caps(self) -> None:
        # The demo keeps its progress in runtime/: leave no stages behind for other runs.
        self.page.wait_for_function('typeof token === "string" && token.length > 0')
        self.assertEqual(self.post_command('{"action":"level_caps_set","stages":[]}'), 202)
        self.assertEqual(self.post_command('{"action":"level_caps_show","show":true}'), 202)

    def test_level_caps_progress_view_editor_and_indicators(self) -> None:
        self.open_tracker()
        self.reset_level_caps()
        chip = self.page.locator('#level-cap-chip')
        self.open_tab('progress')
        expect(self.page.locator('#caps-current')).to_contain_text('Esta partida no tiene etapas')
        expect(chip).to_be_hidden()

        # First stage from the empty state, a second one by keyboard, both validated next to the row.
        self.page.get_by_role('button', name='Añadir la primera etapa').click()
        expect(self.page.locator(':focus')).to_have_attribute('aria-label', 'Nombre de la etapa 1')
        self.page.get_by_role('button', name='Guardar cambios').click()
        expect(self.page.locator('#caps-error-nueva-1')).to_have_text('Escribe un nombre.')
        expect(self.page.get_by_label('Nombre de la etapa 1')).to_have_attribute('aria-invalid', 'true')
        self.page.get_by_label('Nombre de la etapa 1').fill('Primer gimnasio')
        self.page.get_by_label('Nivel máximo de la etapa 1').fill('20')
        self.page.get_by_role('button', name='Añadir etapa').focus()
        self.page.keyboard.press('Enter')
        expect(self.page.locator(':focus')).to_have_attribute('aria-label', 'Nombre de la etapa 2')
        self.page.keyboard.type('Liga')
        self.page.get_by_label('Nivel máximo de la etapa 2').fill('15')
        expect(self.page.locator('#caps-editor')).to_contain_text('Nivel inferior al de la etapa anterior')
        expect(self.page.locator('#progress-unsaved')).to_be_visible()
        # Changing tabs keeps the draft.
        self.open_tab('party')
        self.open_tab('progress')
        expect(self.page.get_by_label('Nombre de la etapa 2')).to_have_value('Liga')
        self.page.get_by_role('button', name='Guardar cambios').click()
        expect(self.page.locator('#caps-select option')).to_have_count(3)
        expect(self.page.locator('#progress-unsaved')).to_be_hidden()

        # Stages without a current one: neutral chip, no card labels.
        expect(chip).to_have_text('Sin etapa vigente')
        expect(self.page.locator('#party .over-cap')).to_have_count(0)
        self.page.locator('#caps-select').select_option(label='1. Primer gimnasio · Nv. 20')
        # The demo team is level 100: all six are over the cap (informative only).
        expect(chip).to_have_text('Límite Nv. 20 · Primer gimnasio · 6 por encima')
        expect(self.page.locator('#caps-current')).to_contain_text('Etapa 1 de 2')
        self.page.get_by_role('button', name='Siguiente etapa').click()
        expect(chip).to_have_text('Límite Nv. 15 · Liga · 6 por encima')
        self.page.get_by_role('button', name='Etapa anterior').click()
        expect(chip).to_have_text('Límite Nv. 20 · Primer gimnasio · 6 por encima')
        self.open_tab('party')
        expect(self.page.locator('#party .over-cap')).to_have_count(6)
        expect(self.page.locator('#party .over-cap').first).to_have_text('+80 sobre el límite')

        # Reorder keeps the current stage by id; removing it leaves no current stage.
        self.open_tab('progress')
        self.page.get_by_role('button', name='Bajar la etapa 1').click()
        self.page.get_by_role('button', name='Guardar cambios').click()
        expect(self.page.locator('#caps-current')).to_contain_text('Etapa 2 de 2')
        expect(chip).to_have_text('Límite Nv. 20 · Primer gimnasio · 6 por encima')
        self.page.get_by_role('button', name='Eliminar la etapa 2').click()
        expect(self.page.locator('#caps-editor-status')).to_contain_text('quedará sin etapa vigente')
        self.page.get_by_role('button', name='Guardar cambios').click()
        expect(self.page.locator('#caps-current')).to_contain_text('Se eliminó la etapa vigente «Primer gimnasio»')
        expect(chip).to_have_text('Sin etapa vigente')

        # Hiding the caps keeps them; the setting survives a reload.
        self.page.locator('#caps-select').select_option(label='1. Liga · Nv. 15')
        expect(chip).to_have_text('Límite Nv. 15 · Liga · 6 por encima')
        self.page.get_by_label('Mostrar el límite en la cabecera y en las fichas').uncheck()
        expect(chip).to_be_hidden()
        self.page.reload(wait_until='domcontentloaded')
        expect(self.page.locator('#party > article.card')).to_have_count(6)
        expect(chip).to_be_hidden()
        expect(self.page.locator('#party .over-cap')).to_have_count(0)
        self.open_tab('progress')
        expect(self.page.get_by_label('Mostrar el límite en la cabecera y en las fichas')).not_to_be_checked()
        expect(self.page.locator('#caps-current')).to_contain_text('Etapa 1 de 1')

        # Editing a saved row (no new or moved rows) enables Guardar/Descartar without rebuilding the table.
        save = self.page.get_by_role('button', name='Guardar cambios')
        expect(save).to_be_disabled()
        self.page.get_by_label('Nombre de la etapa 1').fill('Liga renombrada')
        expect(self.page.get_by_label('Nombre de la etapa 1')).to_be_focused()
        expect(save).to_be_enabled()
        self.page.get_by_role('button', name='Descartar').click()
        expect(self.page.get_by_label('Nombre de la etapa 1')).to_have_value('Liga')
        expect(save).to_be_disabled()

        # Narrow window: no horizontal page scroll.
        self.page.set_viewport_size({'width': 390, 'height': 844})
        expect(self.page.get_by_label('Nombre de la etapa 1')).to_be_visible()
        self.assertLessEqual(self.page.evaluate('document.documentElement.scrollWidth - window.innerWidth'), 1)
        self.reset_level_caps()
        self.assert_clean()


if __name__ == '__main__':
    unittest.main()
