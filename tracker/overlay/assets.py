"""Archivos del overlay: fuentes, PNG de barra/contador/marco, imagen de muerte e importaciones.

Solo se sirven nombres conocidos; nunca rutas que vengan del cliente.
"""
from __future__ import annotations

import base64
import io
import os
import re
import sys
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from .. import custom_sprites
from ..layout_export import normalize_custom_sprite
from .settings import font_is_valid

PNG_KINDS = ('fill', 'frame', 'counter', 'slot')
FONT_NAME = re.compile(r'[a-zA-Z0-9_-]{1,70}\.(?:ttf|otf|woff2?)')
DEATH_IMAGE_STEMS = ('lapida', 'tombstone', 'rip')
WEB = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[2])) / 'web'
BUILTIN_TOMBSTONE = WEB / 'tombstone.svg'


class AssetsMixin:
    runtime: Path
    fonts: Path
    hp_images: Path
    custom_dir: Path

    # --- fonts ---------------------------------------------------------------
    def available_fonts(self) -> list[str]:
        if not self.fonts.is_dir():
            return []
        return sorted(p.name for p in self.fonts.iterdir() if p.is_file() and FONT_NAME.fullmatch(p.name))

    @staticmethod
    def _clean_font(name, data) -> bytes:
        """Validated font bytes (nothing is written)."""
        if not isinstance(name, str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,60}\.(?:ttf|otf|woff2?)', name, re.I):
            raise ValueError('Nombre de fuente inválido')
        if not isinstance(data, str) or len(data) > 4_200_000:
            raise ValueError('Archivo de fuente demasiado grande')
        try:
            raw = base64.b64decode(data, validate=True)
        except (ValueError, base64.binascii.Error) as exc:
            raise ValueError('Fuente Base64 inválida') from exc
        ext = name.rsplit('.', 1)[1].lower()
        if len(raw) > 3_000_000 or not font_is_valid(raw, ext):
            raise ValueError('Fuente inválida; utiliza TTF, OTF, WOFF o WOFF2')
        return raw

    def import_font(self, name, data):
        return self._write_font(name, self._clean_font(name, data))

    def _write_font(self, name, raw):
        self.fonts.mkdir(parents=True, exist_ok=True)
        target = self.fonts / name
        tmp = self.fonts / (name + '.tmp')
        try:
            tmp.write_bytes(raw)
            os.replace(tmp, target)
        finally:
            tmp.unlink(missing_ok=True)
        return self.available_fonts()

    def font_bytes(self, name):
        if name not in self.available_fonts():
            return None
        return (self.fonts / name).read_bytes()

    # --- PNG assets (HP bar fill/frame, counter icon, slot frame) -------------
    def _png_path(self, kind: str) -> Path:
        return self.hp_images / (kind + '.png')

    def _png_bytes(self, kind: str) -> bytes | None:
        try:
            path = self._png_path(kind)
            return path.read_bytes() if path.is_file() else None
        except OSError:
            return None

    def _png_version(self, kind: str) -> str:
        try:
            return str(self._png_path(kind).stat().st_mtime_ns)
        except OSError:
            return '0'

    def hp_image_bytes(self, kind):
        """Solo imágenes conocidas; nunca permite servir rutas suministradas por el cliente."""
        return self._png_bytes(kind) if kind in ('fill', 'frame') else None

    def hp_asset_versions(self):
        return {kind: self._png_version(kind) for kind in ('fill', 'frame')}

    def counter_icon_bytes(self):
        return self._png_bytes('counter')

    def counter_icon_version(self):
        return self._png_version('counter')

    def slot_frame_bytes(self):
        return self._png_bytes('slot')

    def slot_frame_version(self):
        return self._png_version('slot')

    def import_counter_icon(self, data):
        return self._import_png('counter', data)

    def import_hp_image(self, kind, data):
        if kind not in ('fill', 'frame', 'slot'):
            raise ValueError('Tipo de imagen de barra inválido')
        return self._import_png(kind, data)

    def _import_png(self, kind, data):
        """Importa PNG estático, valida dimensiones y elimina metadatos al reescribirlo."""
        return self._write_png(kind, *self._clean_png(kind, data))

    @staticmethod
    def _clean_png(kind, data) -> tuple[bytes, int, int]:
        """(re-encoded PNG, width, height); validates without writing anything."""
        if kind not in PNG_KINDS:
            raise ValueError('Tipo de imagen inválido')
        if not isinstance(data, str) or len(data) > 10_800_000:
            raise ValueError('Imagen demasiado grande (máximo 8 MB)')
        try:
            raw = base64.b64decode(data, validate=True)
            if len(raw) > 8_000_000 or not raw.startswith(b'\x89PNG\r\n\x1a\n'):
                raise ValueError('Se necesita una imagen PNG válida de hasta 8 MB')
            with Image.open(io.BytesIO(raw)) as image:
                w, h = image.size
                if image.format != 'PNG' or getattr(image, 'n_frames', 1) != 1:
                    raise ValueError('Utiliza un PNG estático')
                if not 1 <= w <= 4096 or not 1 <= h <= 1024 or w * h > 4_000_000:
                    raise ValueError('Dimensiones máximas: 4096 × 1024 y 4 megapíxeles')
                output = io.BytesIO()
                image.convert('RGBA').save(output, format='PNG', optimize=True)
                cleaned = output.getvalue()
                if len(cleaned) > 10_000_000:
                    raise ValueError('PNG procesado demasiado grande')
        except (OSError, UnidentifiedImageError, ValueError) as exc:
            raise ValueError('No se pudo importar el PNG: ' + str(exc)) from exc
        return cleaned, w, h

    def _write_png(self, kind, cleaned, w, h):
        self.hp_images.mkdir(parents=True, exist_ok=True)
        tmp = self.hp_images / (kind + '.tmp')
        target = self._png_path(kind)
        try:
            tmp.write_bytes(cleaned)
            os.replace(tmp, target)
        finally:
            tmp.unlink(missing_ok=True)
        return {'kind': kind, 'width': w, 'height': h, 'bytes': len(cleaned)}

    # --- death image (tombstone style) ----------------------------------------
    def _custom_death_file(self) -> Path | None:
        names = [stem + ext for ext in custom_sprites.CUSTOM_EXTENSIONS for stem in DEATH_IMAGE_STEMS]
        dirs = custom_sprites.search_dirs(self.custom_dir, self.selected_sprite_set())
        return custom_sprites.find_file(dirs, names)

    def death_image(self) -> tuple[bytes, str] | None:
        """Own image (lapida.png in the selected set or the root) or the built-in tombstone."""
        found = self._custom_death_file()
        media = custom_sprites.load_media(found) if found is not None else None
        if media is not None:
            return media[0], custom_sprites.MEDIA_TYPES.get(media[1], 'image/png')
        try:
            return BUILTIN_TOMBSTONE.read_bytes(), 'image/svg+xml'
        except OSError:
            return None

    def death_image_version(self) -> str:
        found = self._custom_death_file()
        try:
            return str(found.stat().st_mtime_ns) if found is not None else 'builtin'
        except OSError:
            return 'builtin'

    # --- sprite sets and custom sprites ----------------------------------------
    def selected_sprite_set(self) -> str:
        raise NotImplementedError

    def sprite_sets(self):
        """Subfolders of sprites_personalizados usable as sprite sets."""
        return {'sets': custom_sprites.list_sets(self.custom_dir),
                'selected': self.selected_sprite_set(),
                'path_hint': 'sprites_personalizados'}

    def _decode_upload(self, data):
        if not isinstance(data, str) or len(data) > 10_800_000:
            raise ValueError('Imagen demasiado grande (máximo 8 MB)')
        try:
            raw = base64.b64decode(data, validate=True)
        except (ValueError, base64.binascii.Error) as exc:
            raise ValueError('Imagen Base64 inválida') from exc
        if len(raw) > 8_000_000:
            raise ValueError('Imagen demasiado grande')
        return raw

    def _upload_folder(self, sprite_set, sub=''):
        """Root or a (possibly new) set folder; never outside sprites_personalizados."""
        parts = [self.custom_dir]
        if sprite_set:
            if not custom_sprites.valid_set_name(sprite_set):
                raise ValueError('Nombre de conjunto inválido: letras, números, espacios, - o _ (máx. 40)')
            existing = custom_sprites.list_sets(self.custom_dir)
            real = custom_sprites.canonical_set(self.custom_dir, sprite_set)
            if real is None and len(existing) >= custom_sprites.MAX_SETS:
                raise ValueError('Demasiados conjuntos de sprites')
            parts.append(parts[-1] / (real or sprite_set))
        if sub:
            parts.append(parts[-1] / sub)
        # Every level, including NTFS junctions (is_symlink() misses them).
        for part in parts:
            if part.exists() and (custom_sprites.is_link(part) or not part.is_dir()):
                raise ValueError('La carpeta de destino no es válida')
        return parts[-1]

    def _hint(self, folder):
        """Folder shown to the user, with the real spelling of the set."""
        relative = Path(folder).relative_to(self.custom_dir).as_posix()
        return 'sprites_personalizados' + ('' if relative == '.' else '/' + relative)

    def import_sprite(self, name, data, sprite_set=''):
        """Import a safely named custom image for live OBS replacement.

        Goes to sprites_personalizados or one of its sets (created if needed).
        No arbitrary paths, SVG, compressed archives or unvalidated files.
        Never touches the original ROM, save or memory.
        """
        try:
            stem, suffix = custom_sprites.safe_import_name(name)
        except ValueError:
            raise ValueError('Nombre de sprite inválido. Usa número o especie: 25.png / pikachu.webp') from None
        raw = self._decode_upload(data)
        normalize_custom_sprite(raw, suffix)
        folder = self._upload_folder(sprite_set)
        custom_sprites.write_atomic(folder / (stem + suffix), raw)
        return {'name': stem + suffix, 'bytes': len(raw), 'path_hint': self._hint(folder)}

    def import_item_sprite(self, name, data, sprite_set=''):
        """Custom held-item icon: objetos/234.png, objetos/leftovers.png or objetos/restos.png."""
        try:
            stem, suffix = custom_sprites.safe_import_name(name)
        except ValueError:
            raise ValueError('Nombre de icono inválido. Usa el número o el nombre del objeto: '
                             '234.png, leftovers.png o restos.png') from None
        raw = self._decode_upload(data)
        normalize_custom_sprite(raw, suffix)
        folder = self._upload_folder(sprite_set, custom_sprites.ITEMS_FOLDER)
        target = folder / (stem.lower() + suffix)
        custom_sprites.write_atomic(target, raw)
        return {'name': target.name, 'bytes': len(raw), 'path_hint': self._hint(folder)}
