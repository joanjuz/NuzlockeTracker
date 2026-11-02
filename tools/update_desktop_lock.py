"""Regenera requirements-desktop.lock: versiones exactas + hashes SHA-256 de PyPI.

Uso (desde la raíz del repositorio):
    python tools/update_desktop_lock.py

Resuelve requirements-desktop.txt con `pip install --dry-run --report` (no
instala nada) y añade TODOS los hashes publicados de cada versión, así el
mismo archivo sirve para los wheels de Python 3.13 (CI) y 3.14 (local).
La compilación usa `pip install --require-hashes -r requirements-desktop.lock`.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / 'requirements-desktop.txt'
TARGET = ROOT / 'requirements-desktop.lock'


def resolve() -> list[tuple[str, str]]:
    with tempfile.TemporaryDirectory() as temp:
        report = Path(temp) / 'report.json'
        subprocess.run([sys.executable, '-m', 'pip', 'install', '--dry-run', '--ignore-installed',
                        '--quiet', '--report', str(report), '-r', str(SOURCE)], check=True)
        data = json.loads(report.read_text(encoding='utf-8'))
    return sorted((item['metadata']['name'].lower(), item['metadata']['version'])
                  for item in data['install'])


def hashes(name: str, version: str) -> list[str]:
    with urlopen(f'https://pypi.org/pypi/{name}/{version}/json', timeout=30) as response:
        files = json.load(response)['urls']
    found = sorted({f['digests']['sha256'] for f in files if f.get('digests', {}).get('sha256')})
    if not found:
        raise SystemExit(f'Sin hashes publicados para {name}=={version}')
    return found


def main() -> None:
    lines = ['# Generado por tools/update_desktop_lock.py; no editar a mano.',
             '# Fuente: requirements-desktop.txt. Instalar con:',
             '#   python -m pip install --require-hashes -r requirements-desktop.lock']
    for name, version in resolve():
        lines.append(f'{name}=={version} \\')
        digests = hashes(name, version)
        for index, digest in enumerate(digests):
            suffix = ' \\' if index < len(digests) - 1 else ''
            lines.append(f'    --hash=sha256:{digest}{suffix}')
    TARGET.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f'{TARGET.name}: {sum(1 for l in lines if "==" in l)} paquetes')


if __name__ == '__main__':
    main()
