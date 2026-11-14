"""Genera el recurso de versión Windows desde tracker.__version__."""

from pathlib import Path
import runpy
import sys

version = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'tracker' / '__init__.py'))['__version__']
parts = tuple(int(part) for part in version.split('.'))
if len(parts) != 3 or any(part < 0 or part > 65535 for part in parts):
    raise ValueError('Versión Windows no válida')
quad = parts + (0,)
resource = f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={quad!r}, prodvers={quad!r},
    mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[StringFileInfo([StringTable('040904B0', [
    StringStruct('FileDescription', 'Progressive Tracker'),
    StringStruct('FileVersion', '{version}'),
    StringStruct('InternalName', 'PokemonTracker'),
    StringStruct('OriginalFilename', 'PokemonTracker.exe'),
    StringStruct('ProductName', 'Progressive Tracker'),
    StringStruct('ProductVersion', '{version}')
  ])]), VarFileInfo([VarStruct('Translation', [1033, 1200])])]
)
"""
Path(sys.argv[1]).write_text(resource, encoding='utf-8')
