"""Perfiles de configuración del overlay y exportación/importación de la configuración.

Un perfil es una copia con nombre de los ajustes («Combate», «Exploración»…).
Se guardan en runtime/obs-presets.json, por partida, y una fuente de OBS puede
fijar uno con ?preset=<nombre>.

La exportación es un JSON autocontenido: ajustes, perfiles, PNG importados
(barra, contador, marco por hueco) y fuentes propias. Al importar, todo se
vuelve a validar como si se hubiera subido a mano.
"""
from __future__ import annotations

import base64
import json
import os
import re
import threading
from pathlib import Path
from typing import Any

from .settings import validated_settings

PRESET_NAME = re.compile(r'[A-Za-z0-9 _\-áéíóúüñÁÉÍÓÚÜÑ]{1,40}')
MAX_PRESETS = 30
BUNDLE_FORMAT = 'progressive-tracker-obs'
BUNDLE_SCHEMA = 1
# Base64 bytes of images + fonts in an export; below the 48 MB import limit.
EXPORT_BUDGET = 40_000_000


def valid_preset_name(name: Any) -> str:
    if not isinstance(name, str) or name.strip() != name or not PRESET_NAME.fullmatch(name):
        raise ValueError('Nombre de perfil inválido: de 1 a 40 letras, números, espacios, - o _')
    return name


class PresetStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.lock = threading.Lock()

    def load(self) -> dict[str, dict[str, Any]]:
        """Valid presets only: a damaged entry is skipped, never blocks the app."""
        try:
            raw = json.loads(self.path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return {}
        if not isinstance(raw, dict):
            return {}
        result: dict[str, dict[str, Any]] = {}
        for name, settings in list(raw.items())[:MAX_PRESETS]:
            try:
                result[valid_preset_name(name)] = validated_settings(settings)
            except (ValueError, TypeError):
                continue
        return result

    def _write(self, presets: dict[str, dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix('.tmp')
        try:
            tmp.write_text(json.dumps(presets, indent=2, ensure_ascii=False), encoding='utf-8')
            os.replace(tmp, self.path)
        finally:
            tmp.unlink(missing_ok=True)

    def names(self) -> list[dict[str, str]]:
        return [{'name': name} for name in sorted(self.load(), key=str.casefold)]

    def get(self, name: Any) -> dict[str, Any] | None:
        """Case-insensitive, like save(): renaming «combate» → «Combate» keeps OBS links working."""
        try:
            wanted = valid_preset_name(name).casefold()
        except ValueError:
            return None
        return next((s for n, s in self.load().items() if n.casefold() == wanted), None)

    def save(self, name: Any, settings: dict[str, Any]) -> None:
        name = valid_preset_name(name)
        with self.lock:
            presets = self.load()
            existing = next((n for n in presets if n.casefold() == name.casefold()), None)
            if existing is None and len(presets) >= MAX_PRESETS:
                raise ValueError(f'Máximo {MAX_PRESETS} perfiles de overlay')
            if existing:
                presets.pop(existing)  # same name with different case: rename
            presets[name] = validated_settings(settings)
            self._write(presets)

    def delete(self, name: Any) -> None:
        name = valid_preset_name(name)
        with self.lock:
            presets = self.load()
            existing = next((n for n in presets if n.casefold() == name.casefold()), None)
            if existing is None:
                raise ValueError('Ese perfil no existe')
            del presets[existing]
            self._write(presets)

    def replace_all(self, presets: dict[str, Any]) -> None:
        clean = {}
        for name, settings in list(presets.items())[:MAX_PRESETS]:
            clean[valid_preset_name(name)] = validated_settings(settings)
        with self.lock:
            self._write(clean)


def b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode('ascii')
