"""Aviso de nueva versión: consulta la última release pública en GitHub.

Solo LEE https://api.github.com/repos/joanjuz/NuzlockeTracker/releases/latest
(sin credenciales ni datos de la partida), la primera vez ~15 s después de
arrancar y luego cada 24 h. Nunca descarga ni instala nada: la interfaz solo
muestra un enlace a la página de la release. Cualquier fallo se registra y se
ignora. POKEMON_TRACKER_NO_UPDATE_CHECK=1 desactiva las consultas de red.
"""
from __future__ import annotations

import json
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from urllib.request import Request, urlopen

from tracker import __version__, diaglog

API_URL = 'https://api.github.com/repos/joanjuz/NuzlockeTracker/releases/latest'
RELEASES_PREFIX = 'https://github.com/joanjuz/NuzlockeTracker/releases/'
FALLBACK_URL = 'https://github.com/joanjuz/NuzlockeTracker/releases/latest'
DISABLE_ENV = 'POKEMON_TRACKER_NO_UPDATE_CHECK'
INITIAL_DELAY = 15.0
INTERVAL = 24 * 60 * 60.0
TIMEOUT = 8.0
MAX_BYTES = 256 * 1024
CACHE_NAME = 'update-check.json'

_VERSION = re.compile(r'v?(\d{1,6})\.(\d{1,6})\.(\d{1,6})')
log = diaglog.get('updates')


def parse_version(text):
    """'v1.2.3' o '1.2.3' -> (1, 2, 3); cualquier otra cosa -> None."""
    match = _VERSION.fullmatch(text.strip()) if isinstance(text, str) else None
    return tuple(int(part) for part in match.groups()) if match else None


def _version_text(parts):
    return '.'.join(map(str, parts))


def fetch_latest(url=API_URL, timeout=TIMEOUT, max_bytes=MAX_BYTES):
    """GET de la API de GitHub; devuelve como mucho ``max_bytes + 1`` bytes."""
    request = Request(url, headers={
        'User-Agent': f'PokemonTracker/{__version__} (+https://github.com/joanjuz/NuzlockeTracker)',
        'Accept': 'application/vnd.github+json',
    })
    with urlopen(request, timeout=timeout) as response:
        if getattr(response, 'status', 200) != 200:
            raise OSError(f'HTTP {response.status}')
        return response.read(max_bytes + 1)


def parse_release(raw, max_bytes=MAX_BYTES):
    """Valida la respuesta y devuelve {'latest': '1.2.3', 'url': ...}.

    Lanza ValueError si no es un objeto JSON con un tag_name tipo v1.2.3.
    Un html_url fuera de las releases del repositorio se sustituye por el
    enlace genérico: nunca se enlaza a otro sitio.
    """
    if not isinstance(raw, (bytes, bytearray)) or len(raw) > max_bytes:
        raise ValueError('Respuesta vacía o demasiado grande')
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError('La respuesta no es un objeto JSON')
    version = parse_version(data.get('tag_name'))
    if version is None:
        raise ValueError('tag_name sin formato vX.Y.Z')
    url = data.get('html_url')
    if not (isinstance(url, str) and url.startswith(RELEASES_PREFIX) and len(url) <= 300
            and not any(ch.isspace() for ch in url)):
        url = FALLBACK_URL
    return {'latest': _version_text(version), 'url': url}


def empty_status(current=__version__):
    return {'current': current, 'latest': None, 'update_available': False,
            'url': FALLBACK_URL, 'checked_at': None}


class UpdateChecker:
    """Hilo en segundo plano que mantiene el último resultado conocido.

    ``fetcher(url, timeout, max_bytes) -> bytes`` se puede sustituir en pruebas.
    Ningún método público lanza excepciones.
    """

    def __init__(self, cache_path, current=__version__, fetcher: Callable | None = None,
                 enabled=None, initial_delay=INITIAL_DELAY, interval=INTERVAL, env=None):
        env = os.environ if env is None else env
        self.cache_path = Path(cache_path) if cache_path is not None else None
        self.current = current
        self.fetcher = fetcher or fetch_latest
        disabled_by_env = env.get(DISABLE_ENV, '').strip() == '1'
        self.enabled = (True if enabled is None else bool(enabled)) and not disabled_by_env
        self.initial_delay = initial_delay
        self.interval = interval
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None
        self._result = self._load_cache()

    # --- estado -------------------------------------------------------------
    def status(self):
        with self._lock:
            result = dict(self._result) if self._result else None
        status = empty_status(self.current)
        if not result:
            return status
        latest, current = parse_version(result.get('latest')), parse_version(self.current)
        status.update(latest=result.get('latest'), url=result.get('url') or FALLBACK_URL,
                      checked_at=result.get('checked_at'),
                      update_available=bool(latest and current and latest > current))
        return status

    def check_now(self):
        """Una consulta síncrona. Devuelve True si se obtuvo un resultado."""
        if not self.enabled:
            return False
        try:
            release = parse_release(self.fetcher(API_URL, TIMEOUT, MAX_BYTES))
        except Exception as exc:  # noqa: BLE001 - un aviso nunca debe romper la app
            log.warning('No se pudo comprobar si hay una versión nueva: %s: %s',
                        type(exc).__name__, str(exc)[:200])
            return False
        release['checked_at'] = datetime.now(timezone.utc).isoformat(timespec='seconds')
        with self._lock:
            self._result = release
        self._save_cache(release)
        log.info('Versión actual %s, última publicada %s', self.current, release['latest'])
        return True

    # --- ciclo de vida ------------------------------------------------------
    def start(self):
        if not self.enabled:
            log.info('Comprobación de actualizaciones desactivada')
            return self
        with self._lock:
            if self._thread is not None:
                return self
            self._stop.clear()
            self._thread = threading.Thread(target=self._run, name='tracker-updates', daemon=True)
            self._thread.start()
        return self

    def close(self, timeout=2.0):
        self._stop.set()
        with self._lock:
            thread, self._thread = self._thread, None
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=timeout)

    def _run(self):
        delay = self.initial_delay
        while not self._stop.wait(delay):
            self.check_now()
            delay = self.interval

    # --- caché --------------------------------------------------------------
    def _load_cache(self):
        if self.cache_path is None:
            return None
        try:
            data = json.loads(self.cache_path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return None
        if not isinstance(data, dict) or parse_version(data.get('latest')) is None:
            return None
        url = data.get('url')
        checked = data.get('checked_at')
        return {'latest': _version_text(parse_version(data['latest'])),
                'url': url if isinstance(url, str) and url.startswith(RELEASES_PREFIX) else FALLBACK_URL,
                'checked_at': checked if isinstance(checked, str) and len(checked) <= 40 else None}

    def _save_cache(self, result):
        if self.cache_path is None:
            return
        tmp = self.cache_path.with_name(f'.{self.cache_path.name}.{threading.get_ident()}.tmp')
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                tmp.write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
                tmp.replace(self.cache_path)
            finally:
                tmp.unlink(missing_ok=True)
        except OSError as exc:
            log.warning('No se pudo guardar %s: %s', self.cache_path.name, type(exc).__name__)
