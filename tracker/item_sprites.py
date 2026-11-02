"""Iconos de objetos equipados (sprites de PokeAPI) con caché local.

data/ItemSprites.json traduce el índice interno del objeto (el mismo que lee
el tracker de la RAM) al nombre de archivo de PokeAPI. La imagen se descarga
una sola vez, se valida como PNG pequeño y se guarda en sprite-cache/items/.
Solo se admiten nombres de la tabla: nunca rutas ni URL del cliente.
"""
from __future__ import annotations

import json
import os
import re
import sys
import threading
import time
import urllib.request
from urllib.error import HTTPError
from pathlib import Path
from typing import Callable

from .layout_export import validate_png

DATA = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent)) / 'data' / 'ItemSprites.json'
SLUG = re.compile(r'[a-z0-9]+(?:-{1,2}[a-z0-9]+)*')
MAX_ITEM_ID = 2000
MAX_ICON_BYTES = 200_000
RETRY_SECONDS = 60.0
NETWORK_BACKOFF = 30.0


def fetch_item_png(slug: str) -> bytes:
    if not SLUG.fullmatch(slug) or len(slug) > 60:
        raise ValueError('Nombre de objeto inválido')
    url = 'https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/items/' + slug + '.png'
    request = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(request, timeout=8) as response:
        raw = response.read(MAX_ICON_BYTES + 1)
    if len(raw) > MAX_ICON_BYTES:
        raise ValueError('Icono demasiado grande')  # never cache a truncated PNG
    return validate_png(raw)


class ItemSprites:
    def __init__(self, cache_dir, downloader: Callable[[str], bytes] = fetch_item_png, data_path=DATA,
                 allow_download: bool = True):
        self.directory = Path(cache_dir) / 'items'
        self.downloader = downloader
        # The read-only VPN share serves cached icons only: a remote viewer
        # must not be able to make this computer download the whole table.
        self.allow_download = allow_download
        self.lock = threading.Lock()  # guards the dictionaries below
        self.slug_locks: dict[str, threading.Lock] = {}
        self.retry_after: dict[str, float] = {}
        self.offline_until = 0.0
        try:
            data = json.loads(Path(data_path).read_text(encoding='utf-8'))
            self.mapping: dict[str, str] = dict(data.get('gen7') or {})
            self.gen6_overrides: dict[str, str] = dict(data.get('gen6_overrides') or {})
        except (OSError, ValueError, AttributeError):
            self.mapping, self.gen6_overrides = {}, {}

    def slug(self, item_id, generation: int = 7) -> str | None:
        if type(item_id) is not int or not 0 < item_id <= MAX_ITEM_ID:
            return None
        key = str(item_id)
        name = self.gen6_overrides.get(key) if generation == 6 else None
        name = name or self.mapping.get(key)
        return name if isinstance(name, str) and SLUG.fullmatch(name) else None

    def png(self, item_id, generation: int = 7) -> bytes | None:
        name = self.slug(item_id, generation)
        if name is None:
            return None
        path = self.directory / f'{name}.png'
        try:
            return validate_png(path.read_bytes())
        except (OSError, ValueError):
            pass
        if not self.allow_download:
            return None
        with self.lock:
            now = time.monotonic()
            if now < self.offline_until or now < self.retry_after.get(name, 0.0):
                return None
            slug_lock = self.slug_locks.setdefault(name, threading.Lock())
        # One download per icon; different icons never wait for each other.
        with slug_lock:
            try:
                return validate_png(path.read_bytes())  # fetched while we waited
            except (OSError, ValueError):
                pass
            try:
                raw = self.downloader(name)
            except HTTPError:
                # The server answered (e.g. 404): only this icon is unavailable.
                with self.lock:
                    self.retry_after[name] = time.monotonic() + RETRY_SECONDS
                return None
            except OSError:
                with self.lock:
                    # No network: stop trying every icon for a while.
                    self.offline_until = time.monotonic() + NETWORK_BACKOFF
                    self.retry_after[name] = time.monotonic() + RETRY_SECONDS
                return None
            except ValueError:
                with self.lock:
                    self.retry_after[name] = time.monotonic() + RETRY_SECONDS
                return None
            try:
                self.directory.mkdir(parents=True, exist_ok=True)
                tmp = self.directory / f'.{name}.{os.getpid()}.tmp'
                try:
                    tmp.write_bytes(raw)
                    os.replace(tmp, path)
                finally:
                    tmp.unlink(missing_ok=True)
            except OSError:
                pass  # Show it anyway; the cache folder may be read-only.
            return raw
