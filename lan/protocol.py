"""Minimal, validated payloads: never transmit emulator memory or local files."""
from __future__ import annotations

SLOTS = {
    'A-SUN': ('A', 'Ultra Sun 1.0'),
    'A-MOON': ('A', 'Ultra Moon 1.0'),
    'B-SUN': ('B', 'Ultra Sun 1.0'),
    'B-MOON': ('B', 'Ultra Moon 1.0'),
}


def safe_string(value, limit=36):
    if not isinstance(value, str):
        return ''
    return ''.join(ch for ch in value if ch.isprintable() and ch not in '<>\r\n').strip()[:limit]


def _integer(value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError('Valor numerico fuera de rango')
    return value


def public_state(state):
    """Make an explicit allowlist from /api/state (no personal/local fields)."""
    if not isinstance(state, dict):
        raise ValueError('Estado invalido')
    game = state.get('game')
    if game not in ('Ultra Sun 1.0', 'Ultra Moon 1.0'):
        raise ValueError('Juego no compatible')
    connection = state.get('connection') or {}
    online = isinstance(connection, dict) and connection.get('status') == 'connected' and state.get('stale') is False
    result = []
    if online:
        party = state.get('party')
        if not isinstance(party, list) or len(party) != 6:
            raise ValueError('Equipo invalido')
        for member in party:
            if member is None:
                result.append(None)
                continue
            if not isinstance(member, dict):
                raise ValueError('Pokemon invalido')
            species = _integer(member.get('species_id'), 1, 1025)
            level = _integer(member.get('level'), 1, 100)
            max_hp = _integer(member.get('max_hp'), 1, 9999)
            hp = _integer(member.get('hp'), 0, max_hp)
            result.append({
                'species_id': species,
                'species': safe_string(member.get('species'), 32),
                'nickname': safe_string(member.get('nickname'), 24),
                'level': level, 'hp': hp, 'max_hp': max_hp,
            })
    return {'game': game, 'online': bool(online), 'party': result if online else [None] * 6,
            'battle_hp': bool(state.get('battle_hp')) if online else False}


def validate_submission(data, expected_game):
    """Strictly re-validate client data at the LAN receiver."""
    if not isinstance(data, dict) or data.get('game') != expected_game or type(data.get('online')) is not bool or type(data.get('battle_hp')) is not bool:
        raise ValueError('Juego o estado incompatible con este puesto')
    if any(key not in {'game', 'online', 'battle_hp', 'party', 'display_name'} for key in data):
        raise ValueError('Campos no permitidos')
    if 'display_name' in data and (not isinstance(data['display_name'], str) or not data['display_name'] or safe_string(data['display_name'], 24) != data['display_name']):
        raise ValueError('Nombre de jugador invalido')
    team = data.get('party')
    if not isinstance(team, list) or len(team) != 6:
        raise ValueError('Equipo incorrecto')
    if not data['online']:
        if any(p is not None for p in team) or data['battle_hp']:
            raise ValueError('Estado desconectado incorrecto')
        return {'game': expected_game, 'online': False, 'battle_hp': False, 'party': [None] * 6}
    clean = []
    for member in team:
        if member is None:
            clean.append(None)
            continue
        if not isinstance(member, dict) or any(key not in {'species_id', 'species', 'nickname', 'level', 'hp', 'max_hp'} for key in member):
            raise ValueError('Campos de Pokemon no permitidos')
        species = _integer(member.get('species_id'), 1, 1025)
        level = _integer(member.get('level'), 1, 100)
        max_hp = _integer(member.get('max_hp'), 1, 9999)
        hp = _integer(member.get('hp'), 0, max_hp)
        if not isinstance(member.get('species'), str) or not isinstance(member.get('nickname'), str):
            raise ValueError('Nombre invalido')
        if safe_string(member['species'], 32) != member['species'] or safe_string(member['nickname'], 24) != member['nickname']:
            raise ValueError('Nombre no permitido')
        clean.append({'species_id': species, 'species': member['species'], 'nickname': member['nickname'],
                      'level': level, 'hp': hp, 'max_hp': max_hp})
    return {'game': expected_game, 'online': True, 'battle_hp': data['battle_hp'], 'party': clean}
