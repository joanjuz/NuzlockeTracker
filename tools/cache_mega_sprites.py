"""Refresh the small bundled mega sprites from a pinned public reference."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
REVISION = 'c0542f7c51215d9672439012838c99f520596cbd'


def main():
    data = json.loads((ROOT / 'data/SpeciesReference_Gen6Gen7.json').read_text(encoding='utf-8'))
    ids = sorted({ident for row in data['mega_stones'].values() for ident in (row['sprite_id'], row['species'])})
    def fetch(ident):
        url = f'https://raw.githubusercontent.com/PokeAPI/sprites/{REVISION}/sprites/pokemon/{ident}.png'
        with urlopen(url, timeout=25) as response:
            raw = response.read(100000)
        if not raw.startswith(b'\x89PNG\r\n\x1a\n'):
            raise ValueError(f'Invalid reference PNG: {ident}')
        (ROOT / 'data/sprites' / f'{ident}.png').write_bytes(raw)
        return {'id': ident, 'url': url, 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}
    with ThreadPoolExecutor(max_workers=6) as pool:
        rows = list(pool.map(fetch, ids))
    (ROOT / 'data/MegaSpriteSources.json').write_text(json.dumps({'revision': REVISION, 'sprites': rows}, indent=2)+'\n', encoding='utf-8')
    print(f'{len(rows)} sprites, {sum(row["bytes"] for row in rows)} bytes')


if __name__ == '__main__':
    main()
