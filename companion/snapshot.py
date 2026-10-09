"""The only state allowed to leave a local tracker for a Soul Link partner."""
import copy
import json
import re

MAX_SNAPSHOT_BYTES = 650_000
POKEMON_FIELDS = {
    'species_id', 'species', 'nickname', 'slot', 'level', 'hp', 'max_hp', 'stats',
    'ability', 'item', 'move_names', 'moves', 'nature', 'iv', 'ev', 'met_location',
    'met_location_id', 'met_level', 'met_date', 'egg_location', 'egg_location_id',
    'origin_version', 'encryption_constant', 'egg', 'form', 'type_source', 'types',
    'ability_id', 'item_id', 'move_pp', 'move_pp_ups', 'base_stats', 'evolutions',
}


def pokemon(member):
    if member is None:
        return None
    if not isinstance(member, dict):
        raise ValueError('Registro Pokémon no válido')
    species = member.get('species_id')
    if type(species) is not int or not 1 <= species <= 1025:
        raise ValueError('Especie Pokémon no válida')
    return {key: copy.deepcopy(value) for key, value in member.items() if key in POKEMON_FIELDS}


def snapshot(state):
    """Allowlist only; excludes connection metadata, PID, diagnostics and runtime paths."""
    if not isinstance(state, dict) or state.get('game') not in ('Ultra Sun 1.0', 'Ultra Moon 1.0'):
        raise ValueError('Juego no compatible con Soul Link')
    if state.get('stale') is not False or (state.get('connection') or {}).get('status') != 'connected':
        raise ValueError('El tracker no tiene una lectura actual para compartir')
    party = state.get('party')
    if not isinstance(party, list) or len(party) != 6:
        raise ValueError('El equipo debe tener seis espacios')
    boxes = state.get('boxes') or {}
    if not isinstance(boxes, dict) or len(boxes) > 32:
        raise ValueError('Cajas no válidas')
    result_boxes = {}
    for key, members in boxes.items():
        if not isinstance(key, str) or not key.isdigit() or not 1 <= int(key) <= 32 or not isinstance(members, list) or len(members) != 30:
            raise ValueError('Caja no válida')
        result_boxes[key] = [pokemon(p) for p in members]
    progress = state.get('progress') or {}
    deaths = progress.get('deaths') or {}
    if not isinstance(deaths, dict) or len(deaths) > 500:
        raise ValueError('Registro de debilitados no válido')
    safe_deaths = {}
    for key, entry in deaths.items():
        if not isinstance(key, str) or len(key) > 70 or not isinstance(entry, dict):
            raise ValueError('Registro de debilitados incorrecto')
        safe_deaths[key] = {'pokemon': pokemon(entry.get('pokemon')),
                            'recorded_at': str(entry.get('recorded_at', ''))[:40]}
        # Share ONLY this harmless flag: the partner must display the death
        # in Muertos, without creating a second Soul Link notification.
        if entry.get('source') == 'soullink-response':
            safe_deaths[key]['source'] = 'soullink-response'
    # Solo categorías elegidas manualmente; el auto-detectado se calcula en la UI.
    # No se comparte metadato adicional, únicamente la clave EC ya presente.
    origins = progress.get('origins') or {}
    categories = ('route', 'fossil', 'gift', 'egg', 'trade')
    if not isinstance(origins, dict) or len(origins) > 1200:
        raise ValueError('Clasificaciones de origen inválidas')
    if any(not isinstance(key, str) or re.fullmatch(r'[0-9]{1,3}:[0-9]{1,10}', key) is None or
           not isinstance(value, str) or value not in categories
           for key, value in origins.items()):
        raise ValueError('Clasificación de origen no válida')
    safe_origins = dict(origins)
    route_marks = progress.get('route_marks') or {}
    if not isinstance(route_marks, dict) or len(route_marks) > 1200:
        raise ValueError('Historial de marcas inválido')
    safe_marks = {}
    for key, mark in route_marks.items():
        if (not isinstance(key, str) or
            re.fullmatch(r'[0-9]{1,3}:[0-9]{1,10}', key) is None or
            not isinstance(mark, dict) or mark.get('kind') not in ('trade','fossil')
            or not isinstance(mark.get('pokemon'), dict)):
            raise ValueError('Marca de ruta inválida')
        record = mark['pokemon']
        if (type(record.get('species_id')) is not int or
            not 1 <= record['species_id'] <= 1025):
            raise ValueError('Pokémon de marca inválido')
        # Redacted fields: no trainer IDs or other private game data.
        allowed = ('species_id','species','nickname','origin_version',
                   'encryption_constant','met_location_id','met_location')
        safe_marks[key] = {'kind': mark['kind'],
                           'pokemon': {field: copy.deepcopy(record[field])
                                       for field in allowed if field in record}}
    count = progress.get('death_count', len(safe_deaths))
    if type(count) is not int or not 0 <= count <= 100000:
        raise ValueError('Contador de muertes no válido')
    missed = progress.get('missed_routes') or []
    if not isinstance(missed, list) or len(missed) > 200 or any(not isinstance(x, str) or len(x) > 20 for x in missed):
        raise ValueError('Rutas Miss incorrectas')
    data = {
        'schema_version': 1, 'game': state['game'],
        'party': [pokemon(p) for p in party], 'boxes': result_boxes,
        'progress': {'deaths': safe_deaths, 'missed_routes': missed,
                     'death_count': count, 'origins': safe_origins,
                     'route_marks': safe_marks},
        'battle_hp': state.get('battle_hp') is True,
    }
    raw = json.dumps(data, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    if len(raw) > MAX_SNAPSHOT_BYTES:
        raise ValueError('La sesión supera 650 KB; reduce las cajas leídas antes de sincronizar')
    return data


def viewer_state(data):
    """Adapt a saved remote snapshot to existing read-only UI renderers."""
    if not isinstance(data, dict) or data.get('schema_version') != 1 or data.get('game') not in ('Ultra Sun 1.0', 'Ultra Moon 1.0'):
        raise ValueError('Última sesión incompatible')
    state = copy.deepcopy(data)
    state.update(connection={'status': 'disconnected', 'message': 'Última sesión compartida'},
                 stale=True, selected_box=1, scan={'active': False, 'completed': 0},
                 demo=False, box_verified=True)
    return state
