"""Estado compartido por las rutas HTTP: un ApiContext por cada make_handler().

Las funciones de ruta reciben el manejador de la petición (``req``) y acceden
a todo lo demás mediante ``req.ctx``. Nada aquí abre sockets ni toca la RAM
del emulador: solo agrupa los objetos que ya existían como variables de cierre.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Raíz de los recursos (web/, data/): junto a server.py en el código fuente o
# dentro del paquete de PyInstaller. tracker/api/context.py -> parents[2].
ROOT = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[2]))


@dataclass(eq=False)
class ApiContext:
    service: Any
    # repr=False: el token de sesión nunca debe acabar en un log o traza.
    token: str = field(repr=False)
    companion: Any = None
    profile: str = 'principal'
    overlay: Any = None
    share: Any = None
    remote_only: bool = False
    profiles: Any = None
    updates: Any = None
    sprites: Any = None      # static.SpriteStore (avisos Soul Link)
    item_icons: Any = None   # tracker.item_sprites.ItemSprites o None
    layout: Any = None       # PartyLayoutExporter (sprites del cementerio) o None

    def fields(self, *keys):
        # Narrow copy when the service offers it; never deep-copy 32 boxes
        # just to read the revision or the connection status.
        narrow = getattr(self.service, 'snapshot_fields', None)
        if callable(narrow):
            return narrow(*keys)
        state = self.service.snapshot()
        return {k: state.get(k) for k in keys}

    def current_revision(self):
        with self.service.condition:
            return self.service.state['revision']
