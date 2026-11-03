"""Six stable image slots for OBS, preserving both static PNG and animated GIF.

Local-only layout output; all six slots always have PNG + GIF counterparts.
Never mutate source sprites, game saves, emulator memory or cloud credentials.

Image validation/conversion lives in tracker.sprite_images; its public names
are re-exported here so existing imports (overlay, custom sprites, API, tests)
keep working unchanged.
"""
from __future__ import annotations

import logging
import os
import re
import sys
import threading
import time
import unicodedata
import urllib.request
from collections.abc import Callable, Mapping
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from typing import Any, Protocol

from .progress import pokemon_key
from .sprite_images import (
    BLANK_PNG,
    CUSTOM_EXTENSIONS,
    GIF_MAGIC,
    MAX_GIF_BYTES,
    MAX_GIF_FRAME_PIXELS,
    MAX_GIF_FRAMES,
    MAX_GIF_TOTAL_PIXELS,
    PNG_MAGIC,
    _chunk,
    animation_frames,
    animation_to_webp,
    blank_sprite,
    gif_to_outputs,
    grayscale_png,
    normalize_custom_sprite,
    png_to_gif,
    validate_gif,
    validate_png,
)

__all__ = [
    'ALOLA_SPRITES', 'BLANK_PNG', 'CUSTOM_EXTENSIONS', 'GIF_MAGIC', 'MAX_GIF_BYTES',
    'MAX_GIF_FRAMES', 'MAX_GIF_FRAME_PIXELS', 'MAX_GIF_TOTAL_PIXELS', 'PNG_MAGIC',
    'PartyLayoutExporter', '_chunk', 'animation_frames', 'animation_to_webp',
    'blank_sprite', 'custom_media_names', 'custom_names', 'fetch_sprite',
    'gif_to_outputs', 'grayscale_png', 'layout_directory', 'normalize_custom_sprite',
    'png_to_gif', 'safe_sprite_stem', 'sprite_id', 'validate_gif', 'validate_png',
]

# Pokémon dict as produced by tracker/pokemon.py (party, boxes, deaths).
Pokemon = dict[str, Any]
# (bytes, kind) where kind is 'png', 'gif', 'webp' or 'apng'.
Media = tuple[bytes, str]


class LayoutService(Protocol):
    """Subset of TrackerService the exporter needs (read-only)."""
    condition: threading.Condition

    def snapshot(self) -> dict[str, Any]: ...


# PokeAPI sprite IDs for Gen7 Alolan variants. Do not show the Kanto sprite
# when an Alolan species has been detected.
ALOLA_SPRITES = {
    19: 10091, 20: 10092, 26: 10100, 27: 10101, 28: 10102,
    37: 10103, 38: 10104, 50: 10105, 51: 10106, 52: 10107,
    53: 10108, 74: 10109, 75: 10110, 76: 10111, 88: 10112,
    89: 10113, 103: 10114, 105: 10115,
}


def sprite_id(mon: object) -> int | None:
    if not isinstance(mon, dict):
        return None
    species = mon.get('species_id')
    if type(species) is not int or not 1 <= species <= 807 or mon.get('egg'):
        return None
    if mon.get('form') == 1 and species in ALOLA_SPRITES:
        return ALOLA_SPRITES[species]
    return species


def safe_sprite_stem(value: object) -> str:
    """Normalize friendly names to safe file stems, never to paths."""
    if not isinstance(value, str):
        return ''
    base = unicodedata.normalize('NFKD', value).casefold()
    base = ''.join(c for c in base if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+', '-', base).strip('-')[:80]


def custom_media_names(mon: Pokemon, ident: int) -> tuple[str, ...]:
    """Allow National Dex, padded ID, names, regional variants and shiny names.

    All returned names are flat filenames; files never leave the custom directory.
    GIF/WebP animation takes priority for each *identity*, then lossless PNG.
    """
    species = mon['species_id']
    padded = f'{species:03d}'
    base = [str(species), padded, str(ident)]
    alias = safe_sprite_stem(mon.get('species') or '')
    if alias:
        base.append(alias)
    if mon.get('form') == 1 and species in ALOLA_SPRITES:
        base = ([f'{species}-alola', f'{padded}-alola',
                 f'{species}_alola', f'{padded}_alola',
                 f'{alias}-alola' if alias else '',
                 str(ident)] + base)
    form = mon.get('form')
    if type(form) is int and form > 0 and not (form == 1 and species in ALOLA_SPRITES):
        base = [f'{species}-{form}', f'{padded}-{form}',
                f'{alias}-{form}' if alias else ''] + base
    if mon.get('shiny') or mon.get('is_shiny'):
        base = ([stem+ending for stem in base for ending in ('-shiny','_shiny','-s')]
                + base)
    stems = list(dict.fromkeys(stem for stem in base if stem))
    # Preserve old behaviour: animation before any static image.
    return tuple(stem+ext for ext in CUSTOM_EXTENSIONS for stem in stems)


def custom_names(mon: Pokemon, ident: int) -> tuple[str, ...]:
    """Species National Dex ID; regional names override their numeric form ID."""
    species = mon['species_id']
    if mon.get('form') == 1 and species in ALOLA_SPRITES:
        return (f'{species}-alola.png', f'{ident}.png')
    return (f'{species}.png',)


def fetch_sprite(identifier: int) -> bytes:
    if not 1 <= identifier <= 10115:
        raise ValueError('Identificador fuera de rango')
    url = 'https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/' + str(identifier) + '.png'
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=8) as response:
        return validate_png(response.read(500_001))


def layout_directory(home: str | os.PathLike[str], profile: str = 'principal',
                     executable: str | os.PathLike[str] | None = None,
                     frozen: bool | None = None) -> Path:
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
    def __init__(self, service: LayoutService, directory: str | os.PathLike[str],
                 cache_dir: str | os.PathLike[str] | None = None,
                 downloader: Callable[[int], bytes] = fetch_sprite,
                 bundled: str | os.PathLike[str] | None = None,
                 custom_dir: str | os.PathLike[str] | None = None,
                 sprite_set: Callable[[], str | None] | None = None) -> None:
        self.service = service
        # Callable returning the selected sprite set (subfolder) or ''.
        self.sprite_set: Callable[[], str | None] = sprite_set if callable(sprite_set) else (lambda: '')
        self.directory = Path(directory)
        self.cache = Path(cache_dir or self.directory.parent / 'sprite-cache')
        self.custom = Path(custom_dir or self.directory.parent / 'sprites_personalizados')
        self.bundled = Path(bundled or (Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent)) / 'data' / 'sprites'))
        self.downloader = downloader
        self.stop = threading.Event()
        self.thread: threading.Thread | None = None
        self.pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix='layout-sprite')
        self.futures: dict[int, Future[bytes]] = {}
        self.retry_after: dict[int, float] = {}
        # futures/retry_after are shared with HTTP threads (sprite_for).
        self.futures_lock = threading.Lock()
        self.slots: list[int | None] = [None] * 6
        self.contents: list[bytes | None] = [None] * 6
        self.gif_contents: list[bytes | None] = [None] * 6
        self.render_signatures: list[tuple[int, bool, bool | str, bytes] | None] = [None] * 6
        self.media_types: list[str | None] = [None] * 6
        # path -> (mtime_ns, size), validated media or None
        self.custom_cache: dict[Path, tuple[tuple[int, int], Media | None]] = {}
        self.last_error: str | None = None  # last per-slot failure, for diagnostics
        self.directory.mkdir(parents=True, exist_ok=True)
        self.custom.mkdir(parents=True, exist_ok=True)
        # Guarantee six files immediately, including slots that are empty.
        self.blank_gif = png_to_gif(BLANK_PNG)
        for index in range(6):
            self.write_slot(index, BLANK_PNG)
            self.write_gif_slot(index, self.blank_gif)
            self.write_media_type(index, 'png')

    def write_slot(self, index: int, data: bytes) -> None:
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

    def write_gif_slot(self, index: int, data: bytes) -> None:
        if self.gif_contents[index] == data:
            return
        name = self.directory / f'pokemon_{index+1}.gif'
        tmp = self.directory / f'.pokemon_{index+1}.{os.getpid()}.gif.tmp'
        try:
            tmp.write_bytes(data)
            os.replace(tmp, name)
            self.gif_contents[index] = data
        finally:
            if tmp.exists():
                tmp.unlink()

    def write_media_type(self, index: int, kind: str) -> None:
        if self.media_types[index]==kind:
            return
        target=self.directory/f'pokemon_{index+1}.media'
        tmp=self.directory/f'.pokemon_{index+1}.{os.getpid()}.media.tmp'
        try:
            tmp.write_text(kind,encoding='ascii')
            os.replace(tmp,target)
            self.media_types[index]=kind
        finally:
            tmp.unlink(missing_ok=True)

    def write_webp_slot(self, index: int, data: bytes) -> None:
        target=self.directory/f'pokemon_{index+1}.webp'
        tmp=self.directory/f'.pokemon_{index+1}.{os.getpid()}.webp.tmp'
        try:
            tmp.write_bytes(data)
            os.replace(tmp,target)
        finally:
            tmp.unlink(missing_ok=True)

    def publish(self, index: int, ident: int, source: bytes,
                animated: bool | str = False, dead: bool = False) -> None:
        """Expose the original visual format, not an indexed GIF for every PNG."""
        signature = (ident, dead, animated, source)
        if self.render_signatures[index] == signature:
            return
        if animated == 'webp' or animated == 'apng':
            png, webp=animation_to_webp(source,animated,dead=dead)
            self.write_slot(index,png)
            # Legacy GIF slot preserved for existing OBS setups (first frame).
            self.write_gif_slot(index,png_to_gif(png))
            self.write_webp_slot(index,webp)
            self.write_media_type(index,'webp')
        elif animated is True or animated == 'gif':
            png,gif=gif_to_outputs(source,dead=dead)
            self.write_slot(index,png)
            self.write_gif_slot(index,gif)
            self.write_media_type(index,'gif')
        else:
            png=self.render_sprite(source,dead)
            self.write_slot(index,png)
            self.write_gif_slot(index,png_to_gif(png))
            self.write_media_type(index,'png')
        self.render_signatures[index]=signature

    def clear_slot(self, index: int) -> None:
        self.render_signatures[index]=None
        self.write_slot(index,BLANK_PNG)
        self.write_gif_slot(index,self.blank_gif)
        self.write_media_type(index,'png')

    def local_sprite(self, ident: int) -> bytes | None:
        for folder in (self.cache, self.bundled):
            candidate = folder / f'{ident}.png'
            if candidate.is_file():
                try:
                    return validate_png(candidate.read_bytes())
                except (OSError, ValueError):
                    continue
        return None

    def custom_media(self, mon: Pokemon, ident: int) -> Media | None:
        from .custom_sprites import sprite_dirs
        if not self.custom.is_dir():return None
        try:
            chosen=self.sprite_set() or ''
        except Exception:
            chosen=''
        # Resolve case-insensitively, including names such as Pikachu.PNG.
        # Selected set first, then the root folder; files never leave them.
        names=custom_media_names(mon,ident)
        for folder in sprite_dirs(self.custom,chosen,mon):
            media=self._custom_media_in(folder,names)
            if media is not None:return media
        return None

    def _custom_media_in(self, folder: Path, names: tuple[str, ...]) -> Media | None:
        from .custom_sprites import listing
        available=listing(folder)  # cached until the folder changes
        for name in names:
            candidate=available.get(name.casefold())
            if candidate is None:continue
            try:
                stat=candidate.stat()
                signature=(stat.st_mtime_ns,stat.st_size)
                cached=self.custom_cache.get(candidate)
                if cached and cached[0]==signature:
                    if cached[1] is not None:return cached[1]
                    continue
                media=None
                if stat.st_size<=8_000_000:
                    try:
                        media=normalize_custom_sprite(candidate.read_bytes(),
                                                       candidate.suffix.lower())
                    except (OSError,ValueError):
                        pass
                if len(self.custom_cache)>96:self.custom_cache.clear()
                self.custom_cache[candidate]=(signature,media)
                if media is not None:return media
            except OSError:
                self.custom_cache.pop(candidate,None)
        return None

    def sprite_for(self, mon: Pokemon, download: bool = True) -> Media | None:
        """Media for any Pokémon (e.g. the OBS graveyard) without blocking.

        Returns (bytes, kind) from the custom set, cache or bundled sprites;
        otherwise schedules a download and returns None until it finishes.
        """
        ident = sprite_id(mon)
        if ident is None:
            return None
        custom = self.custom_media(mon, ident)
        if custom is not None:
            return custom
        local = self.local_sprite(ident)
        if local is not None:
            return local, 'png'
        now = time.monotonic()
        with self.futures_lock:
            future = self.futures.get(ident)
            if future is None and not download:
                return None  # read-only VPN viewers never trigger downloads
            if future is None and now >= self.retry_after.get(ident, 0):
                self.futures[ident] = self.pool.submit(self.download_and_store, ident)
                return None
            if future is None or not future.done():
                return None
            del self.futures[ident]
        try:
            return future.result(), 'png'
        except Exception:
            with self.futures_lock:
                self.retry_after[ident] = now + 30
        return None

    def render_sprite(self, data: bytes, dead: bool) -> bytes:
        return grayscale_png(data) if dead else data

    def download_and_store(self, ident: int) -> bytes:
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

    def _state(self) -> dict[str, Any]:
        # Only the party and the death keys are needed: avoid deep-copying the
        # 32-box cache twice per second when the service offers a narrow copy.
        fields = getattr(self.service, 'snapshot_fields', None)
        if callable(fields):
            state: dict[str, Any] = fields('party', 'progress')
            return state
        return self.service.snapshot()

    def refresh(self) -> None:
        state = self._state()
        party = state.get('party') or []
        deaths = (state.get('progress') or {}).get('deaths') or {}
        now = time.monotonic()
        failed = None
        for i in range(6):
            mon = party[i] if i < len(party) else None
            try:
                self._refresh_slot(i, mon, deaths, now)
            except Exception as exc:
                # One bad sprite (huge animation, damaged custom file) must not
                # freeze the remaining slots or leave a dead Pokémon in color.
                failed = f'Pokémon {i+1}: {exc}'
                self._fallback_slot(i, mon, deaths)
        # Diagnostics show the current problem only, not one already solved.
        if failed != self.last_error:
            if failed:
                logging.getLogger('tracker.sprites').warning('Sprite OBS: %s', failed)
            elif self.last_error:
                logging.getLogger('tracker.sprites').info('Sprites OBS recuperados')
        self.last_error = failed

    def _fallback_slot(self, i: int, mon: Pokemon | None, deaths: Mapping[str, Any]) -> None:
        ident = sprite_id(mon)
        if ident is None or mon is None:
            return
        local = self.local_sprite(ident)
        if local is None:
            return
        try:
            self.publish(i, ident, local, dead=pokemon_key(mon) in deaths)
            self.slots[i] = ident
        except Exception:
            pass  # refresh() already records this slot's error.

    def _refresh_slot(self, i: int, mon: Pokemon | None, deaths: Mapping[str, Any], now: float) -> None:
        ident = sprite_id(mon)
        if ident is None or mon is None:
            self.slots[i] = None
            self.clear_slot(i)
            return
        dead = pokemon_key(mon) in deaths
        # User PNG/GIF changes are picked up on the next refresh.
        # Animation conversion is cached when all inputs are unchanged.
        custom = self.custom_media(mon, ident)
        if custom is not None:
            raw,kind=custom
            self.slots[i]=ident
            self.publish(i,ident,raw,animated=kind if kind!='png' else False,dead=dead)
            return
        local = self.local_sprite(ident)
        if local is not None:
            self.slots[i] = ident
            self.publish(i, ident, local, dead=dead)
            return
        if self.slots[i] != ident:
            self.slots[i] = ident
            self.clear_slot(i)
        with self.futures_lock:
            future = self.futures.get(ident)
            if future and future.done():
                del self.futures[ident]
            elif future is None and now >= self.retry_after.get(ident, 0):
                self.futures[ident] = self.pool.submit(self.download_and_store, ident)
                future = None
            else:
                future = None
        if future is not None:
            try:
                # Only use the downloaded sprite for the species currently
                # occupying this slot; keep custom priority intact.
                self.publish(i, ident, future.result(), dead=dead)
            except Exception:
                with self.futures_lock:
                    self.retry_after[ident] = now + 30

    def run(self) -> None:
        while not self.stop.is_set():
            try:
                self.refresh()
            except Exception:
                # Layout is optional: no failure may stop the RAM or cloud worker.
                pass
            with self.service.condition:
                self.service.condition.wait(timeout=0.5)

    def start(self) -> None:
        if self.thread is not None:
            return
        self.thread = threading.Thread(target=self.run, name='layout-export', daemon=True)
        self.thread.start()

    def close(self) -> None:
        self.stop.set()
        with self.service.condition:
            self.service.condition.notify_all()
        if self.thread:
            self.thread.join(timeout=3)
        self.pool.shutdown(wait=False, cancel_futures=True)
