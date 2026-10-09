"""Safe OBS browser overlays backed by the already-running localhost tracker.

Read-only public payload contains only six party slots: nickname, health,
species, live/stale/dead flags and image revisions. No saved Pokémon,
PID, partner data, session token, templates, or credentials are sent to OBS.
"""
from __future__ import annotations

import base64
import copy
import io
import json
import os
import re
import tempfile
import threading
from pathlib import Path
from PIL import Image, UnidentifiedImageError

from .progress import pokemon_key
from .layout_export import BLANK_PNG, png_to_gif

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
    'hp_custom_fill': False, 'hp_custom_frame': False,
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
        elif name == 'direction':
            if value not in ('row', 'column', 'grid'):
                raise ValueError('Dirección desconocida')
        elif name == 'hp_label':
            if value not in ('fraction', 'percent', 'both', 'none'):
                raise ValueError('Etiqueta de vida incorrecta')
        elif name == 'hp_style':
            if value not in ('solid', 'gradient', 'striped'):
                raise ValueError('Estilo de barra incorrecto')
        elif name in ('hp_glow', 'hp_reverse', 'show_empty', 'hp_custom_fill', 'hp_custom_frame'):
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
    def __init__(self, service, runtime, layout):
        self.service = service
        self.runtime = Path(runtime)
        self.layout = Path(layout)
        self.path = self.runtime / 'obs-overlay.json'
        self.fonts = self.runtime / 'obs-fonts'
        self.hp_images = self.runtime / 'obs-hp-images'
        self.lock = threading.RLock()
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

    def import_hp_image(self, kind, data):
        """Importa PNG estático, valida dimensiones y elimina metadatos al reescribirlo."""
        if kind not in ('fill', 'frame'):
            raise ValueError('Tipo de imagen de barra inválido')
        if not isinstance(data, str) or len(data) > 3_000_000:
            raise ValueError('Imagen demasiado grande (máximo 2 MB)')
        try:
            raw = base64.b64decode(data, validate=True)
            if len(raw) > 2_000_000 or not raw.startswith(b'\\x89PNG\\r\\n\\x1a\\n'):
                raise ValueError('Se necesita una imagen PNG válida de hasta 2 MB')
            with Image.open(io.BytesIO(raw)) as image:
                w, h = image.size
                if image.format != 'PNG' or getattr(image, 'n_frames', 1) != 1:
                    raise ValueError('Utiliza un PNG estático')
                if not 1 <= w <= 2048 or not 1 <= h <= 512 or w * h > 1_000_000:
                    raise ValueError('Dimensiones máximas: 2048 × 512 y 1 megapíxel')
                normalized = image.convert('RGBA')
                output = io.BytesIO()
                normalized.save(output, format='PNG', optimize=True)
                cleaned = output.getvalue()
                if len(cleaned) > 3_000_000:
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
        if type(slot) is not int or slot not in range(1,7) or suffix not in ('png','gif'):
            return None
        target = self.layout / f'pokemon_{slot}.{suffix}'
        try:
            if target.is_file():
                return target.read_bytes()
        except OSError:
            pass
        if suffix == 'png':
            return BLANK_PNG
        # Valid single-frame transparent GIF before the sprite exporter starts.
        return png_to_gif(BLANK_PNG)

    def public_state(self):
        # OBS may poll from several sources twice per second. Copy only the six
        # party slots, never the entire 32-box cache (~960 Pokémon).
        if hasattr(self.service, 'condition') and hasattr(self.service, 'state'):
            with self.service.condition:
                original = self.service.state
                state = {
                    'party': copy.deepcopy(original.get('party') or []),
                    'progress': {'deaths': list(((original.get('progress') or {}).get('deaths') or {}))},
                    'stale': original.get('stale', True),
                    'game': original.get('game'),
                    'revision': original.get('revision', 0),
                }
        else:
            state = self.service.snapshot()
        deaths = (state.get('progress') or {}).get('deaths') or {}
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
            sprite = self.layout / f'pokemon_{i+1}.gif'
            try:
                image_rev = str(sprite.stat().st_mtime_ns)
            except OSError:
                image_rev = '0'
            result.append({
                'slot':i+1, 'present': True, 'species_id': mon['species_id'],
                'image_rev': image_rev,
                'nickname': str(mon.get('nickname') or mon.get('species') or '')[:40],
                'hp': hp, 'max_hp': maximum if valid else None,
                'percent': round(100*hp/maximum, 2) if valid else None,
                'dead': pokemon_key(mon) in deaths, 'stale': bool(state.get('stale', True)),
            })
        return {'revision':state.get('revision',0), 'game':state.get('game'),
                'stale':bool(state.get('stale', True)), 'party':result}
