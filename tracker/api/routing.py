"""Tabla de rutas mínima: patrón (fullmatch) -> función ``handler(req, match)``.

La primera ruta cuyo patrón coincide con la ruta COMPLETA gana. Opciones:

* ``remote=True``: la ruta también se sirve en el servidor de solo lectura de
  la VPN (``RemoteOverlayShare``). Todo lo demás responde 404 allí.
* ``needs_overlay=True``: responde ``404 {}`` si no hay OverlayManager.
"""
from __future__ import annotations

import re
from typing import Callable, NamedTuple


class Route(NamedTuple):
    pattern: re.Pattern
    handler: Callable
    remote: bool = False
    needs_overlay: bool = False


def route(pattern: str, handler: Callable, *, remote: bool = False,
          needs_overlay: bool = False) -> Route:
    """Crea una ruta. ``pattern`` es una expresión regular aplicada con fullmatch."""
    return Route(re.compile(pattern, re.S), handler, remote, needs_overlay)


def exact(path: str, handler: Callable, **options) -> Route:
    """Atajo para una ruta literal (sin caracteres especiales de regex)."""
    return route(re.escape(path), handler, **options)


def find(routes, path: str):
    for candidate in routes:
        match = candidate.pattern.fullmatch(path)
        if match:
            return candidate, match
    return None, None
