"""Cementerio y estadísticas públicas de la partida para OBS.

Los ids públicos de cada muerte son un HMAC con una clave aleatoria por
proceso: estables mientras la app está abierta, pero no permiten recuperar la
constante de cifrado (EC) que forma la clave interna de la muerte.
"""
from __future__ import annotations

import copy
import hashlib
import hmac
import re
from typing import Any

GRAVE_REV = re.compile(r'[0-9a-f]{12}')
Record = tuple[str, str, dict[str, Any]]


def graveyard_records(progress: Any, order: str = 'recent', limit: int = 60) -> list[Record]:
    """Deaths in display order (max `limit`; 0 = all), with the original record for sprites."""
    deaths = (progress or {}).get('deaths') or {}
    records: list[Record] = []
    for key, entry in deaths.items():
        if not isinstance(entry, dict) or not isinstance(entry.get('pokemon'), dict):
            continue
        mon = entry['pokemon']
        if type(mon.get('species_id')) is not int:
            continue
        records.append((str(entry.get('recorded_at') or ''), str(key), mon))
    records.sort(key=lambda r: (r[0], r[1]), reverse=order != 'oldest')
    return records[:limit] if limit else records


def run_stats(progress: Any, party_public: list[dict[str, Any]]) -> dict[str, int]:
    """Numbers for the OBS stats layer, from data the tracker already keeps."""
    progress = progress or {}
    encounters = progress.get('encounters')
    missed = progress.get('missed_routes')
    deaths = progress.get('deaths')
    return {
        'captures': len(encounters) if isinstance(encounters, dict) else 0,
        'deaths': len(deaths) if isinstance(deaths, (dict, list)) else 0,
        'alive': sum(1 for p in party_public if p.get('present') and not p.get('dead') and (p.get('hp') or 0) > 0),
        'missed': len(missed) if isinstance(missed, list) else 0,
    }


class GraveyardMixin:
    _rev_key: bytes
    service: Any

    def _grave_rev(self, key: str) -> str:
        return hmac.new(self._rev_key, key.encode('utf-8'), hashlib.sha256).hexdigest()[:12]

    def _progress_records(self, limit: int = 60, order: str = 'recent') -> list[Record]:
        if hasattr(self.service, 'condition') and hasattr(self.service, 'state'):
            with self.service.condition:
                return copy.deepcopy(graveyard_records(self.service.state.get('progress'), order, limit))
        return graveyard_records(self.service.snapshot().get('progress'), order, limit)

    def graveyard_entry(self, index):
        """Pokémon record shown at position `index` of the public graveyard."""
        if type(index) is not int or not 0 <= index < 60:
            return None
        records = self._progress_records()
        return records[index][2] if index < len(records) else None

    def graveyard_entry_for(self, rev):
        """Record whose public image_rev matches; stable while new deaths shift positions."""
        if not isinstance(rev, str) or not GRAVE_REV.fullmatch(rev):
            return None
        for _, key, mon in self._progress_records(limit=0):
            if self._grave_rev(key) == rev:
                return mon
        return None

    def _graveyard_public(self, records: list[Record]) -> list[dict[str, Any]]:
        result = []
        for index, (_recorded, key, mon) in enumerate(records):
            level = mon.get('level')
            result.append({
                'n': index,
                'species_id': mon['species_id'],
                'nickname': str(mon.get('nickname') or mon.get('species') or '')[:40],
                'species': str(mon.get('species') or '')[:40],
                'level': level if type(level) is int and 1 <= level <= 100 else None,
                'route': str(mon.get('met_location') or '')[:60],
                'image_rev': self._grave_rev(key),
            })
        return result
