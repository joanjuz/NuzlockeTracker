"""Build the checked-in offline Gen6/Gen7 reference; never used at runtime.

Only six bases, types, abilities and species/form indices are retained from
PKHeX personal tables. Item/form associations use Pokemon Showdown; sprite IDs
use PokeAPI. All downloads are pinned and source digests are recorded.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path
import re
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
PKHEX_COMMIT = '6c9583883c7551ac74a4b74180cead249d4277b8'
SHOWDOWN_COMMIT = 'f827a1d41064e0dec4c19c6ea0394fcf0c23479c'
POKEAPI_COMMIT = '8d8a49d9295bbc951d882004570ca496866fd9d8'
SOURCES: list[dict[str, str]] = []


def download(repo: str, commit: str, path: str) -> bytes:
    url = f'https://raw.githubusercontent.com/{repo}/{commit}/{path}'
    with urlopen(Request(url, headers={'User-Agent':'ProgressiveTracker-reference-builder'}), timeout=30) as response:
        raw = response.read()
    SOURCES.append({'url':url, 'sha256':hashlib.sha256(raw).hexdigest()})
    return raw


def records(raw: bytes, size: int, maximum: int) -> dict[str, list[list[int]]]:
    if len(raw) % size:
        raise ValueError('Unexpected personal-table size')
    output = {}
    for species in range(1, maximum + 1):
        base = raw[species * size:(species + 1) * size]
        count = max(1, base[0x20])
        index = int.from_bytes(base[0x1c:0x1e], 'little')
        for form in range(count):
            at = index + form - 1 if form and index else species
            row = raw[at * size:(at + 1) * size]
            if len(row) != size or not row[0]:
                continue
            # Wire order is HP/ATK/DEF/SPA/SPD/SPE; the binary stores SPE at 3.
            output[f'{species}:{form}'] = [[row[i] for i in (0,1,2,4,5,3)],
                                          list(dict.fromkeys(row[6:8])), list(row[0x18:0x1b])]
    return output


def main() -> None:
    tables = {}
    for key, size, maximum in [('xy',0x40,721), ('ao',0x50,721), ('uu',0x54,807)]:
        raw = download('kwsch/PKHeX', PKHEX_COMMIT, 'PKHeX.Core/Resources/byte/personal/personal_' + key)
        tables[key] = records(raw, size, maximum)
    english = download('kwsch/PKHeX', PKHEX_COMMIT,
                       'PKHeX.Core/Resources/text/other/en/text_Species_en.txt').decode('utf-8-sig').splitlines()
    species_ids = {name:i for i,name in enumerate(english)}
    items = download('smogon/pokemon-showdown', SHOWDOWN_COMMIT, 'data/items.ts').decode('utf-8')
    pokemon = download('PokeAPI/pokeapi', POKEAPI_COMMIT, 'data/v2/csv/pokemon.csv').decode('utf-8')
    sprites = {row['identifier']:int(row['id']) for row in csv.DictReader(io.StringIO(pokemon))}
    mega_stones = {}
    for block in re.split(r'^\t[a-z0-9]+: \{', items, flags=re.M)[1:]:
        mega = re.search(r'megaStone:\s*\{\s*"([^"]+)":\s*"([^"]+)"', block)
        number = re.search(r'\bnum:\s*(\d+)', block)
        generation = re.search(r'\bgen:\s*(\d+)', block)
        if not mega or not number or not generation or int(generation[1]) > 7:
            continue
        species = species_ids[mega[1]]
        form = 2 if mega[2].endswith('-Y') else 1
        label = 'Mega Y' if form == 2 else 'Mega X' if mega[2].endswith('-X') else 'Mega'
        slug = mega[2].lower().replace(' ', '-')
        mega_stones[number[1]] = {'species':species, 'form':form, 'label':label,
                                 'sprite_id':sprites.get(slug, species)}
    if len(mega_stones) != 47:
        raise ValueError(f'Expected 47 Gen6/Gen7 mega stones, got {len(mega_stones)}')
    output = {'schema_version':1, 'sources':SOURCES, 'tables':tables, 'mega_stones':mega_stones}
    target = ROOT / 'data' / 'SpeciesReference_Gen6Gen7.json'
    target.write_text(json.dumps(output, ensure_ascii=False, separators=(',',':')) + '\n', encoding='utf-8')
    license_text = download('smogon/pokemon-showdown', SHOWDOWN_COMMIT, 'LICENSE').decode('utf-8')
    (ROOT / 'data' / 'LICENSE_PokemonShowdown.txt').write_text(license_text, encoding='utf-8')
    print(f'{target.name}: ' + ', '.join(f'{key}={len(rows)} forms' for key,rows in tables.items())
          + f'; {len(mega_stones)} stones')


if __name__ == '__main__':
    main()
