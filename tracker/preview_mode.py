"""Explicit portable preview isolation, separate from installed user profiles."""
from __future__ import annotations

import json
from pathlib import Path
import sys


def preview_home(executable=None, *, frozen=None):
    """A sibling marker opts frozen previews into a fixed private data folder.

    Invalid markers fail closed: they must never silently open stable profiles.
    Source launches and ordinary distributions retain their existing behavior.
    """
    if frozen is None:
        frozen = getattr(sys, 'frozen', False)
    if not frozen:
        return None
    root = Path(executable or sys.executable).resolve().parent
    marker = root / 'TRACKER_PREVIEW.json'
    if not marker.exists():
        return None
    try:
        config = json.loads(marker.read_text(encoding='utf-8'))
    except (OSError, ValueError) as error:
        raise ValueError('No se pudo leer el marcador de la preview.') from error
    if config != {'format': 'progressive-tracker-preview', 'version': 1}:
        raise ValueError('El marcador de la preview no es compatible.')
    home = (root / 'Datos-Prueba').resolve()
    if not home.is_relative_to(root):
        raise ValueError('La carpeta de datos de prueba sale de la preview.')
    return home
