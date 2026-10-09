"""Windows desktop launcher: native WebView2 window over the existing localhost tracker.

This entry point is bundled as PokemonTracker.exe. The legacy server.py and
browser/.bat workflow remain supported until native builds are validated.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import threading
import traceback
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import urlopen
import secrets

from companion.sync import CompanionSync
from server import make_handler, runtime_directory
from tracker.service import TrackerService
from tracker.layout_export import PartyLayoutExporter, layout_directory
from tracker.desktop_export import DesktopExportApi

APP_NAME = 'PokemonTracker'
PROFILE_CHOICES = ('principal', 'segundo-jugador')  # Internal only; never shown in the UI.


def app_home(env=None):
    """Writable data home, independent of the immutable PyInstaller bundle."""
    env = os.environ if env is None else env
    base = env.get('LOCALAPPDATA')
    if base:
        return Path(base) / APP_NAME
    return Path.home() / '.pokemon-tracker'


def legacy_runtime_candidates(executable=None):
    """Identify nearby source checkouts; never guess another app's credentials."""
    executable = Path(executable or sys.executable).resolve()
    # Covers <repo>/dist/PokemonTracker/PokemonTracker.exe when built locally.
    dirs = [executable.parent, *list(executable.parents)[:4]]
    # Downloaded ZIP is often a sibling of an existing NuzlockeTracker checkout.
    for parent in (executable.parent, *list(executable.parents)[:2]):
        dirs.extend((parent / 'NuzlockeTracker', parent / 'Pokemon_Tracker'))
    seen = set()
    for directory in dirs:
        source = directory / 'runtime'
        if source in seen:
            continue
        seen.add(source)
        if (directory / 'server.py').is_file() and source.is_dir():
            yield source


def import_legacy_runtime(source, destination):
    """Copy an entire local runtime without overwriting any existing profile."""
    source = Path(source).expanduser().resolve()
    destination = Path(destination).expanduser()
    if not source.is_dir() or not any((source / name).exists() for name in
        ('state.json', 'profiles', 'companion-credentials.json',
         'pk3ds-templates.json', 'session-profile.json')):
        raise ValueError('Elige la carpeta runtime del tracker anterior.')
    if destination.exists():
        raise FileExistsError('Ya hay una sesión local; no se sobrescribirá.')
    if source == destination.resolve():
        raise ValueError('La carpeta elegida ya es el destino.')
    destination.parent.mkdir(parents=True, exist_ok=True)
    # A complete copy preserves per-profile Soul Link tokens and saved Pokémon.
    shutil.copytree(source, destination, symlinks=False)
    return destination


def auto_migrate_local_checkout(home, executable=None):
    """Only auto-import when the EXE is actually inside the previous checkout."""
    dest = Path(home) / 'runtime'
    if dest.exists():
        return False
    for source in legacy_runtime_candidates(executable):
        import_legacy_runtime(source, dest)
        return True
    return False


def acquire_profile_lock(home, profile):
    """Prevent concurrent writes from two windows using the same profile."""
    if sys.platform != 'win32':
        return None
    import msvcrt

    folder = Path(home) / '.locks'
    folder.mkdir(parents=True, exist_ok=True)
    file = open(folder / (profile + '.lock'), 'a+b')
    try:
        file.seek(0, os.SEEK_END)
        if file.tell() == 0:
            file.write(b'0')
            file.flush()
        file.seek(0)
        msvcrt.locking(file.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        file.close()
        raise RuntimeError('Ese perfil ya está abierto. Elige el otro jugador.') from None
    return file


def automatic_profile(home):
    """First window uses existing primary session; second uses the other.

    Keep both Soul Link profiles and cache files, but no player chooser.
    """
    for profile in PROFILE_CHOICES:
        try:
            lock = acquire_profile_lock(home, profile)
            return profile, lock
        except RuntimeError:
            continue
    raise RuntimeError('Ya hay dos ventanas de Pokémon Tracker abiertas.')


class LocalBackend:
    """Start/stop the same tracker core as server.py, without an external browser."""
    def __init__(self, runtime, profile, layout_path=None, sprite_cache=None, custom_dir=None):
        self.runtime = Path(runtime)
        self.profile = profile
        self.layout_path = Path(layout_path) if layout_path else self.runtime.parent / 'layout'
        self.sprite_cache = Path(sprite_cache) if sprite_cache else self.runtime.parent / 'sprite-cache'
        self.custom_dir = Path(custom_dir) if custom_dir else self.layout_path.parent / 'sprites_personalizados'
        self.layout = None
        self.service = None
        self.companion = None
        self.server = None
        self.worker = None
        self.http_thread = None

    @property
    def url(self):
        return f'http://127.0.0.1:{self.server.server_port}/'

    def start(self):
        self.service = TrackerService(self.runtime / 'state.json')
        self.companion = CompanionSync(self.service, self.runtime)
        self.server = ThreadingHTTPServer(('127.0.0.1', 0),
            make_handler(self.service, secrets.token_urlsafe(32),
                         self.companion, profile=self.profile))
        self.http_thread = threading.Thread(target=self.server.serve_forever,
                                             name='tracker-http', daemon=True)
        self.worker = threading.Thread(target=self.service.run,
                                        name='tracker-memory', daemon=True)
        self.http_thread.start()
        self.worker.start()
        self.companion.start()
        self.layout = PartyLayoutExporter(self.service, self.layout_path,
                                          cache_dir=self.sprite_cache,
                                          custom_dir=self.custom_dir)
        self.layout.start()
        return self

    def close(self):
        if self.layout:
            self.layout.close()
        if self.service:
            self.service.stop.set()
            with self.service.condition:
                self.service.condition.notify_all()
        if self.companion:
            self.companion.close()
        if self.server:
            if self.http_thread and self.http_thread.is_alive():
                self.server.shutdown()
            self.server.server_close()
        if self.http_thread:
            self.http_thread.join(timeout=4)
        if self.worker:
            self.worker.join(timeout=4)


def smoke_test_native():
    """Load the SAME .NET/WinForms backend used by the real window.

    In particular this detects pythonnet / Python.Runtime.dll packaging failures
    that an HTTP-only smoke test misses. No windows are opened by this check.
    """
    if sys.platform == 'win32' and getattr(sys, 'frozen', False):
        import webview.platforms.winforms as winforms
        if not hasattr(winforms, 'BrowserView'):
            raise RuntimeError('Backend gráfico WinForms incompleto')
    return True


def smoke_test(backend):
    """CI check on Windows: verify actual frozen HTTP/resources without opening a GUI."""
    for endpoint in ('', 'app.js', 'app-icon.png', 'style.css', 'api/state',
                     'api/session', 'api/templates', 'api/routes'):
        with urlopen(backend.url + endpoint, timeout=12) as response:
            assert response.status == 200, endpoint
            data=response.read(120)
            assert data, endpoint
            if endpoint == 'app-icon.png':
                assert data.startswith(b'\x89PNG\r\n\x1a\n'), 'Icono PNG inválido'
    with urlopen(backend.url + 'api/session', timeout=12) as response:
        session = json.load(response)
    assert session['profile'] == backend.profile
    assert len(list(backend.layout_path.glob('pokemon_*.png'))) == 6
    return True


def message_error(message):
    if sys.platform == 'win32':
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, str(message),
              'Pokémon Tracker', 0x10)
    else:
        print(message, file=sys.stderr)



def create_desktop_window(backend, webview):
    """Expose only a plain function; never let pywebview traverse the backend.

    Passing DesktopExportApi as js_api freezes WebView2 initialization:
    pywebview recursively inspects public attributes and follows the attached
    TrackerService and Window object. A narrow window.expose callback does
    not inspect its closure and preserves the same JS API name.
    """
    export_api = DesktopExportApi(backend.service)

    def save_export(kind):
        return export_api.save_export(kind)

    window = webview.create_window('Pokémon Tracker', backend.url,
                                  width=1220, height=850,
                                  min_size=(820, 560),
                                  background_color='#15191e')
    export_api.window = window
    window.expose(save_export)
    return window

def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--profile', choices=PROFILE_CHOICES, default=None,
                        help='Perfil interno opcional para usos avanzados.')
    parser.add_argument('--smoke-test', action='store_true',
                        help='Solo para validar la compilación en CI.')
    opts = parser.parse_args(argv)
    home = app_home()
    home.mkdir(parents=True, exist_ok=True)
    backend = None
    locked = None
    try:
        if not opts.smoke_test:
            auto_migrate_local_checkout(home)
        if opts.profile:
            profile = opts.profile
            locked = acquire_profile_lock(home, profile)
        elif opts.smoke_test:
            profile = 'principal'
            locked = acquire_profile_lock(home, profile)
        else:
            profile, locked = automatic_profile(home)
        backend = LocalBackend(
            runtime_directory(home, None if profile == 'principal' else profile),
            profile, layout_path=layout_directory(home, profile),
            sprite_cache=home / 'sprite-cache',
            custom_dir=layout_directory(home).parent / 'sprites_personalizados'
        ).start()
        if opts.smoke_test:
            smoke_test(backend)
            smoke_test_native()
            return 0
        # Deliberately lazy: CI smoke test does not require installed WebView2.
        import webview
        create_desktop_window(backend, webview)
        webview.start(gui='edgechromium', debug=False)
        return 0
    except Exception as error:
        # Error logs are local, never sent to GitHub or the cloud.
        (home / 'desktop-error.log').write_text(traceback.format_exc(),
                                                 encoding='utf-8')
        message_error(str(error) + '\n\nDetalles en ' + str(home / 'desktop-error.log'))
        return 1
    finally:
        if backend:
            backend.close()
        if locked:
            locked.close()


if __name__ == '__main__':
    raise SystemExit(main())
