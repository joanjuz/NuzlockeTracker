"""Conjuntos de sprites personalizados (subcarpetas) y búsqueda segura de archivos.

`sprites_personalizados/` puede contener subcarpetas, cada una un conjunto
(por ejemplo `HD/`, `Pixel/`, `Shiny-hunt/`). El overlay usa el conjunto
elegido y, si un archivo no está ahí, recurre a la carpeta raíz.
`objetos/` (en la raíz o dentro de un conjunto) guarda iconos de objetos.

Solo se leen archivos regulares directamente dentro de carpetas conocidas:
nunca rutas del cliente, enlaces simbólicos ni uniones de directorio.
"""
from __future__ import annotations

import os
import re
import threading
import time
from pathlib import Path
from typing import Iterable

from .layout_export import CUSTOM_EXTENSIONS, normalize_custom_sprite, safe_sprite_stem

SET_NAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9 _-]{0,39}')
ITEMS_FOLDER = 'objetos'
RESERVED = {ITEMS_FOLDER}
MAX_SETS = 64


def _is_link(path: Path) -> bool:
    try:
        return path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction())
    except OSError:
        return True


def valid_set_name(name) -> bool:
    return (isinstance(name, str) and SET_NAME.fullmatch(name) is not None
            and name.strip() == name and name.casefold() not in RESERVED)


def list_sets(root) -> list[str]:
    """Visible subfolders usable as sprite sets (sorted, case-insensitive)."""
    root = Path(root)
    if not root.is_dir():
        return []
    found = []
    try:
        for child in root.iterdir():
            if child.is_dir() and not _is_link(child) and valid_set_name(child.name):
                found.append(child.name)
    except OSError:
        return []
    return sorted(found, key=str.casefold)[:MAX_SETS]


def canonical_set(root, name) -> str | None:
    """Real folder name of a set, matched without case (Windows/NTFS semantics)."""
    if not name or not valid_set_name(name):
        return None
    wanted = name.casefold()
    for existing in list_sets(root):
        if existing.casefold() == wanted:
            return existing
    return None


def is_link(path: Path) -> bool:
    return _is_link(path)


def set_directory(root, name) -> Path | None:
    """The folder of a set, only if it is a real direct child of root."""
    real = canonical_set(root, name)
    if real is None:
        return None
    candidate = Path(root) / real
    if not candidate.is_dir() or _is_link(candidate):
        return None
    if candidate.resolve().parent != Path(root).resolve():
        return None
    return candidate


def search_dirs(root, sprite_set: str = '', sub: str = '') -> list[Path]:
    """Folders to search in priority order: chosen set first, then root."""
    root = Path(root)
    dirs = []
    chosen = set_directory(root, sprite_set)
    if chosen is not None:
        dirs.append(chosen / sub if sub else chosen)
    dirs.append(root / sub if sub else root)
    return [d for d in dirs if d.is_dir() and not _is_link(d)]


_listing_lock = threading.Lock()
_listings: dict[str, tuple[int, float, dict[str, Path]]] = {}
# NTFS does not always bump a folder's mtime between two quick writes, so a
# cached listing also expires after a short time (re-reading costs ~2 ms).
LISTING_TTL = 2.0


def clear_listing_cache(folder: Path | None = None) -> None:
    with _listing_lock:
        if folder is None:
            _listings.clear()
        else:
            _listings.pop(str(folder), None)


def listing(folder: Path) -> dict[str, Path]:
    """casefold(name) -> file for the regular files directly in `folder`.

    Sprite sets can hold thousands of files and are looked up several times a
    second, so the listing is cached until the folder's modification time
    changes or LISTING_TTL seconds pass, whichever comes first.
    """
    try:
        stamp = folder.stat().st_mtime_ns
    except OSError:
        return {}
    key = str(folder)
    now = time.monotonic()
    with _listing_lock:
        cached = _listings.get(key)
        if cached and cached[0] == stamp and now - cached[1] < LISTING_TTL:
            return cached[2]
    available: dict[str, Path] = {}
    try:
        with os.scandir(folder) as entries:
            for entry in entries:
                if entry.is_file(follow_symlinks=False):
                    available.setdefault(entry.name.casefold(), Path(entry.path))
    except OSError:
        return {}
    with _listing_lock:
        if len(_listings) > 64:
            _listings.clear()
        _listings[key] = (stamp, now, available)
    return available


def find_file(dirs: Iterable[Path], names: Iterable[str]) -> Path | None:
    """First regular file whose name matches (case-insensitive), dir by dir."""
    wanted = [n.casefold() for n in names]
    for folder in dirs:
        available = listing(folder)
        for name in wanted:
            if name in available:
                return available[name]
    return None


def item_icon_names(item_id: int, slug: str | None, name: str | None) -> tuple[str, ...]:
    """File names accepted for a custom item icon: 234.png, leftovers.png, restos.png…"""
    stems = [str(item_id), f'{item_id:03d}']
    if slug:
        stems.append(slug)
    alias = safe_sprite_stem(name or '')
    if alias:
        stems.append(alias)
    stems = list(dict.fromkeys(stems))
    return tuple(stem + ext for ext in CUSTOM_EXTENSIONS for stem in stems)


MEDIA_TYPES = {'png': 'image/png', 'apng': 'image/apng', 'gif': 'image/gif', 'webp': 'image/webp'}


def load_media(path: Path) -> tuple[bytes, str] | None:
    """Validated (bytes, kind) for a custom file, or None when unreadable."""
    try:
        if path.stat().st_size > 8_000_000:
            return None
        return normalize_custom_sprite(path.read_bytes(), path.suffix.lower())
    except (OSError, ValueError):
        return None


def safe_import_name(name) -> tuple[str, str]:
    """(stem, extension) for an uploaded file name, or ValueError."""
    if not isinstance(name, str) or not re.fullmatch(
            r'[A-Za-z0-9_-]{1,80}\.(?:png|apng|gif|webp|jpe?g|bmp)', name, re.IGNORECASE):
        raise ValueError('Nombre de archivo inválido. Usa letras, números, - o _')
    stem, ext = name.rsplit('.', 1)
    return stem, '.' + ext.lower()


def write_atomic(target: Path, raw: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_symlink():
        raise ValueError('No se permite sobrescribir enlaces simbólicos')
    tmp = target.with_name('.' + target.name + '.tmp')
    try:
        tmp.write_bytes(raw)
        os.replace(tmp, target)
    finally:
        tmp.unlink(missing_ok=True)
    clear_listing_cache(target.parent)  # an import is visible immediately
