"""Route-scoped capture selections. Uses the Tracker's existing route catalogs."""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from tracker.reference import ROUTE_PROFILES
from .snapshot import JSONDict

DATA = Path(__file__).resolve().parent.parent / 'data'


def family(game: str) -> str:
    if game.startswith('Ultra '):
        return 'alola'
    if game.startswith('Pokémon '):
        return 'xy'
    return 'oras'


@lru_cache(maxsize=6)
def routes(game: str) -> dict[int, int]:
    filename, _ = ROUTE_PROFILES[game]
    rows = json.loads((DATA / filename).read_text(encoding='utf-8'))['routes']
    return {location: row['id'] for row in rows for location in row.get('ids', [row['id']])}


def captures(game: str, state: JSONDict | None) -> dict[str, set[str]]:
    if state is None:
        return {}
    region = family(game)
    versions = {'xy': (24, 25), 'oras': (26, 27), 'alola': (30, 31, 32, 33)}[region]
    entries = [(None, p) for p in state['party']]
    entries += [(None, p) for box in state['boxes'].values() for p in box]
    entries += [(key, value['pokemon']) for key, value in state['progress']['deaths'].items()]
    entries += [(key, value['pokemon']) for key, value in state['progress']['route_marks'].items()]
    result: dict[str, set[str]] = {}
    for key, mon in entries:
        if not mon or mon.get('egg') or mon.get('origin_version') not in versions:
            continue
        if key is None:
            if type(mon.get('encryption_constant')) is not int:
                continue
            key = str(mon['origin_version']) + ':' + str(mon['encryption_constant'])
        if state['progress']['origins'].get(key, 'route') not in ('route',):
            continue
        canonical = routes(game).get(mon.get('met_location_id'))
        if canonical is not None:
            result.setdefault(f'{region}:{canonical}', set()).add(key)
    return result


def links(value: object, game: str) -> dict[str, str]:
    if not isinstance(value, dict) or len(value) > 200:
        raise ValueError('Grupos de captura inválidos')
    result = {}
    valid = {f'{family(game)}:{location}' for location in routes(game).values()}
    for route, key in value.items():
        if (not isinstance(route, str) or route not in valid or not isinstance(key, str)
                or re.fullmatch(r'\d{1,3}:\d{1,10}', key) is None):
            raise ValueError('La captura o la ruta no corresponde a este juego')
        result[route] = key
    return result
