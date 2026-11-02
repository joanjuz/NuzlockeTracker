"""Genera data/ItemSprites.json: índice interno de objeto (Gen6/Gen7) -> sprite PokeAPI.

Uso: python tools/build_item_sprites.py
Fuente: tablas CSV públicas de PokeAPI (licencia en data/LICENSE_PokeAPI.md).
Solo se guardan nombres de archivo; las imágenes se descargan bajo demanda y
quedan en la caché local de sprites del usuario.
"""
from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
BASE = 'https://raw.githubusercontent.com/PokeAPI/pokeapi/master/data/v2/csv/'
TARGET = ROOT / 'data' / 'ItemSprites.json'


def table(name: str) -> list[dict[str, str]]:
    request = Request(BASE + name, headers={'User-Agent': 'Mozilla/5.0'})
    with urlopen(request, timeout=30) as response:
        return list(csv.DictReader(io.StringIO(response.read().decode('utf-8'))))


def main() -> None:
    identifiers = {row['id']: row['identifier'] for row in table('items.csv')}
    by_generation: dict[str, dict[str, str]] = {'6': {}, '7': {}}
    for row in table('item_game_indices.csv'):
        generation = row['generation_id']
        if generation in by_generation and row['item_id'] in identifiers:
            by_generation[generation][row['game_index']] = identifiers[row['item_id']]
    # Gen6 shares most indices with Gen7: store only Gen6 entries that differ.
    gen7 = by_generation['7']
    gen6 = {k: v for k, v in by_generation['6'].items() if gen7.get(k) != v}
    data = {'source': 'PokeAPI item_game_indices.csv', 'gen7': dict(sorted(gen7.items(), key=lambda kv: int(kv[0]))),
            'gen6_overrides': dict(sorted(gen6.items(), key=lambda kv: int(kv[0])))}
    TARGET.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    print(f'{TARGET.name}: {len(gen7)} objetos Gen7, {len(gen6)} diferencias Gen6')


if __name__ == '__main__':
    main()
