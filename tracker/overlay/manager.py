"""OverlayManager: ajustes, perfiles, recursos y estado público del overlay de OBS.

El estado público contiene un total de muertes, seis huecos del equipo (mote,
objeto, nivel, tipos, shiny, género, PS, revisiones de imagen y banderas de
vivo/muerto/desactualizado), el cementerio y unas estadísticas de la partida.
Nunca incluye PID, constantes de cifrado, cajas, datos del compañero, tokens
ni plantillas.
"""
from __future__ import annotations

import copy
import json
import os
import secrets
import threading
from pathlib import Path
from typing import Any

from .. import custom_sprites
from ..layout_export import BLANK_PNG, png_to_gif
from ..progress import pokemon_key
from .assets import AssetsMixin
from .graveyard import GraveyardMixin, graveyard_records, run_stats
from .presets import (BUNDLE_FORMAT, BUNDLE_SCHEMA, EXPORT_BUDGET, MAX_PRESETS, PresetStore, b64,
                      valid_preset_name)
from .settings import DEFAULT, validated_settings


class OverlayManager(AssetsMixin, GraveyardMixin):
    def __init__(self, service, runtime, layout, custom_dir=None):
        self.service = service
        self.runtime = Path(runtime)
        self.layout = Path(layout)
        self.path = self.runtime / 'obs-overlay.json'
        self.fonts = self.runtime / 'obs-fonts'
        self.hp_images = self.runtime / 'obs-hp-images'
        self.custom_dir = Path(custom_dir) if custom_dir is not None else self.layout.parent / 'sprites_personalizados'
        self.presets = PresetStore(self.runtime / 'obs-presets.json')
        self.lock = threading.RLock()
        # Public graveyard ids are an HMAC with a per-process secret.
        self._rev_key = secrets.token_bytes(16)
        self.settings = copy.deepcopy(DEFAULT)
        if self.path.is_file():
            try:
                self.settings = validated_settings(json.loads(self.path.read_text(encoding='utf-8')))
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                # Corrupted custom settings must not block Pokémon Tracker.
                self.settings = copy.deepcopy(DEFAULT)

    # --- settings ---------------------------------------------------------------
    def get_settings(self):
        with self.lock:
            return copy.deepcopy(self.settings)

    def selected_sprite_set(self) -> str:
        return self.get_settings().get('sprite_set', '')

    def _checked(self, data):
        """Validated settings whose referenced font and sprite set exist on disk."""
        clean = validated_settings(data)
        if clean['font_file'] and clean['font_file'] not in self.available_fonts():
            raise ValueError('Debes cargar primero esa fuente')
        if clean['sprite_set']:
            real = custom_sprites.canonical_set(self.custom_dir, clean['sprite_set'])
            if real is None:
                raise ValueError('Ese conjunto de sprites no existe en sprites_personalizados')
            clean['sprite_set'] = real  # the folder's real spelling
        return clean

    def set_settings(self, data):
        clean = self._checked(data)
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

    def public_settings(self, preset=None):
        """Settings plus asset versions, as the overlay reads them (None: unknown preset)."""
        config = self.get_settings() if preset is None else self.presets.get(preset)
        if config is None:
            return None
        config = copy.deepcopy(config)
        config['hp_asset_versions'] = self.hp_asset_versions()
        config['counter_icon_version'] = self.counter_icon_version()
        config['death_image_version'] = self.death_image_version()
        config['slot_frame_version'] = self.slot_frame_version()
        return config

    # --- presets ------------------------------------------------------------------
    def presets_status(self):
        return {'presets': self.presets.names()}

    def preset_action(self, action, name):
        if action == 'save':
            self.presets.save(name, self.get_settings())
        elif action == 'apply':
            preset = self.presets.get(name)
            if preset is None:
                raise ValueError('Ese perfil no existe')
            self.set_settings(preset)
        elif action == 'delete':
            self.presets.delete(name)
        else:
            raise ValueError('Acción de perfil desconocida')
        return {'presets': self.presets.names(), 'settings': self.get_settings()}

    # --- export / import ------------------------------------------------------------
    def export_bundle(self):
        """Self-contained JSON that always fits the import limit (EXPORT_BUDGET).

        The font in use is included first; anything that does not fit is
        listed in 'omitted' so the editor can tell the user.
        """
        images, fonts, omitted, used = {}, {}, [], 0
        in_use = self.get_settings().get('font_file')
        candidates = [('image', kind, self._png_bytes(kind)) for kind in ('fill', 'frame', 'counter', 'slot')]
        names = sorted(self.available_fonts(), key=lambda n: n != in_use)
        candidates += [('font', name, self.font_bytes(name)) for name in names]
        for group, name, raw in candidates:
            if raw is None:
                continue
            encoded = b64(raw)
            if used + len(encoded) > EXPORT_BUDGET:
                omitted.append(name)
                continue
            used += len(encoded)
            (images if group == 'image' else fonts)[name] = encoded
        return {'format': BUNDLE_FORMAT, 'schema': BUNDLE_SCHEMA, 'settings': self.get_settings(),
                'presets': self.presets.load(), 'images': images, 'fonts': fonts, 'omitted': omitted}

    def import_bundle(self, bundle):
        """Validate everything first, then write: a bad bundle changes nothing."""
        if not isinstance(bundle, dict) or bundle.get('format') != BUNDLE_FORMAT or bundle.get('schema') != BUNDLE_SCHEMA:
            raise ValueError('El archivo no es una configuración de OBS de Progressive Tracker')
        settings = validated_settings(bundle.get('settings'))
        presets = bundle.get('presets') or {}
        images = bundle.get('images') or {}
        fonts = bundle.get('fonts') or {}
        if not all(isinstance(x, dict) for x in (presets, images, fonts)):
            raise ValueError('Configuración de OBS dañada')
        if len(presets) > MAX_PRESETS:
            raise ValueError(f'La configuración trae más de {MAX_PRESETS} perfiles')
        clean_presets = {valid_preset_name(n): validated_settings(s) for n, s in presets.items()}
        if len({n.casefold() for n in clean_presets}) != len(clean_presets):
            raise ValueError('La configuración trae perfiles repetidos')
        if set(images) - {'fill', 'frame', 'counter', 'slot'}:
            raise ValueError('Imagen desconocida en la configuración')
        # Phase 1: decode and validate EVERYTHING in memory.
        clean_fonts = {name: self._clean_font(name, data) for name, data in fonts.items()}
        clean_images = {kind: self._clean_png(kind, data) for kind, data in images.items()}
        # Phase 2: only now touch the disk.
        for name, raw in clean_fonts.items():
            self._write_font(name, raw)
        for kind, cleaned in clean_images.items():
            self._write_png(kind, *cleaned)
        # A sprite set that does not exist on this computer falls back to the root.
        if settings['sprite_set'] and custom_sprites.canonical_set(self.custom_dir, settings['sprite_set']) is None:
            settings['sprite_set'] = ''
        if settings['font_file'] and settings['font_file'] not in self.available_fonts():
            settings['font_file'] = ''
        self.presets.replace_all(clean_presets)
        return {'settings': self.set_settings(settings), 'presets': self.presets.names()}

    # --- party media and public state --------------------------------------------------
    def image_bytes(self, slot, suffix):
        if type(slot) is not int or slot not in range(1, 7) or suffix not in ('png', 'gif', 'webp'):
            return None
        target = self.layout / f'pokemon_{slot}.{suffix}'
        try:
            if target.is_file():
                return target.read_bytes()
        except OSError:
            pass
        if suffix in ('png', 'webp'):
            return BLANK_PNG if suffix == 'png' else None
        # Valid single-frame transparent GIF before the sprite exporter starts.
        return png_to_gif(BLANK_PNG)

    def _media_format(self, slot: int) -> tuple[str, str]:
        try:
            image_format = (self.layout / f'pokemon_{slot}.media').read_text(encoding='ascii').strip()
        except (OSError, ValueError, UnicodeError):
            image_format = 'png'
        if image_format not in ('png', 'gif', 'webp'):
            image_format = 'png'
        try:
            image_rev = str((self.layout / f'pokemon_{slot}.{image_format}').stat().st_mtime_ns)
        except OSError:
            image_rev = '0'
        return image_format, image_rev

    @staticmethod
    def _slot_extras(mon: dict[str, Any]) -> dict[str, Any]:
        """Optional per-Pokémon data for the OBS info layer."""
        level = mon.get('level')
        types = mon.get('types')
        gender = mon.get('gender')
        return {
            'level': level if type(level) is int and 1 <= level <= 100 else None,
            'types': [str(t)[:12] for t in types[:2] if isinstance(t, str)] if isinstance(types, list) else [],
            'shiny': mon.get('shiny') is True,
            'gender': gender if type(gender) is int and gender in (0, 1, 2) else None,
        }

    def public_state(self, preset=None):
        # OBS may poll from several sources twice per second. Copy only the six
        # party slots and the progress summary, never the 32-box cache.
        pinned = self.presets.get(preset) if preset else None
        order = (pinned or self.settings).get('graveyard_order', 'recent')
        if hasattr(self.service, 'condition') and hasattr(self.service, 'state'):
            with self.service.condition:
                original = self.service.state
                progress = original.get('progress') or {}
                graveyard = self._graveyard_public(graveyard_records(progress, order))
                state = {
                    'party': copy.deepcopy(original.get('party') or []),
                    'deaths': list(progress.get('deaths') or {}),
                    'death_count': progress.get('death_count'),
                    'progress_summary': {'deaths': dict.fromkeys(progress.get('deaths') or {}),
                                         'encounters': dict.fromkeys(progress.get('encounters') or {}),
                                         'missed_routes': list(progress.get('missed_routes') or [])},
                    'stale': original.get('stale', True),
                    'game': original.get('game'),
                    'revision': original.get('revision', 0),
                }
        else:
            snap = self.service.snapshot()
            progress = snap.get('progress') or {}
            graveyard = self._graveyard_public(graveyard_records(progress, order))
            state = {'party': snap.get('party') or [], 'deaths': list(progress.get('deaths') or {}),
                     'death_count': progress.get('death_count'), 'progress_summary': progress,
                     'stale': snap.get('stale', True), 'game': snap.get('game'),
                     'revision': snap.get('revision', 0)}
        deaths = set(state['deaths'])
        count = state['death_count']
        count = count if type(count) is int and count >= 0 else len(deaths)
        result = []
        party = state['party']
        for i in range(6):
            mon = party[i] if i < len(party) else None
            if not isinstance(mon, dict) or not isinstance(mon.get('species_id'), int):
                result.append({'slot': i + 1, 'present': False})
                continue
            hp = mon.get('hp')
            maximum = mon.get('max_hp')
            valid = type(hp) is int and type(maximum) is int and maximum > 0
            hp = max(0, min(hp, maximum)) if valid else None
            image_format, image_rev = self._media_format(i + 1)
            item = mon.get('item') if type(mon.get('item_id')) is int and mon['item_id'] > 0 else ''
            result.append({
                'slot': i + 1, 'present': True, 'species_id': mon['species_id'],
                'item': str(item or '')[:40],
                'item_id': mon['item_id'] if item else 0,
                'image_rev': image_rev, 'image_format': image_format,
                'nickname': str(mon.get('nickname') or mon.get('species') or '')[:40],
                'hp': hp, 'max_hp': maximum if valid else None,
                'percent': round(100 * hp / maximum, 2) if valid else None,
                'dead': pokemon_key(mon) in deaths, 'stale': bool(state['stale']),
                **self._slot_extras(mon),
            })
        return {'revision': state['revision'], 'game': state['game'],
                'stale': bool(state['stale']), 'party': result,
                'death_count': count, 'graveyard': graveyard,
                # Fallen right now (revived ones excluded), unlike the cumulative counter.
                'graveyard_total': len(deaths),
                'stats': run_stats(state['progress_summary'], result)}
