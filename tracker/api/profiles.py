"""Partidas locales: listar, crear, abrir y eliminar (GET/POST /api/profiles).

``ctx.profiles`` es el LocalBackend de desktop.py; sin él (server --demo o
pruebas) las rutas responden 404.
"""
from __future__ import annotations

from tracker.run_profiles import valid_profile_id

from .routing import exact

PROFILES_LIMIT = 1024


def status(req, _match):
    if req.ctx.profiles is None:
        req.reply(404, {'error': 'Perfiles no disponibles'})
        return
    req.reply(200, req.ctx.profiles.profiles_status())


def change(req, _match):
    profiles = req.ctx.profiles
    if profiles is None:
        req.reply(404, {'error': 'Perfiles no disponibles'})
        return
    try:
        obj = req.read_json(PROFILES_LIMIT, 'Solicitud demasiado grande', 'Solicitud incorrecta')
        action = obj.get('action')
        if action == 'create':
            result = profiles.create_profile(obj.get('name'))
        elif action == 'select':
            result = profiles.switch_profile(obj.get('id'))
        elif action == 'delete':
            ident = obj.get('id')
            if not valid_profile_id(ident):
                raise ValueError('Perfil inválido.')
            result = profiles.delete_profile(ident)
        else:
            raise ValueError('Acción de perfil inválida')
        req.reply(200, result)
    except (ValueError, TypeError, RuntimeError, OSError) as exc:
        req.reply(400, {'error': str(exc)})


ROUTES_GET = [exact('/api/profiles', status)]
ROUTES_POST = [exact('/api/profiles', change)]
