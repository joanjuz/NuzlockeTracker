"""Six PNG sprites for OBS layouts, updated from the LOCAL party only.

No save modification, browser needed or cloud credentials included. Empty slots
are transparent 96x96 PNG files. Downloads are asynchronous and cached.
"""
from __future__ import annotations

import os
import struct
import sys
import threading
import time
import urllib.request
import zlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# PokeAPI sprite IDs for Gen7 Alolan variants. Do not show the Kanto sprite
# when an Alolan species has been detected.
ALOLA_SPRITES = {
    19: 10091, 20: 10092, 26: 10100, 27: 10101, 28: 10102,
    37: 10103, 38: 10104, 50: 10105, 51: 10106, 52: 10107,
    53: 10108, 74: 10109, 75: 10110, 76: 10111, 88: 10112,
    89: 10113, 103: 10114, 105: 10115,
}
PNG_MAGIC = b'\x89PNG\r\n\x1a\n'


def _chunk(name, data):
    return struct.pack('>I', len(data)) + name + data + struct.pack(
        '>I', zlib.crc32(name + data) & 0xffffffff)


def blank_sprite(size=96):
    """Fixed transparent canvas avoids OBS resizing a slot when it is empty."""
    raw = b''.join(b'\x00' + bytes(size * 4) for _ in range(size))
    return (PNG_MAGIC + _chunk(b'IHDR', struct.pack('>IIBBBBB', size, size, 8, 6, 0, 0, 0))
            + _chunk(b'IDAT', zlib.compress(raw, 9)) + _chunk(b'IEND', b''))


BLANK_PNG = blank_sprite()


def sprite_id(mon):
    if not isinstance(mon, dict):
        return None
    species = mon.get('species_id')
    if type(species) is not int or not 1 <= species <= 807 or mon.get('egg'):
        return None
    if mon.get('form') == 1 and species in ALOLA_SPRITES:
        return ALOLA_SPRITES[species]
    return species


def validate_png(data):
    if not isinstance(data, bytes) or not (33 <= len(data) <= 500_000):
        raise ValueError('Sprite PNG inválido')
    if not data.startswith(PNG_MAGIC) or data[12:16] != b'IHDR':
        raise ValueError('Cabecera PNG inválida')
    width, height = struct.unpack_from('>II', data, 16)
    if not (1 <= width <= 512 and 1 <= height <= 512):
        raise ValueError('Dimensiones PNG inválidas')
    return data


def fetch_sprite(identifier):
    if not 1 <= identifier <= 10115:
        raise ValueError('Identificador fuera de rango')
    url = 'https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/' + str(identifier) + '.png'
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=8) as response:
        return validate_png(response.read(500_001))


def layout_directory(home, profile='principal', executable=None, frozen=None):
    """Portable next-to-EXE when writable, otherwise persistent AppData fallback."""
    home = Path(home)
    if frozen is None:
        frozen = getattr(sys, 'frozen', False)
    if frozen:
        parent = Path(executable or sys.executable).resolve().parent
        try:
            parent.mkdir(parents=True, exist_ok=True)
            test = parent / '.layout-write-test'
            with open(test, 'wb') as f:
                f.write(b'x')
            test.unlink()
            base = parent / 'layout'
        except OSError:
            base = home / 'layout'
    else:
        base = home / 'layout'
    return base if profile == 'principal' else base / 'perfil_2'


class PartyLayoutExporter:
    def __init__(self, service, directory, cache_dir=None, downloader=fetch_sprite, bundled=None):
        self.service = service
        self.directory = Path(directory)
        self.cache = Path(cache_dir or self.directory.parent / 'sprite-cache')
        self.bundled = Path(bundled or (Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent)) / 'data' / 'sprites'))
        self.downloader = downloader
        self.stop = threading.Event()
        self.thread = None
        self.pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix='layout-sprite')
        self.futures = {}
        self.retry_after = {}
        self.slots = [None] * 6
        self.contents = [None] * 6
        self.directory.mkdir(parents=True, exist_ok=True)
        # Guarantee six files immediately, including slots that are empty.
        for index in range(6):
            self.write_slot(index, BLANK_PNG)

    def write_slot(self, index, data):
        if self.contents[index] == data:
            return
        name = self.directory / f'pokemon_{index+1}.png'
        tmp = self.directory / f'.pokemon_{index+1}.{os.getpid()}.tmp'
        try:
            tmp.write_bytes(data)
            os.replace(tmp, name)
            self.contents[index] = data
        finally:
            if tmp.exists():
                tmp.unlink()

    def local_sprite(self, ident):
        for folder in (self.cache, self.bundled):
            candidate = folder / f'{ident}.png'
            if candidate.is_file():
                try:
                    return validate_png(candidate.read_bytes())
                except (OSError, ValueError):
                    continue
        return None

    def download_and_store(self, ident):
        data = validate_png(self.downloader(ident))
        self.cache.mkdir(parents=True, exist_ok=True)
        tmp = self.cache / f'.{ident}.{os.getpid()}.tmp'
        try:
            tmp.write_bytes(data)
            os.replace(tmp, self.cache / f'{ident}.png')
        finally:
            if tmp.exists():
                tmp.unlink()
        return data

    def refresh(self):
        party = self.service.snapshot().get('party') or []
        ids = [sprite_id(party[i] if i < len(party) else None) for i in range(6)]
        now = time.monotonic()
        for i, ident in enumerate(ids):
            if ident is None:
                self.slots[i] = None
                self.write_slot(i, BLANK_PNG)
                continue
            local = self.local_sprite(ident)
            if local is not None:
                self.slots[i] = ident
                self.write_slot(i, local)
                continue
            if self.slots[i] != ident:
                # Never leave the previous Pokémon visible while the new one downloads.
                self.slots[i] = ident
                self.write_slot(i, BLANK_PNG)
            future = self.futures.get(ident)
            if future and future.done():
                del self.futures[ident]
                try:
                    self.write_slot(i, future.result())
                except Exception:
                    self.retry_after[ident] = now + 30
            elif future is None and now >= self.retry_after.get(ident, 0):
                self.futures[ident] = self.pool.submit(self.download_and_store, ident)

    def run(self):
        while not self.stop.is_set():
            try:
                self.refresh()
            except Exception:
                # Layout is optional: no failure may stop the RAM or cloud worker.
                pass
            with self.service.condition:
                self.service.condition.wait(timeout=0.5)

    def start(self):
        if self.thread is not None:
            return
        self.thread = threading.Thread(target=self.run, name='layout-export', daemon=True)
        self.thread.start()

    def close(self):
        self.stop.set()
        with self.service.condition:
            self.service.condition.notify_all()
        if self.thread:
            self.thread.join(timeout=3)
        self.pool.shutdown(wait=False, cancel_futures=True)
