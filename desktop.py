"""Windows desktop launcher: native WebView2 window over the existing localhost tracker.

This entry point is bundled as PokemonTracker.exe. The legacy server.py and
browser/.bat workflow remain supported until native builds are validated.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import sys
import threading
import traceback
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import urlopen
import secrets

from companion.sync import CompanionSync
from server import make_handler, runtime_directory, RemoteOverlayShare
from tracker.service import TrackerService
from tracker.layout_export import PartyLayoutExporter, layout_directory
from tracker.overlay import OverlayManager
from tracker.desktop_export import DesktopExportApi
from tracker.run_profiles import RunProfileStore, acquire_run_lock

APP_NAME = 'PokemonTracker'
PROFILE_CHOICES = ('principal', 'segundo-jugador')  # Internal only; never shown in the UI.


class LocalHTTPServer(ThreadingHTTPServer):
    # Windows SO_REUSEADDR can bind two listeners to the same live port, sending
    # requests to another app instance instead of triggering the safe fallback.
    allow_reuse_address = False
    request_queue_size = 128
    daemon_threads = True

    def server_bind(self):
        if sys.platform == 'win32':
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


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
    return acquire_run_lock(home, profile)


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


def automatic_session(home):
    """Reserve a window's OBS output separately from its changeable run."""
    store = RunProfileStore(Path(home) / 'runtime')
    for slot in PROFILE_CHOICES:
        try:
            slot_lock = acquire_profile_lock(home, 'window-' + slot)
        except RuntimeError:
            continue
        available = [p['id'] for p in store.profiles()]
        candidates = dict.fromkeys([p for p in [slot, *PROFILE_CHOICES, *available] if p in available])
        for profile in candidates:
            lock = None
            try:
                lock = acquire_profile_lock(home, profile)
                store.require(profile)
                return profile, lock, slot, slot_lock
            except (RuntimeError, ValueError):
                if lock:
                    lock.close()
                continue
        slot_lock.close()
    raise RuntimeError('Ya hay dos ventanas de Pokémon Tracker abiertas.')


class LocalBackend:
    """Start/stop the same tracker core as server.py, without an external browser."""
    def __init__(self, runtime, profile, layout_path=None, sprite_cache=None, custom_dir=None,
                 profile_lock=None, slot_profile=None, slot_lock=None):
        self.runtime = Path(runtime)
        self.profile = profile
        base = self.runtime if profile == 'principal' else self.runtime.parent.parent
        self.profiles = RunProfileStore(base)
        self.lock_home = base.parent
        self.profile_lock = profile_lock
        self.request_lock = threading.RLock()
        self.slot_profile = slot_profile or ('principal' if profile == 'principal' else 'segundo-jugador')
        self.slot_lock = slot_lock
        self.token = secrets.token_urlsafe(32)
        self.layout_path = Path(layout_path) if layout_path else self.runtime.parent / 'layout'
        self.sprite_cache = Path(sprite_cache) if sprite_cache else self.runtime.parent / 'sprite-cache'
        self.custom_dir = Path(custom_dir) if custom_dir else self.layout_path.parent / 'sprites_personalizados'
        self.layout = None
        self.overlay = None
        self.remote_share = None
        self.service = None
        self.companion = None
        self.server = None
        self.worker = None
        self.http_thread = None

    @property
    def url(self):
        return f'http://127.0.0.1:{self.server.server_port}/'

    def start(self):
        if self.profile_lock is None:
            self.profile_lock = acquire_profile_lock(self.lock_home, self.profile)
        try:
            if self.slot_lock is None:
                self.slot_lock = acquire_profile_lock(self.lock_home, 'window-' + self.slot_profile)
        except Exception:
            self.profile_lock.close()
            self.profile_lock = None
            raise
        self._start_services()
        handler = self._handler()
        # Stable URL in OBS after restart, with a safe fallback if in use.
        preferred_port = 8765 if self.slot_profile == 'principal' else 8766
        try:
            self.server = LocalHTTPServer(('127.0.0.1', preferred_port), handler)
        except OSError:
            self.server = LocalHTTPServer(('127.0.0.1', 0), handler)
        self.http_thread = threading.Thread(target=self.server.serve_forever,
                                             name='tracker-http', daemon=True)
        self.http_thread.start()
        return self

    def _handler(self):
        return make_handler(self.service, self.token, self.companion,
                            profile=self.profile, overlay=self.overlay,
                            share=self.remote_share, sprite_cache=self.sprite_cache,
                            profiles=self)

    def _start_services(self):
        self.service = TrackerService(self.runtime / 'state.json')
        self.companion = CompanionSync(self.service, self.runtime)
        self.overlay = OverlayManager(self.service, self.runtime, self.layout_path,custom_dir=self.custom_dir)
        self.remote_share = RemoteOverlayShare(
            self.service, self.overlay, preferred_port=8767 if self.slot_profile == 'principal' else 8768)
        self.worker = threading.Thread(target=self.service.run,
                                        name='tracker-memory', daemon=True)
        self.worker.start()
        self.companion.start()
        self.layout = PartyLayoutExporter(self.service, self.layout_path,
                                          cache_dir=self.sprite_cache,
                                          custom_dir=self.custom_dir)
        self.layout.start()

    def profiles_status(self):
        with self.request_lock:
            return {'active': self.profile, 'profiles': self.profiles.profiles()}

    def create_profile(self, name):
        with self.request_lock:
            created = self.profiles.create(name)
            return {**self.profiles_status(), 'created': created['id']}

    def delete_profile(self, ident):
        with self.request_lock:
            if ident == self.profile:
                raise ValueError('Abre otra partida antes de eliminar la que estás usando.')
            self.profiles.delete(ident)
            return self.profiles_status()

    def switch_profile(self, ident):
        with self.request_lock:
            runtime = self.profiles.require(ident)
            if ident == self.profile:
                if self.service.stop.is_set():
                    self._stop_services()
                    self._start_services()
                    self.server.RequestHandlerClass = self._handler()
                return self.profiles_status()
            # Never disconnect the current game if another window owns the target.
            lock = acquire_profile_lock(self.lock_home, ident)
            try:
                # Another window may have deleted it while this one waited.
                runtime = self.profiles.require(ident)
            except Exception:
                lock.close()
                raise
            previous_runtime, previous_profile = self.runtime, self.profile
            previous_lock = self.profile_lock
            try:
                self._stop_services()
            except Exception:
                lock.close()
                raise
            try:
                self.runtime, self.profile = runtime, ident
                self.profile_lock = lock
                self._start_services()
                self.server.RequestHandlerClass = self._handler()
            except Exception:
                # Keep the current run recoverable after a failed target startup.
                # Do not release its lock or restart a service until all target
                # workers have actually stopped.
                self._stop_services()
                lock.close()
                self.runtime, self.profile = previous_runtime, previous_profile
                self.profile_lock = previous_lock
                self._start_services()
                self.server.RequestHandlerClass = self._handler()
                raise
            self.profile_lock = lock
            if previous_lock:
                previous_lock.close()
            return self.profiles_status()

    def _stop_services(self):
        if self.service:
            self.service.stop.set()
            with self.service.condition:
                self.service.condition.notify_all()
        if self.remote_share:
            self.remote_share.close()
        if self.layout:
            self.layout.close()
        if self.companion:
            self.companion.close()
        if self.worker:
            self.worker.join(timeout=12)
        for worker in (self.worker, getattr(self.layout, 'thread', None),
                       getattr(self.companion, 'thread', None)):
            if worker and worker.is_alive():
                raise RuntimeError('La conexión no pudo cerrarse. Cierra y vuelve a abrir la aplicación antes de cambiar de partida.')

    def close(self):
        self._stop_services()
        if self.server:
            if self.http_thread and self.http_thread.is_alive():
                self.server.shutdown()
            self.server.server_close()
        if self.http_thread:
            self.http_thread.join(timeout=4)
        if self.profile_lock:
            self.profile_lock.close()
            self.profile_lock = None
        if self.slot_lock:
            self.slot_lock.close()
            self.slot_lock = None


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
                     'api/session', 'api/templates', 'api/routes',
                     'overlay', 'overlay/editor', 'overlay.js',
                     'overlay.css','api/overlay/public','api/overlay/settings'):
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
        # Profiles swap the service without rebuilding the native window.
        export_api.service = backend.service
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
    slot_lock = None
    try:
        if not opts.smoke_test:
            auto_migrate_local_checkout(home)
        if opts.profile:
            profile = opts.profile
            slot = profile
            locked = acquire_profile_lock(home, profile)
        elif opts.smoke_test:
            profile = 'principal'
            slot = profile
            locked = acquire_profile_lock(home, profile)
        else:
            profile, locked, slot, slot_lock = automatic_session(home)
        backend = LocalBackend(
            runtime_directory(home, None if profile == 'principal' else profile),
            profile, layout_path=layout_directory(home, slot),
            sprite_cache=home / 'sprite-cache',
            custom_dir=layout_directory(home).parent / 'sprites_personalizados',
            profile_lock=locked, slot_profile=slot, slot_lock=slot_lock
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
        if slot_lock:
            slot_lock.close()


if __name__ == '__main__':
    raise SystemExit(main())
