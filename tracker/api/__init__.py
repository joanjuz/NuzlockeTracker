"""Rutas HTTP del tracker local (servidor de server.py y de la ventana nativa).

Módulos:
  handler.py   make_handler(), comprobaciones de origen/token y despacho.
  routing.py   Route, route(), exact(), find().
  context.py   ApiContext (servicio, overlay, companion, perfiles...) y ROOT.
  static.py    archivos de web/, CSP y sprites de Pokémon.
  overlay.py   /overlay*, /api/overlay/* (OBS y editor).
  state.py     /api/state, /api/session, /api/routes, /api/move, /api/diagnostic,
               /api/processes, /api/templates, /ws.
  companion.py /api/companion (Soul Link).
  profiles.py  /api/profiles (partidas locales).
  commands.py  /api/command (validación y cola de órdenes).
  update.py    /api/update (aviso de nueva versión, solo local).

Para añadir una ruta: función ``fn(req, match)`` en el módulo del tema y una
entrada ``exact(...)``/``route(...)`` en su ROUTES_GET o ROUTES_POST.
"""
from .context import ROOT, ApiContext
from .handler import ROUTES_GET, ROUTES_POST, TrackerRequestHandler, make_handler
from .state import frame
from .static import content_security_policy

__all__ = ['ROOT', 'ApiContext', 'ROUTES_GET', 'ROUTES_POST', 'TrackerRequestHandler',
           'make_handler', 'frame', 'content_security_policy']
