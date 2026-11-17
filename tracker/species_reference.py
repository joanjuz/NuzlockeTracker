"""Small bundled species/form references. No network, ROM or emulator access."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from .game_data import TYPE_NAMES

DATA = Path(__file__).resolve().parent.parent / 'data' / 'SpeciesReference_Gen6Gen7.json'
GAMES = {'Pokémon X 1.0':'xy', 'Pokémon Y 1.0':'xy',
         'Omega Ruby 1.0':'ao', 'Alpha Sapphire 1.0':'ao',
         'Ultra Sun 1.0':'uu', 'Ultra Moon 1.0':'uu'}
LABELS = {'xy':'X/Y', 'ao':'ORAS', 'uu':'USUM'}
STAT_KEYS = ('HP','ATK','DEF','SPA','SPD','SPE')


class SpeciesReference:
    """Exact known forms only; unknown forms never masquerade as the normal one."""

    def __init__(self, path: Path = DATA) -> None:
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            self.data: dict[str, Any] = data if data.get('schema_version') == 1 else {}
        except (OSError, ValueError, AttributeError):
            self.data = {}

    def lookup(self, species: Any, form: Any, game: str) -> dict[str, Any] | None:
        table = GAMES.get(game)
        if table is None or type(species) is not int or type(form) is not int or species < 1 or form < 0:
            return None
        row = self.data.get('tables', {}).get(table, {}).get(f'{species}:{form}')
        if row is None:
            return None
        return {'base_stats':dict(zip(STAT_KEYS, row[0])),
                'types':[TYPE_NAMES[index] for index in row[1]], 'abilities':list(row[2]),
                'source':f'Referencia {LABELS[table]} · PKHeX'}

    def mega_stone(self, item: Any) -> dict[str, Any] | None:
        if type(item) is not int:
            return None
        stone = self.data.get('mega_stones', {}).get(str(item))
        return {str(key):copy.deepcopy(value) for key,value in stone.items()} if isinstance(stone, dict) else None
