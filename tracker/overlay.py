"""Safe OBS browser overlays backed by the already-running localhost tracker.

Read-only public payload contains a death total and six party slots: nickname,
held item name, health, species, live/stale/dead flags and image revisions. No saved Pokémon,
PID, partner data, session token, templates, or credentials are sent to OBS.
"""
from __future__ import annotations

import base64
import copy
import io
import json
import os
import re
import threading
from pathlib import Path
from PIL import Image, UnidentifiedImageError

from .progress import pokemon_key
import hashlib
import hmac
import secrets

from .layout_export import BLANK_PNG, png_to_gif, normalize_custom_sprite
from . import custom_sprites

PALETTE = {
    'high': '#5de09a', 'medium': '#f2c15c', 'low': '#ef5967',
}
DEFAULT = {
    'order': ['sprites', 'names', 'hp'],
    'direction': 'row', 'gap': 16, 'slot_width': 142, 'sprite_size': 94,
    'name_size': 20, 'name_color': '#ffffff', 'name_weight': 700,
    'font': 'Oxanium', 'name_outline': '#151515',
    'hp_height': 17, 'hp_radius': 9, 'hp_background': '#20242f',
    'hp_border': '#ffffff', 'hp_border_width': 1,
    'hp_good': PALETTE['high'], 'hp_mid': PALETTE['medium'],
    'hp_low': PALETTE['low'], 'hp_low_threshold': 25,
    'hp_mid_threshold': 50, 'hp_label': 'fraction',
    'hp_text_color': '#ffffff', 'hp_text_size': 13,
    'hp_style': 'solid', 'hp_reverse': False, 'hp_glow': False,
    'show_empty': False, 'font_file': '',
    'render_scale': 1, 'sprite_scaling': 'pixelated',
    'sprite_shadow': False, 'sprite_padding': 0,
    'hp_animation_ms': 250,
    'hp_custom_fill': False, 'hp_custom_frame': False,
    'counter_mode': 'off', 'counter_total': 10, 'counter_lost': 'gray',
    'counter_in_composition': False, 'counter_custom_icon': False,
    'counter_icon_size': 36,
    'items_in_composition': False, 'item_size': 14, 'item_color': '#f2c15c',
    'item_display': 'name', 'item_icon_size': 32,
    'sprite_set': '',
    'graveyard_max': 12, 'graveyard_columns': 6, 'graveyard_sprite_size': 64,
    'graveyard_order': 'recent', 'graveyard_title': True, 'graveyard_show_name': True,
    'graveyard_show_species': False, 'graveyard_show_level': True, 'graveyard_show_route': True,
}
VALID_FONTS = ('ttf', 'otf', 'woff', 'woff2')
ALLOWED = set(DEFAULT)


def validated_settings(candidate):
    if not isinstance(candidate, dict) or set(candidate) - ALLOWED:
        raise ValueError('Configuración de overlay inválida')
    out = copy.deepcopy(DEFAULT)
    for name, value in candidate.items():
        if name == 'order':
            if not isinstance(value, list) or sorted(value) != ['hp', 'names', 'sprites']:
                raise ValueError('Las tres capas deben aparecer una vez')
        elif name == 'counter_mode':
            if value not in ('off', 'deaths', 'lives'):
                raise ValueError('Modo de contador desconocido')
        elif name == 'sprite_set':
            if not isinstance(value, str) or (value and not custom_sprites.valid_set_name(value)):
                raise ValueError('Conjunto de sprites inválido')
        elif name == 'graveyard_order':
            if value not in ('recent', 'oldest'):
                raise ValueError('Orden del cementerio desconocido')
        elif name == 'item_display':
            if value not in ('name', 'icon', 'both'):
                raise ValueError('Forma de mostrar el objeto desconocida')
        elif name == 'counter_lost':
            if value not in ('hide', 'gray'):
                raise ValueError('Aspecto de vidas perdidas desconocido')
        elif name == 'direction':
            if value not in ('row', 'column', 'grid'):
                raise ValueError('Dirección desconocida')
        elif name == 'hp_label':
            if value not in ('fraction', 'percent', 'both', 'none'):
                raise ValueError('Etiqueta de vida incorrecta')
        elif name == 'hp_style':
            if value not in ('solid', 'gradient', 'striped'):
                raise ValueError('Estilo de barra incorrecto')
        elif name == 'sprite_scaling':
            if value not in ('pixelated','smooth'):
                raise ValueError('Interpolación de sprites desconocida')
        elif name in ('hp_glow', 'hp_reverse', 'show_empty', 'hp_custom_fill', 'hp_custom_frame', 'sprite_shadow',
                      'counter_in_composition', 'counter_custom_icon', 'items_in_composition',
                      'graveyard_title', 'graveyard_show_name', 'graveyard_show_species',
                      'graveyard_show_level', 'graveyard_show_route'):
            if type(value) is not bool:
                raise ValueError('Opción incorrecta: ' + name)
        elif name == 'font':
            if value not in ('Oxanium', 'Arial', 'Segoe UI', 'Verdana', 'Georgia', 'monospace'):
                raise ValueError('Familia tipográfica incorrecta')
        elif name == 'font_file':
            if not isinstance(value, str) or (value and not re.fullmatch(r'[a-zA-Z0-9_-]{1,70}\.(?:ttf|otf|woff2?)', value)):
                raise ValueError('Fuente personalizada inválida')
        elif name.endswith('color') or name in ('name_outline', 'hp_background', 'hp_border', 'hp_good', 'hp_mid', 'hp_low'):
            if not isinstance(value, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', value):
                raise ValueError('Color HEX inválido: ' + name)
        else:
            ranges = {
                'gap': (0, 120), 'slot_width': (60, 480), 'sprite_size': (24, 360),
                'name_size': (9, 80), 'name_weight': (400, 900),
                'hp_height': (3, 100), 'hp_radius': (0, 50),
                'hp_border_width': (0, 8), 'hp_low_threshold': (1, 49),
                'hp_mid_threshold': (50, 95), 'hp_text_size': (8, 48),
                'render_scale': (1, 4), 'sprite_padding': (0, 64),
                'hp_animation_ms': (0, 1500),
                'counter_total': (1, 100), 'counter_icon_size': (12, 256),
                'item_size': (8, 60), 'item_icon_size': (12, 128),
                'graveyard_max': (1, 60), 'graveyard_columns': (1, 12), 'graveyard_sprite_size': (24, 256),
            }
            if type(value) is not int or not ranges[name][0] <= value <= ranges[name][1]:
                raise ValueError('Valor fuera de rango: ' + name)
        out[name] = value
    if out['hp_low_threshold'] >= out['hp_mid_threshold']:
        raise ValueError('El umbral rojo debe ser menor que el amarillo')
    return out


def font_is_valid(raw, ext):
    if ext == 'ttf':
        return raw[:4] in (b'\x00\x01\x00\x00', b'true')
    if ext == 'otf':
        return raw.startswith(b'OTTO')
    if ext == 'woff':
        return raw.startswith(b'wOFF')
    return ext == 'woff2' and raw.startswith(b'wOF2')


class OverlayManager:
    def __init__(self, service, runtime, layout, custom_dir=None):
        self.service = service
        self.runtime = Path(runtime)
        self.layout = Path(layout)
        self.path = self.runtime / 'obs-overlay.json'
        self.fonts = self.runtime / 'obs-fonts'
        self.hp_images = self.runtime / 'obs-hp-images'
        self.custom_dir = Path(custom_dir) if custom_dir is not None else self.layout.parent/'sprites_personalizados'
        self.lock = threading.RLock()
        # Public graveyard ids are an HMAC with a per-process secret: stable
        # while the app runs, but the encryption constant cannot be recovered.
        self._rev_key = secrets.token_bytes(16)
        self.settings = copy.deepcopy(DEFAULT)
        if self.path.is_file():
            try:
                self.settings = validated_settings(json.loads(self.path.read_text(encoding='utf-8')))
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                # Corrupted custom settings must not block Pokémon Tracker.
                self.settings = copy.deepcopy(DEFAULT)

    def get_settings(self):
        with self.lock:
            return copy.deepcopy(self.settings)

    def set_settings(self, data):
        clean = validated_settings(data)
        if clean['font_file'] and clean['font_file'] not in self.available_fonts():
            raise ValueError('Debes cargar primero esa fuente')
        if clean['sprite_set']:
            real = custom_sprites.canonical_set(self.custom_dir, clean['sprite_set'])
            if real is None:
                raise ValueError('Ese conjunto de sprites no existe en sprites_personalizados')
            clean['sprite_set'] = real  # the folder's real spelling
        self.runtime.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix('.tmp')
        with self.lock:
            try:
                tmp.write_text(json.dumps(clean, indent=2, ensure_ascii=False), encoding='utf-8')
                os.replace(tmp, self.path)
                self.settings = clean
            finally:
                tmp.unlink(missing_ok=True)
        return self.get_settings()

    def available_fonts(self):
        if not self.fonts.is_dir():
            return []
        return sorted(p.name for p in self.fonts.iterdir()
                      if p.is_file() and re.fullmatch(r'[a-zA-Z0-9_-]{1,70}\.(?:ttf|otf|woff2?)', p.name))

    def sprite_sets(self):
        """Subfolders of sprites_personalizados usable as sprite sets."""
        return {'sets': custom_sprites.list_sets(self.custom_dir),
                'selected': self.get_settings().get('sprite_set', ''),
                'path_hint': 'sprites_personalizados'}

    def selected_sprite_set(self):
        return self.get_settings().get('sprite_set', '')

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

    def _hint(self, folder):
        """Folder shown to the user, with the real spelling of the set."""
        relative = Path(folder).relative_to(self.custom_dir).as_posix()
        return 'sprites_personalizados' + ('' if relative == '.' else '/' + relative)

    @staticmethod
    def _graveyard_records(progress, order='recent', limit=60):
        """Deaths in display order (max `limit`), with the original record for sprites."""
        deaths = (progress or {}).get('deaths') or {}
        records = []
        for key, entry in deaths.items():
            if not isinstance(entry, dict) or not isinstance(entry.get('pokemon'), dict):
                continue
            mon = entry['pokemon']
            if type(mon.get('species_id')) is not int:
                continue
            records.append((str(entry.get('recorded_at') or ''), str(key), mon))
        records.sort(key=lambda r: (r[0], r[1]), reverse=order != 'oldest')
        return records[:limit] if limit else records

    def graveyard_entry(self, index):
        """Pokémon record shown at position `index` of the public graveyard."""
        if type(index) is not int or not 0 <= index < 60:
            return None
        if hasattr(self.service, 'condition') and hasattr(self.service, 'state'):
            with self.service.condition:
                records = self._graveyard_records(self.service.state.get('progress'))
                record = records[index] if index < len(records) else None
                return copy.deepcopy(record[2]) if record else None
        records = self._graveyard_records(self.service.snapshot().get('progress'))
        return copy.deepcopy(records[index][2]) if index < len(records) else None

    def graveyard_entry_for(self, rev):
        """Record whose public image_rev matches; stable while new deaths shift positions."""
        if not isinstance(rev, str) or not re.fullmatch(r'[0-9a-f]{12}', rev):
            return None
        if hasattr(self.service, 'condition') and hasattr(self.service, 'state'):
            with self.service.condition:
                records = self._graveyard_records(self.service.state.get('progress'), limit=0)
        else:
            records = self._graveyard_records(self.service.snapshot().get('progress'), limit=0)
        for _, key, mon in records:
            if self._grave_rev(key) == rev:
                return copy.deepcopy(mon)
        return None

    def _grave_rev(self, key):
        return hmac.new(self._rev_key, key.encode('utf-8'), hashlib.sha256).hexdigest()[:12]

    def _graveyard_public(self, records):
        result = []
        for index, (recorded, key, mon) in enumerate(records):
            level = mon.get('level')
            result.append({
                'n': index,
                'species_id': mon['species_id'],
                'nickname': str(mon.get('nickname') or mon.get('species') or '')[:40],
                'species': str(mon.get('species') or '')[:40],
                'level': level if type(level) is int and 1 <= level <= 100 else None,
                'route': str(mon.get('met_location') or '')[:60],
                # Stable per death without exposing the encryption constant.
                'image_rev': self._grave_rev(key),
            })
        return result

    def import_font(self, name, data):
        if not isinstance(name, str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,60}\.(?:ttf|otf|woff2?)', name, re.I):
            raise ValueError('Nombre de fuente inválido')
        if not isinstance(data, str) or len(data) > 4_200_000:
            raise ValueError('Archivo de fuente demasiado grande')
        try:
            raw = base64.b64decode(data, validate=True)
        except (ValueError, base64.binascii.Error) as exc:
            raise ValueError('Fuente Base64 inválida') from exc
        ext = name.rsplit('.',1)[1].lower()
        if len(raw) > 3_000_000 or not font_is_valid(raw, ext):
            raise ValueError('Fuente inválida; utiliza TTF, OTF, WOFF o WOFF2')
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

    def hp_image_bytes(self, kind):
        """Solo imágenes conocidas; nunca permite servir rutas suministradas por el cliente."""
        if kind not in ('fill', 'frame'):
            return None
        path = self.hp_images / (kind + '.png')
        try:
            return path.read_bytes() if path.is_file() else None
        except OSError:
            return None

    def hp_asset_versions(self):
        versions = {}
        for kind in ('fill', 'frame'):
            try:
                versions[kind] = str((self.hp_images / (kind + '.png')).stat().st_mtime_ns)
            except OSError:
                versions[kind] = '0'
        return versions

    def counter_icon_bytes(self):
        try:
            return (self.hp_images / 'counter.png').read_bytes()
        except OSError:
            return None

    def counter_icon_version(self):
        try:
            return str((self.hp_images / 'counter.png').stat().st_mtime_ns)
        except OSError:
            return '0'

    def import_counter_icon(self, data):
        return self._import_png('counter', data)

    def import_hp_image(self, kind, data):
        if kind not in ('fill', 'frame'):
            raise ValueError('Tipo de imagen de barra inválido')
        return self._import_png(kind, data)

    def _import_png(self, kind, data):
        """Importa PNG estático, valida dimensiones y elimina metadatos al reescribirlo."""
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
                normalized = image.convert('RGBA')
                output = io.BytesIO()
                normalized.save(output, format='PNG', optimize=True)
                cleaned = output.getvalue()
                if len(cleaned) > 10_000_000:
                    raise ValueError('PNG procesado demasiado grande')
        except (OSError, UnidentifiedImageError, ValueError) as exc:
            raise ValueError('No se pudo importar el PNG: ' + str(exc)) from exc
        self.hp_images.mkdir(parents=True, exist_ok=True)
        tmp = self.hp_images / (kind + '.tmp')
        target = self.hp_images / (kind + '.png')
        try:
            tmp.write_bytes(cleaned)
            os.replace(tmp, target)
        finally:
            tmp.unlink(missing_ok=True)
        return {'kind': kind, 'width': w, 'height': h, 'bytes': len(cleaned)}

    def image_bytes(self, slot, suffix):
        if type(slot) is not int or slot not in range(1,7) or suffix not in ('png','gif','webp'):
            return None
        target = self.layout / f'pokemon_{slot}.{suffix}'
        try:
            if target.is_file():
                return target.read_bytes()
        except OSError:
            pass
        if suffix in ('png','webp'):
            return BLANK_PNG if suffix=='png' else None
        # Valid single-frame transparent GIF before the sprite exporter starts.
        return png_to_gif(BLANK_PNG)

    def public_state(self):
        # OBS may poll from several sources twice per second. Copy only the six
        # party slots, never the entire 32-box cache (~960 Pokémon).
        if hasattr(self.service, 'condition') and hasattr(self.service, 'state'):
            with self.service.condition:
                original = self.service.state
                graveyard = self._graveyard_public(self._graveyard_records(
                    original.get('progress'), self.settings.get('graveyard_order', 'recent')))
                state = {
                    'party': copy.deepcopy(original.get('party') or []),
                    'progress': {
                        'deaths': list(((original.get('progress') or {}).get('deaths') or {})),
                        'death_count': (original.get('progress') or {}).get('death_count'),
                    },
                    'stale': original.get('stale', True),
                    'game': original.get('game'),
                    'revision': original.get('revision', 0),
                }
        else:
            state = self.service.snapshot()
            graveyard = self._graveyard_public(self._graveyard_records(
                state.get('progress'), self.settings.get('graveyard_order', 'recent')))
        deaths = (state.get('progress') or {}).get('deaths') or {}
        count = (state.get('progress') or {}).get('death_count')
        count = count if type(count) is int and count >= 0 else len(deaths)
        result = []
        party = state.get('party') or []
        for i in range(6):
            mon = party[i] if i < len(party) else None
            if not isinstance(mon, dict) or not isinstance(mon.get('species_id'), int):
                result.append({'slot': i + 1, 'present': False})
                continue
            hp = mon.get('hp')
            maximum = mon.get('max_hp')
            valid = type(hp) is int and type(maximum) is int and maximum > 0
            hp = max(0, min(hp, maximum)) if valid else None
            media=self.layout/f'pokemon_{i+1}.media'
            try:
                image_format=media.read_text(encoding='ascii').strip()
            except (OSError,ValueError,UnicodeError):
                image_format='png'
            if image_format not in ('png','gif','webp'):
                image_format='png'
            sprite=self.layout/f'pokemon_{i+1}.{image_format}'
            try:
                image_rev=str(sprite.stat().st_mtime_ns)
            except OSError:
                image_rev='0'
            item = mon.get('item') if type(mon.get('item_id')) is int and mon['item_id'] > 0 else ''
            result.append({
                'slot':i+1, 'present': True, 'species_id': mon['species_id'],
                'item': str(item or '')[:40],
                'item_id': mon['item_id'] if item else 0,
                'image_rev': image_rev, 'image_format':image_format,
                'nickname': str(mon.get('nickname') or mon.get('species') or '')[:40],
                'hp': hp, 'max_hp': maximum if valid else None,
                'percent': round(100*hp/maximum, 2) if valid else None,
                'dead': pokemon_key(mon) in deaths, 'stale': bool(state.get('stale', True)),
            })
        return {'revision':state.get('revision',0), 'game':state.get('game'),
                'stale':bool(state.get('stale', True)), 'party':result,
                'death_count': count, 'graveyard': graveyard,
                # Fallen right now (revived ones excluded), unlike the cumulative counter.
                'graveyard_total': len(deaths)}
