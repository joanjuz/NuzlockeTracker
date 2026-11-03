"""Ajustes del overlay de OBS: valores por defecto y validación estricta.

Cada clave tiene una sola regla (opción cerrada, booleano, rango, color o
texto validado). Una configuración con claves desconocidas se rechaza entera;
las claves que falten toman el valor por defecto, así que las configuraciones
guardadas por versiones anteriores siguen cargando.
"""
from __future__ import annotations

import copy
import re
from typing import Any

from .. import custom_sprites

PALETTE = {'high': '#5de09a', 'medium': '#f2c15c', 'low': '#ef5967'}

DEFAULT: dict[str, Any] = {
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
    # 1.2: estilo de muerte, datos por Pokémon, marco por hueco y estadísticas.
    'death_style': 'gray', 'death_animation': 'none',
    'info_in_composition': False, 'info_size': 14, 'info_show_level': True,
    'info_show_types': True, 'info_show_shiny': True, 'info_show_gender': True,
    'slot_frame': False,
    'stats_show_captures': True, 'stats_show_deaths': True, 'stats_show_alive': True,
    'stats_show_missed': True, 'stats_direction': 'row', 'stats_size': 20,
}
ALLOWED = set(DEFAULT)
VALID_FONTS = ('ttf', 'otf', 'woff', 'woff2')

# Closed choices: key -> (allowed values, error message).
CHOICES: dict[str, tuple[tuple[Any, ...], str]] = {
    'counter_mode': (('off', 'deaths', 'lives'), 'Modo de contador desconocido'),
    'graveyard_order': (('recent', 'oldest'), 'Orden del cementerio desconocido'),
    'item_display': (('name', 'icon', 'both'), 'Forma de mostrar el objeto desconocida'),
    'counter_lost': (('hide', 'gray'), 'Aspecto de vidas perdidas desconocido'),
    'direction': (('row', 'column', 'grid'), 'Dirección desconocida'),
    'hp_label': (('fraction', 'percent', 'both', 'none'), 'Etiqueta de vida incorrecta'),
    'hp_style': (('solid', 'gradient', 'striped'), 'Estilo de barra incorrecto'),
    'sprite_scaling': (('pixelated', 'smooth'), 'Interpolación de sprites desconocida'),
    'font': (('Oxanium', 'Arial', 'Segoe UI', 'Verdana', 'Georgia', 'monospace'), 'Familia tipográfica incorrecta'),
    'death_style': (('gray', 'tombstone', 'hide'), 'Estilo de muerte desconocido'),
    'death_animation': (('none', 'fade', 'shake'), 'Animación de muerte desconocida'),
    'stats_direction': (('row', 'column'), 'Dirección de estadísticas desconocida'),
}
BOOLEANS = frozenset(name for name, value in DEFAULT.items() if type(value) is bool)
RANGES: dict[str, tuple[int, int]] = {
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
    'info_size': (8, 60), 'stats_size': (10, 80),
}
COLORS = frozenset({'name_color', 'name_outline', 'hp_background', 'hp_border', 'hp_good', 'hp_mid',
                    'hp_low', 'hp_text_color', 'item_color'})
HEX = re.compile(r'#[0-9a-fA-F]{6}')
FONT_FILE = re.compile(r'[a-zA-Z0-9_-]{1,70}\.(?:ttf|otf|woff2?)')


def _check(name: str, value: Any) -> None:
    if name == 'order':
        if not isinstance(value, list) or sorted(value) != ['hp', 'names', 'sprites']:
            raise ValueError('Las tres capas deben aparecer una vez')
    elif name in CHOICES:
        allowed, message = CHOICES[name]
        if value not in allowed:
            raise ValueError(message)
    elif name in BOOLEANS:
        if type(value) is not bool:
            raise ValueError('Opción incorrecta: ' + name)
    elif name in COLORS:
        if not isinstance(value, str) or not HEX.fullmatch(value):
            raise ValueError('Color HEX inválido: ' + name)
    elif name == 'sprite_set':
        if not isinstance(value, str) or (value and not custom_sprites.valid_set_name(value)):
            raise ValueError('Conjunto de sprites inválido')
    elif name == 'font_file':
        if not isinstance(value, str) or (value and not FONT_FILE.fullmatch(value)):
            raise ValueError('Fuente personalizada inválida')
    else:
        low, high = RANGES[name]
        if type(value) is not int or not low <= value <= high:
            raise ValueError('Valor fuera de rango: ' + name)


# Every key must have exactly one rule (checked by tests/test_overlay_presets.py).
RULED = {'order', 'sprite_set', 'font_file'} | set(CHOICES) | BOOLEANS | set(RANGES) | COLORS


def validated_settings(candidate: Any) -> dict[str, Any]:
    if not isinstance(candidate, dict) or set(candidate) - ALLOWED:
        raise ValueError('Configuración de overlay inválida')
    out = copy.deepcopy(DEFAULT)
    for name, value in candidate.items():
        _check(name, value)
        out[name] = value
    if out['hp_low_threshold'] >= out['hp_mid_threshold']:
        raise ValueError('El umbral rojo debe ser menor que el amarillo')
    return out


def font_is_valid(raw: bytes, ext: str) -> bool:
    if ext == 'ttf':
        return raw[:4] in (b'\x00\x01\x00\x00', b'true')
    if ext == 'otf':
        return raw.startswith(b'OTTO')
    if ext == 'woff':
        return raw.startswith(b'wOFF')
    return ext == 'woff2' and raw.startswith(b'wOF2')
