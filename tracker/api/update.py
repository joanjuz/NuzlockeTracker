"""GET /api/update: aviso de nueva versión (solo local, nunca por la VPN).

``ctx.updates`` es un tracker.updates.UpdateChecker; sin él (demo, pruebas)
se responde la versión actual sin comprobar nada.
"""
from __future__ import annotations

from tracker.updates import empty_status

from .routing import exact


def update_status(req, _match):
    checker = req.ctx.updates
    req.reply(200, checker.status() if checker is not None else empty_status())


ROUTES_GET = [exact('/api/update', update_status)]
