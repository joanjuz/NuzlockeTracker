"""The only state allowed to leave a local tracker for a Soul Link partner."""
import json
import re
from tracker.profiles import PROFILES

SUPPORTED_GAMES = frozenset(PROFILES)

MAX_SNAPSHOT_BYTES = 650_000
POKEMON_FIELDS = {
    'species_id', 'species', 'nickname', 'slot', 'level', 'hp', 'max_hp', 'stats',
    'ability', 'item', 'move_names', 'moves', 'nature', 'iv', 'ev', 'met_location',
    'met_location_id', 'met_level', 'met_date', 'egg_location', 'egg_location_id',
    'origin_version', 'encryption_constant', 'egg', 'form', 'type_source', 'types',
    'ability_id', 'item_id', 'move_pp', 'move_pp_ups', 'base_stats', 'evolutions',
}

# Partner data reaches HTML renderers. Text may never carry markup or control
# characters, and every number/list has the shape tracker/pokemon.py produces.
UNSAFE_TEXT = re.compile(r'[<>\x00-\x1f\x7f]')
STAT_KEY = re.compile(r'[A-Za-z_]{1,8}')
ISO_DATE = re.compile(r'[0-9]{4}-[0-9]{2}-[0-9]{2}')
EVOLUTION_INTS = {'target': (1, 1025), 'target_form': (-1, 255), 'form': (-1, 255),
                  'sprite_id': (1, 65535), 'level': (0, 100)}
EVOLUTION_TEXT = ('target_name', 'method', 'raw_method', 'source', 'item')


def _fail(field):
    raise ValueError('Dato Pokémon no válido: ' + field)


def safe_text(value, limit):
    return isinstance(value, str) and len(value) <= limit and UNSAFE_TEXT.search(value) is None


def _int(value, low, high):
    return type(value) is int and low <= value <= high


def _text_field(limit):
    def check(field, value):
        if not safe_text(value, limit):
            _fail(field)
        return value
    return check


def _int_field(low, high, nullable=False):
    def check(field, value):
        if value is None and nullable:
            return None
        if not _int(value, low, high):
            _fail(field)
        return value
    return check


def _int_list(low, high, max_len, exact=None):
    def check(field, value):
        if (not isinstance(value, list) or len(value) > max_len
                or (exact is not None and len(value) != exact)
                or not all(_int(v, low, high) for v in value)):
            _fail(field)
        return list(value)
    return check


def _text_list(limit, max_len):
    def check(field, value):
        if not isinstance(value, list) or len(value) > max_len or not all(safe_text(v, limit) for v in value):
            _fail(field)
        return list(value)
    return check


def _stat_dict(high):
    def check(field, value):
        if value is None:
            return None
        if (not isinstance(value, dict) or len(value) > 8 or
                not all(isinstance(k, str) and STAT_KEY.fullmatch(k) and _int(v, 0, high) for k, v in value.items())):
            _fail(field)
        return dict(value)
    return check


def _nickname(field, value):
    # Free text decoded from game RAM: neutralise instead of losing the whole sync.
    if not isinstance(value, str) or len(value) > 40:
        _fail(field)
    return UNSAFE_TEXT.sub('', value.replace('<', '\u2039').replace('>', '\u203a'))


def _met_date(field, value):
    if value is None:
        return None
    if not isinstance(value, str) or ISO_DATE.fullmatch(value) is None:
        _fail(field)
    return value


def _bool(field, value):
    if type(value) is not bool:
        _fail(field)
    return value


def _evolutions(field, value):
    if not isinstance(value, list) or len(value) > 64:
        _fail(field)
    result = []
    for record in value:
        if not isinstance(record, dict) or len(record) > 24:
            _fail(field)
        clean = {}
        for key, (low, high) in EVOLUTION_INTS.items():
            if key in record:
                if record[key] is not None and not _int(record[key], low, high):
                    _fail(field)
                clean[key] = record[key]
        for key in EVOLUTION_TEXT:
            if key in record:
                if record[key] is not None and not safe_text(record[key], 200):
                    _fail(field)
                clean[key] = record[key]
        result.append(clean)
    return result


FIELD_CHECKS = {
    'species': _text_field(100), 'nickname': _nickname, 'ability': _text_field(100),
    'item': _text_field(100), 'nature': _text_field(100), 'met_location': _text_field(180),
    'egg_location': _text_field(180), 'type_source': _text_field(60),
    'move_names': _text_list(100, 4), 'types': _text_list(30, 3),
    'slot': _int_field(0, 255), 'level': _int_field(1, 100, nullable=True),
    'hp': _int_field(0, 999, nullable=True), 'max_hp': _int_field(0, 999, nullable=True),
    'met_level': _int_field(0, 127), 'form': _int_field(0, 255), 'origin_version': _int_field(0, 255),
    'encryption_constant': _int_field(0, 0xFFFFFFFF), 'ability_id': _int_field(0, 65535),
    'item_id': _int_field(0, 65535), 'met_location_id': _int_field(0, 65535),
    'egg_location_id': _int_field(0, 65535),
    'moves': _int_list(0, 65535, 4), 'move_pp': _int_list(0, 255, 4), 'move_pp_ups': _int_list(0, 255, 4),
    'iv': _int_list(0, 31, 6, exact=6), 'ev': _int_list(0, 255, 6, exact=6),
    'stats': _stat_dict(999), 'base_stats': _stat_dict(255),
    'met_date': _met_date, 'egg': _bool, 'evolutions': _evolutions,
}
if set(FIELD_CHECKS) | {'species_id'} != POKEMON_FIELDS:
    raise RuntimeError('Cada campo compartido necesita una validación')


# Text fields that can be repaired instead of discarded, with their limits.
SALVAGE_TEXT = {'species': 100, 'nickname': 40, 'ability': 100, 'item': 100, 'nature': 100,
                'met_location': 180, 'egg_location': 180, 'type_source': 60}
SALVAGE_TEXT_LISTS = {'move_names': (100, 4), 'types': (30, 3)}


def _neutralise(value, limit):
    return UNSAFE_TEXT.sub('', value.replace('<', '‹').replace('>', '›'))[:limit]


def _salvage(key, value):
    """Repair or drop ONE bad field instead of losing the whole Soul Link session.

    A single odd value (an unbounded stat from RAM, '<' in a pk3DS CSV method)
    must not stop synchronisation. Text is neutralised; anything else that
    fails validation is removed, so hostile values never reach the UI.
    """
    if key in SALVAGE_TEXT and isinstance(value, str):
        return _neutralise(value, SALVAGE_TEXT[key])
    if key in SALVAGE_TEXT_LISTS and isinstance(value, list):
        limit, count = SALVAGE_TEXT_LISTS[key]
        if all(isinstance(v, str) for v in value[:count]):
            return [_neutralise(v, limit) for v in value[:count]]
    return _DROP


_DROP = object()
STRICT_FIELDS = {'encryption_constant', 'origin_version'}


def pokemon(member, max_species=1025):
    if member is None:
        return None
    if not isinstance(member, dict):
        raise ValueError('Registro Pokémon no válido')
    species = member.get('species_id')
    if type(species) is not int or not 1 <= species <= max_species:
        raise ValueError('Especie Pokémon no válida')
    result = {'species_id': species}
    for key, check in FIELD_CHECKS.items():
        if key in member:
            try:
                result[key] = check(key, member[key])
            except ValueError:
                if key in STRICT_FIELDS:
                    raise  # Identity: dropping it would mismatch deaths and routes.
                repaired = _salvage(key, member[key])
                if repaired is not _DROP:
                    result[key] = repaired
    return result


def snapshot(state):
    """Allowlist only; excludes connection metadata, PID, diagnostics and runtime paths."""
    if not isinstance(state, dict) or not isinstance(state.get('game'), str) or state['game'] not in SUPPORTED_GAMES:
        raise ValueError('Juego no compatible con Soul Link')
    if state.get('stale') is not False or (state.get('connection') or {}).get('status') != 'connected':
        raise ValueError('El tracker no tiene una lectura actual para compartir')
    generation = PROFILES[state['game']].generation
    max_boxes, max_species = (31, 721) if generation == 6 else (32, 807)
    party = state.get('party')
    if not isinstance(party, list) or len(party) != 6:
        raise ValueError('El equipo debe tener seis espacios')
    boxes = state.get('boxes') or {}
    if not isinstance(boxes, dict) or len(boxes) > max_boxes:
        raise ValueError('Cajas no válidas')
    result_boxes = {}
    for key, members in boxes.items():
        if not isinstance(key, str) or not key.isdigit() or not 1 <= int(key) <= max_boxes or not isinstance(members, list) or len(members) != 30:
            raise ValueError('Caja no válida')
        result_boxes[key] = [pokemon(p, max_species) for p in members]
    progress = state.get('progress') or {}
    deaths = progress.get('deaths') or {}
    if not isinstance(deaths, dict) or len(deaths) > 500:
        raise ValueError('Registro de debilitados no válido')
    safe_deaths = {}
    for key, entry in deaths.items():
        if not safe_text(key, 70) or not isinstance(entry, dict):
            raise ValueError('Registro de debilitados incorrecto')
        recorded_at = str(entry.get('recorded_at', ''))[:40]
        if not safe_text(recorded_at, 40):
            raise ValueError('Fecha de debilitado no válida')
        safe_deaths[key] = {'pokemon': pokemon(entry.get('pokemon'), max_species),
                            'recorded_at': recorded_at}
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
            not 1 <= record['species_id'] <= max_species):
            raise ValueError('Pokémon de marca inválido')
        # Redacted fields: no trainer IDs or other private game data.
        allowed = ('species_id','species','nickname','origin_version',
                   'encryption_constant','met_location_id','met_location')
        checked = pokemon({field: record[field] for field in allowed if field in record}, max_species)
        safe_marks[key] = {'kind': mark['kind'], 'pokemon': checked}
    traded_routes = progress.get('traded_routes') or []
    if (not isinstance(traded_routes,list) or len(traded_routes)>200 or
        any(not isinstance(route,str) or not route.isdigit() or len(route)>10
            for route in traded_routes)):
        raise ValueError('Rutas intercambiadas inválidas')
    count = progress.get('death_count', len(safe_deaths))
    if type(count) is not int or not 0 <= count <= 100000:
        raise ValueError('Contador de muertes no válido')
    missed = progress.get('missed_routes') or []
    if not isinstance(missed, list) or len(missed) > 200 or not all(safe_text(x, 20) for x in missed):
        raise ValueError('Rutas Miss incorrectas')
    data = {
        'schema_version': 1, 'game': state['game'],
        'party': [pokemon(p, max_species) for p in party], 'boxes': result_boxes,
        'progress': {'deaths': safe_deaths, 'missed_routes': missed,
                     'death_count': count, 'origins': safe_origins,
                     'route_marks': safe_marks, 'traded_routes': traded_routes},
        'battle_hp': state.get('battle_hp') is True,
    }
    raw = json.dumps(data, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    if len(raw) > MAX_SNAPSHOT_BYTES:
        raise ValueError('La sesión supera 650 KB; reduce las cajas leídas antes de sincronizar')
    return data


def shared_state(data):
    """Rebuild a snapshot received from a partner, Worker or cache.

    Never trust remote JSON: it passes through the same allowlist and type
    validation as local snapshots, so unknown keys are dropped and markup in
    any field is rejected before it reaches the UI.
    """
    if data is None:
        return None
    if not isinstance(data, dict) or data.get('schema_version') != 1:
        raise ValueError('Sesión del compañero incompatible')
    try:
        return snapshot(dict(data, stale=False, connection={'status': 'connected'}))
    except (TypeError, AttributeError, KeyError, RecursionError):
        raise ValueError('Sesión del compañero inválida') from None


def viewer_state(data):
    """Adapt a saved remote snapshot to existing read-only UI renderers."""
    if not isinstance(data, dict) or data.get('schema_version') != 1 or not isinstance(data.get('game'), str) or data['game'] not in SUPPORTED_GAMES:
        raise ValueError('Última sesión incompatible')
    state = shared_state(data)
    state.update(connection={'status': 'disconnected', 'message': 'Última sesión compartida'},
                 stale=True, selected_box=1, scan={'active': False, 'completed': 0},
                 demo=False, box_verified=True)
    return state
