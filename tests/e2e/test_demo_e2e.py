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

import hashlib
import json
import os
import re
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
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

    def __init__(self, log_path: Path, profile: str | None = None):
        self.log_path = log_path
        self.lines: list[str] = []
        self.url: str | None = None
        self._ready = threading.Event()
        env = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONUTF8='1')
        self.process = subprocess.Popen(
            [sys.executable, '-u', 'server.py', '--demo', '--no-browser', *(['--profile', profile] if profile else [])],
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


    def stage_ids(self) -> list[str]:
        return self.page.evaluate('state.level_caps.stages.map(s => s.id)')

    def test_level_caps_stage_lists_export_import_and_replace(self) -> None:
        self.open_tracker()
        self.reset_level_caps()
        export = self.page.get_by_role('button', name='Exportar lista…')
        import_button = self.page.get_by_role('button', name='Importar lista…')
        self.open_tab('progress')
        expect(export).to_be_disabled()
        expect(self.page.locator('#caps-lists-hint')).to_contain_text('aún no tiene etapas')
        files = Path(tempfile.mkdtemp(prefix='etapas-e2e-'))

        def write(name: str, content) -> str:
            path = files / name
            path.write_text(content if isinstance(content, str) else json.dumps(content, ensure_ascii=False), encoding='utf-8')
            return str(path)

        def choose(path: str) -> None:
            with self.page.expect_file_chooser() as chooser:
                import_button.click()
            chooser.value.set_files(path)

        shared = {'format': 'progressive-tracker-stage-list', 'version': 1,
                  'stages': [{'name': 'Primer gimnasio', 'cap': 20}, {'name': 'Cueva', 'cap': 15}, {'name': 'Liga', 'cap': 60}]}

        # Importing into a run without stages: preview first, nothing changes until «Importar lista».
        choose(write('compartida.json', shared))
        dialog = self.page.locator('#level-caps-import-dialog')
        expect(dialog).to_be_visible()
        expect(dialog).to_contain_text('Primer gimnasio')
        expect(dialog).to_contain_text('Nv. 60')
        expect(dialog).to_contain_text('inferior al de la anterior')
        expect(dialog).to_contain_text('Ninguna etapa quedará vigente')
        expect(self.page.locator('#level-caps-import-confirm')).to_have_count(0)
        self.assertEqual(self.stage_ids(), [], 'La vista previa no modifica la partida')
        self.page.get_by_role('button', name='Cancelar').click()
        expect(dialog).to_be_hidden()
        expect(self.page.locator('#caps-lists-status')).to_contain_text('no se cambió nada')
        self.assertEqual(self.stage_ids(), [])
        expect(import_button).to_be_focused()

        choose(write('compartida.json', shared))
        self.page.get_by_role('button', name='Importar lista', exact=True).last.click()
        expect(dialog).to_be_hidden()
        expect(self.page.locator('#caps-lists-status')).to_contain_text('Lista importada: 3 etapas')
        expect(self.page.locator('#caps-select option')).to_have_count(4)
        expect(self.page.locator('#level-cap-chip')).to_have_text('Sin etapa vigente')
        first_ids = self.stage_ids()
        self.assertEqual(len(set(first_ids)), 3)

        # Export: a normal download in the browser with names, caps and order only.
        with self.page.expect_download() as download:
            export.click()
        self.assertEqual(download.value.suggested_filename, 'limites-de-nivel.json')
        exported = json.loads(Path(download.value.path()).read_text(encoding='utf-8'))
        self.assertEqual(exported, shared, 'Roundtrip exacto')
        self.assertNotIn(first_ids[0], json.dumps(exported))
        expect(self.page.locator('#caps-lists-status')).to_contain_text('Solo contiene nombres y niveles máximos')

        # Replacing an existing list needs an explicit confirmation and creates new ids.
        self.page.locator('#caps-select').select_option(label='2. Cueva · Nv. 15')
        expect(self.page.locator('#level-cap-chip')).to_contain_text('Cueva')
        replacement = {'format': 'progressive-tracker-stage-list', 'version': 1,
                       'stages': [{'name': 'Etapa nueva', 'cap': 40}]}
        choose(write('reemplazo.json', replacement))
        expect(dialog).to_contain_text('Esta partida ya tiene 3 etapas')
        apply = self.page.get_by_role('button', name='Reemplazar la lista')
        expect(apply).to_be_disabled()
        confirm = self.page.get_by_label('Entiendo que se reemplazará la lista actual')
        confirm.focus()
        self.page.keyboard.press('Space')
        expect(apply).to_be_enabled()
        self.assertEqual(self.stage_ids(), first_ids, 'Aún no se ha reemplazado nada')
        # Narrow window with the preview open: no horizontal page scroll.
        self.page.set_viewport_size({'width': 390, 'height': 844})
        expect(apply).to_be_visible()
        self.assertLessEqual(self.page.evaluate('document.documentElement.scrollWidth - window.innerWidth'), 1)
        self.page.set_viewport_size({'width': 1366, 'height': 900})
        apply.click()
        expect(dialog).to_be_hidden()
        expect(self.page.locator('#caps-select option')).to_have_count(2)
        self.assertEqual(len(self.stage_ids()), 1)
        self.assertTrue(set(self.stage_ids()).isdisjoint(first_ids), 'IDs nuevos')
        expect(self.page.locator('#level-cap-chip')).to_have_text('Sin etapa vigente')
        expect(self.page.locator('#caps-current')).to_contain_text('Se eliminó la etapa vigente «Cueva»')

        # Escape cancels; broken, future and invalid files show a clear error and change nothing.
        before = self.stage_ids()
        choose(write('otra.json', replacement))
        expect(dialog).to_be_visible()
        self.page.keyboard.press('Escape')
        expect(dialog).to_be_hidden()
        for name, content, message in (
                ('roto.json', '{ no es json', 'El archivo no es un JSON válido'),
                ('futuro.json', {**shared, 'version': 2}, 'versión 2 del formato'),
                ('otro.json', {'hola': 'mundo'}, 'no es una lista de etapas'),
                ('limite.json', {**shared, 'stages': [{'name': 'X', 'cap': 101}]}, 'entre 1 y 100'),
                ('ids.json', {**shared, 'stages': [{'id': 'a', 'name': 'X', 'cap': 5}]}, 'campos no admitidos'),
                ('grande.json', ' ' * 40_000, 'demasiado grande')):
            choose(write(name, content))
            expect(self.page.locator('#caps-lists-error')).to_contain_text(message)
            expect(dialog).to_be_hidden()
            self.assertEqual(self.stage_ids(), before, name)

        # Unsaved draft: importing is blocked, never discards it silently.
        self.page.get_by_label('Nombre de la etapa 1').fill('Borrador sin guardar')
        expect(import_button).to_be_disabled()
        expect(self.page.locator('#caps-lists-hint')).to_contain_text('cambios sin guardar')
        expect(export).to_be_enabled()
        self.assertEqual(self.page.get_by_label('Nombre de la etapa 1').input_value(), 'Borrador sin guardar')
        self.page.get_by_role('button', name='Descartar').click()
        expect(import_button).to_be_enabled()

        # The imported list survives a reload; the display option was never touched.
        self.page.reload(wait_until='domcontentloaded')
        expect(self.page.locator('#party > article.card')).to_have_count(6)
        self.open_tab('progress')
        expect(self.page.locator('#caps-select option')).to_have_count(2)
        expect(self.page.get_by_label('Mostrar el límite en la cabecera y en las fichas')).to_be_checked()
        self.reset_level_caps()
        self.assert_clean()


# Level caps proposed by Definitive Randomizer. The imported game data belongs to a run folder, so this
# class starts its own demo in a throwaway profile: the files of the default folder are never touched.
PROPOSAL_PROFILE = 'e2e-propuesta-limites'
PROPOSAL_FIXTURE = ROOT / 'tests' / 'fixtures' / 'definitive-game-data-v1.player-level-caps.synthetic.json'


@unittest.skipUnless(ENABLED, SKIP_REASON)
class LevelCapsProposalBrowserTests(unittest.TestCase):
    server: DemoServer
    base_url: str
    setUp = DemoBrowserTests.setUp
    tearDown = DemoBrowserTests.tearDown
    _known = staticmethod(DemoBrowserTests._known)
    _on_console = DemoBrowserTests._on_console
    _on_response = DemoBrowserTests._on_response
    assert_clean = DemoBrowserTests.assert_clean
    open_tracker = DemoBrowserTests.open_tracker
    open_tab = DemoBrowserTests.open_tab
    post_command = DemoBrowserTests.post_command
    stage_ids = DemoBrowserTests.stage_ids

    @classmethod
    def setUpClass(cls) -> None:
        ARTIFACTS.mkdir(parents=True, exist_ok=True)
        cls.folder = ROOT / 'runtime' / 'profiles' / PROPOSAL_PROFILE
        shutil.rmtree(cls.folder, ignore_errors=True)
        cls.server = DemoServer(ARTIFACTS / 'server-propuesta.log', profile=PROPOSAL_PROFILE)
        try:
            cls.base_url = cls.server.wait_ready(SERVER_START_TIMEOUT)
            expect.set_options(timeout=UI_TIMEOUT_MS)
            cls.playwright = sync_playwright().start()
            cls.browser = cls.playwright.chromium.launch()
        except BaseException:
            cls.server.stop()
            if getattr(cls, 'playwright', None):
                cls.playwright.stop()
            shutil.rmtree(cls.folder, ignore_errors=True)
            raise

    @classmethod
    def tearDownClass(cls) -> None:
        try:
            cls.browser.close()
            cls.playwright.stop()
        finally:
            cls.server.stop()
            shutil.rmtree(cls.folder, ignore_errors=True)

    def import_game_data(self, document: dict) -> None:
        """The real import flow of Conexión: choose the file, preview, acknowledge and confirm."""
        path = Path(tempfile.mkdtemp(prefix='dgd-e2e-')) / 'datos.json'
        path.write_text(json.dumps(document, ensure_ascii=False), encoding='utf-8')
        self.open_tab('connection')
        self.page.evaluate("document.getElementById('game-data-settings').open = true")
        self.page.locator('#game-data-file').set_input_files(str(path))
        self.page.locator('#preview-game-data').click()
        expect(self.page.locator('#game-data-preview')).to_be_visible()
        self.page.locator('#game-data-ack').check()
        self.page.locator('#apply-game-data').click()
        expect(self.page.locator('#game-data-status')).to_contain_text('DGD activo para esta partida')


    def test_profile_provenance_preview_persistence_keyboard_and_narrow_layout(self) -> None:
        document = json.loads((ROOT / 'tests/fixtures/definitive-game-data-v1.profile-provenance.synthetic.json').read_text(encoding='utf-8'))
        document['game'].update(id='ultra-moon', titleId='00040000001B5100')
        document['profileProvenance']['gameId'] = 'ultra-moon'
        document['profileProvenance']['profile']['name'] = '<Perfil de pruebas>'
        baseline = json.loads(json.dumps(document))
        del baseline['profileProvenance']
        self.open_tracker()
        self.import_game_data(baseline)
        expect(self.page.locator('#game-data-profile-text')).to_contain_text('no incluye procedencia')
        self.page.screenshot(path=str(ARTIFACTS / 'profile-before-import.png'), full_page=True)
        before_caps = self.level_caps()
        with tempfile.TemporaryDirectory(prefix='dgd-profile-e2e-') as folder:
            path = Path(folder) / 'profile.json'
            path.write_text(json.dumps(document, ensure_ascii=False), encoding='utf-8')
            self.page.locator('#game-data-file').set_input_files(str(path))
            self.page.locator('#preview-game-data').click()
            expect(self.page.locator('#game-data-profile-title')).to_contain_text('vista previa')
            expect(self.page.locator('#game-data-profile-text')).to_contain_text('<Perfil de pruebas>')
            self.page.locator('#cancel-game-data').click()
            expect(self.page.locator('#game-data-profile-text')).to_contain_text('no incluye procedencia')
            self.assertNotIn('<Perfil de pruebas>', self.page.locator('#game-data-profile-text').inner_text())
            self.page.locator('#game-data-file').set_input_files(str(path))
            self.page.locator('#preview-game-data').click()
            self.page.locator('#game-data-ack').check()
            self.page.locator('#apply-game-data').click()
            expect(self.page.locator('#game-data-profile-title')).to_have_text('Perfil de origen')
            expect(self.page.locator('#game-data-profile-text')).to_contain_text('Autor declarado: Autor de ejemplo')
            expect(self.page.locator('#game-data-profile-text')).to_contain_text('No acredita coincidencia exacta')
            self.assertEqual(self.page.locator('#game-data-profile-text b').count(), 0)
            self.assertEqual(self.level_caps(), before_caps)
            details = self.page.locator('#game-data-profile-details')
            details.locator('summary').focus()
            self.page.keyboard.press('Enter')
            self.assertTrue(details.evaluate('(el) => el.open'))
            expect(self.page.locator('#game-data-profile-hash')).to_have_text('A' * 64)
            self.page.screenshot(path=str(ARTIFACTS / 'profile-after-import.png'), full_page=True)
            self.page.set_viewport_size({'width': 390, 'height': 844})
            self.assertTrue(self.page.locator('#game-data-profile').evaluate('(el) => el.scrollWidth <= el.clientWidth'))
            self.page.screenshot(path=str(ARTIFACTS / 'profile-narrow.png'), full_page=True)
            self.page.reload(wait_until='domcontentloaded')
            self.open_tab('connection')
            self.page.evaluate("document.getElementById('game-data-settings').open = true")
            expect(self.page.locator('#game-data-profile-text')).to_contain_text('<Perfil de pruebas>')
            self.assertEqual(self.level_caps(), before_caps)
        self.assert_clean()


    def level_caps(self) -> dict:
        return self.page.evaluate('({total: state.level_caps.total, current: state.level_caps.current, show: state.level_caps.show,'
                                  ' caps: state.level_caps.stages.map(s => s.cap), names: state.level_caps.stages.map(s => s.name)})')

    def test_randomizer_proposal_review_accept_replace_dismiss_and_withdraw(self) -> None:
        document = json.loads(PROPOSAL_FIXTURE.read_text(encoding='utf-8'))
        document['game'].update(id='ultra-moon', titleId='00040000001B5100')  # the demo run is Ultra Moon
        self.page.on('dialog', lambda dialog: dialog.accept())
        self.open_tracker()
        self.page.wait_for_function('typeof token === "string" && token.length > 0')
        card = self.page.locator('#caps-proposal')
        dialog = self.page.locator('#level-caps-proposal-dialog')
        apply = self.page.locator('#level-caps-proposal-apply')
        self.open_tab('progress')
        expect(card).to_be_hidden()

        # Importing the data never changes the caps of the run: it only offers a proposal.
        self.import_game_data(document)
        expect(self.page.locator('#game-data-status')).to_contain_text('propuesta de límites de nivel')
        self.open_tab('progress')
        expect(card).to_be_visible()
        expect(card).to_contain_text('Propuesta de Definitive Randomizer')
        expect(card).to_contain_text('6 puntos de Player Level Caps, de Nv. 15 a Nv. 70')
        expect(card).to_contain_text('no etapas de tu desafío')
        self.assertEqual(self.stage_ids(), [])
        expect(self.page.locator('#level-cap-chip')).to_be_hidden()

        # Review: preview, comparison and technical data. Keeping the current caps changes nothing.
        card.get_by_role('button', name='Revisar propuesta…').click()
        expect(dialog).to_be_visible()
        expect(dialog).to_contain_text('restricciones mecánicas del juego')
        expect(dialog.locator('tbody tr')).to_have_count(6)
        expect(dialog).to_contain_text('Sin nombre en el catálogo · Event Flag · byte 0x0150, máscara 0x04')
        expect(dialog).to_contain_text('Ninguna etapa quedará vigente')
        expect(self.page.locator('#level-caps-proposal-final')).not_to_be_checked()
        expect(self.page.locator('#level-caps-proposal-confirm')).to_have_count(0)
        dialog.locator('summary').click()
        expect(dialog).to_contain_text('Hash de la tabla del parche')
        self.assertEqual(self.stage_ids(), [], 'La revisión no modifica la partida')
        self.page.get_by_role('button', name='Conservar los límites actuales').click()
        expect(dialog).to_be_hidden()
        expect(card).to_contain_text('Se conservan los límites actuales: no se cambió nada')
        self.assertEqual(self.stage_ids(), [])
        card.get_by_role('button', name='Revisar propuesta…').click()
        self.page.keyboard.press('Escape')
        expect(dialog).to_be_hidden()
        self.assertEqual(self.stage_ids(), [])

        # Accept into a run without stages: six stages, no current one, the display option untouched.
        card.get_by_role('button', name='Revisar propuesta…').click()
        expect(apply).to_have_text('Aceptar la propuesta')
        apply.click()
        expect(dialog).to_be_hidden()
        expect(self.page.locator('#caps-select option')).to_have_count(7)
        expect(card).to_contain_text('Propuesta aceptada: 6 etapas')
        expect(card).to_contain_text('Propuesta de Definitive Randomizer en uso')
        caps = self.level_caps()
        self.assertEqual((caps['caps'], caps['current'], caps['show']), ([15, 20, 45, 50, 60, 70], None, True))
        expect(self.page.locator('#level-cap-chip')).to_have_text('Sin etapa vigente')
        expect(self.page.locator('#caps-current')).to_contain_text('Sin etapa vigente')

        # The player chooses the current stage; accepting again replaces only with an explicit confirmation.
        self.page.locator('#caps-select').select_option(label='2. Defeat Kahuna Hala · Nv. 20')
        expect(self.page.locator('#level-cap-chip')).to_contain_text('Límite Nv. 20')
        first_ids = self.stage_ids()
        card.get_by_role('button', name='Ver la propuesta…').click()
        expect(dialog).to_contain_text('ya tiene 6 etapas')
        expect(dialog).to_contain_text('la vigente es «Defeat Kahuna Hala»')
        expect(apply).to_be_disabled()
        expect(apply).to_have_text('Aceptar y reemplazar las etapas')
        self.page.locator('#level-caps-proposal-confirm').check()
        expect(apply).to_be_enabled()
        # The optional final stage changes the list under review: the confirmation is asked again.
        self.page.locator('#level-caps-proposal-final').check()
        expect(dialog.locator('tbody tr')).to_have_count(7)
        expect(dialog).to_contain_text('Después del último punto (techo del parche)')
        expect(self.page.locator('#level-caps-proposal-confirm')).not_to_be_checked()
        expect(apply).to_be_disabled()
        self.assertEqual(self.stage_ids(), first_ids, 'Aún no se ha reemplazado nada')
        self.page.locator('#level-caps-proposal-confirm').check()
        apply.click()
        expect(dialog).to_be_hidden()
        expect(self.page.locator('#caps-select option')).to_have_count(8)
        caps = self.level_caps()
        self.assertEqual((caps['caps'][-1], caps['names'][-1], caps['current']), (100, 'Después del último punto (techo del parche)', None))
        self.assertTrue(set(self.stage_ids()).isdisjoint(first_ids), 'IDs nuevos')
        expect(self.page.locator('#caps-current')).to_contain_text('Se eliminó la etapa vigente «Defeat Kahuna Hala»')
        expect(self.page.locator('#level-cap-chip')).to_have_text('Sin etapa vigente')

        # An unsaved draft blocks the review instead of being discarded.
        self.page.get_by_label('Nombre de la etapa 1').fill('Borrador sin guardar')
        expect(card.get_by_role('button', name='Ver la propuesta…')).to_be_disabled()
        expect(card).to_contain_text('cambios sin guardar en las etapas')
        self.page.get_by_role('button', name='Descartar', exact=True).click()
        expect(card.get_by_role('button', name='Ver la propuesta…')).to_be_enabled()

        # Editing by hand keeps the origin and offers the proposal again; it can be set aside and brought back.
        self.page.get_by_label('Nivel máximo de la etapa 1').fill('16')
        self.page.get_by_role('button', name='Guardar cambios').click()
        expect(card).to_contain_text('Después se editaron a mano')
        card.get_by_role('button', name='Descartar propuesta').click()
        expect(card).to_contain_text('Propuesta de Definitive Randomizer descartada')
        self.assertEqual(self.level_caps()['caps'][0], 16, 'Descartar conserva las etapas')
        card.get_by_role('button', name='Volver a mostrarla').click()
        expect(card.get_by_role('button', name='Descartar propuesta')).to_be_visible()

        # Reload: stages, origin and proposal are still there and nothing became current.
        self.page.reload(wait_until='domcontentloaded')
        expect(self.page.locator('#party > article.card')).to_have_count(6)
        self.open_tab('progress')
        expect(self.page.locator('#caps-select option')).to_have_count(8)
        expect(card).to_contain_text('Después se editaron a mano')
        self.assertIsNone(self.level_caps()['current'])

        # Withdrawing the imported data keeps the accepted stages and their origin.
        self.open_tab('connection')
        self.page.evaluate("document.getElementById('game-data-settings').open = true")
        self.page.locator('#remove-game-data').click()
        expect(self.page.locator('#game-data-status')).to_contain_text('Sin datos DGD importados')
        self.open_tab('progress')
        expect(card).to_contain_text('Origen de las etapas')
        expect(card).to_contain_text('las etapas se conservan')
        expect(card.get_by_role('button')).to_have_count(0)
        self.assertEqual(self.level_caps()['total'], 7)
        self.assert_clean()

    def test_states_without_a_usable_list_only_inform(self) -> None:
        document = json.loads(PROPOSAL_FIXTURE.read_text(encoding='utf-8'))
        document['game'].update(id='ultra-moon', titleId='00040000001B5100')
        self.open_tracker()
        self.page.wait_for_function('typeof token === "string" && token.length > 0')
        self.assertEqual(self.post_command('{"action":"level_caps_set","stages":[]}'), 202)
        card = self.page.locator('#caps-proposal')
        cases = [({'version': 1, 'status': 'not-detected', 'hooks': {'battleCro': 'stock', 'codeBin': 'stock'},
                   'source': {'fingerprintAlgorithm': 'SHA-256', 'scope': 'battle.cro,code.bin', 'fingerprint': 'B' * 64}},
                  'no tiene instalado el parche Player Level Caps'),
                 ({'version': 1, 'status': 'inconsistent', 'hooks': {'battleCro': 'applied', 'codeBin': 'stock'},
                   'source': {'fingerprintAlgorithm': 'SHA-256', 'scope': 'battle.cro,code.bin', 'fingerprint': 'B' * 64},
                   'detail': 'Battle.cro tiene el parche y code.bin conserva el código original.'}, 'no coinciden'),
                 ({'version': 2, 'anything': True}, 'formato más nuevo'),
                 ({**document['playerLevelCaps'], 'source': {**document['playerLevelCaps']['source'], 'tableSha256': '0' * 64}},
                  'no son válidos y se ignoran')]
        for block, message in cases:
            self.import_game_data({**document, 'playerLevelCaps': block})
            self.open_tab('progress')
            expect(card).to_contain_text(message)
            expect(card.get_by_role('button')).to_have_count(0)
            self.assertEqual(self.stage_ids(), [])
        # 65 points: a valid patch table that a run cannot hold. It is refused whole, never truncated.
        points = [{'order': i + 1, 'cap': min(100, 10 + i), 'condition': {'kind': 'event-flag-set', 'byte': i, 'mask': 1}} for i in range(65)]
        table = b''.join(struct.pack('<BBHH', 0, p['cap'], p['condition']['byte'], 1) for p in points) + bytes((0xFF, 100, 0, 0, 0, 0))
        block = {**document['playerLevelCaps'], 'checkpoints': points,
                 'source': {**document['playerLevelCaps']['source'], 'tableSha256': hashlib.sha256(table).hexdigest().upper()}}
        self.import_game_data({**document, 'playerLevelCaps': block})
        self.open_tab('progress')
        expect(card).to_contain_text('65 puntos')
        expect(card).to_contain_text('no se recorta')
        expect(card.get_by_role('button')).to_have_count(0)
        self.assertEqual(self.stage_ids(), [])
        self.assert_clean()


if __name__ == '__main__':
    unittest.main()
