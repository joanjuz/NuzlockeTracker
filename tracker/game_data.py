"""Definitive Game Data v1: validated local metadata, never emulator writes."""
from __future__ import annotations

import copy
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import re
import secrets
import struct
import threading

from .progress import MAX_STAGES, MAX_STAGE_NAME, _CONTROL_CHARACTERS
from .templates import evolutions_csv
from .profile_provenance import profile_provenance_summary

MAX_BYTES = 5_000_000
GAMES = {'ultra-sun': ('Ultra Sun 1.0', '00040000001B5000'),
         'ultra-moon': ('Ultra Moon 1.0', '00040000001B5100')}
# Game IDs, not PokéAPI IDs nor the alphabetic display order.
TYPE_NAMES = ['Normal', 'Lucha', 'Volador', 'Veneno', 'Tierra', 'Roca', 'Bicho',
              'Fantasma', 'Acero', 'Fuego', 'Agua', 'Planta', 'Eléctrico',
              'Psíquico', 'Hielo', 'Dragón', 'Siniestro', 'Hada']
STAT_KEYS = {'hp': 'HP', 'attack': 'ATK', 'defense': 'DEF',
             'specialAttack': 'SPA', 'specialDefense': 'SPD', 'speed': 'SPE'}
SOURCE = 'Definitive Game Data'


def _object(value, label):
    if not isinstance(value, dict):
        raise ValueError(label + ' debe ser un objeto.')
    return value


def _integer(value, lo, hi, label):
    if type(value) is not int or not lo <= value <= hi:
        raise ValueError(f'{label}: se requiere un entero entre {lo} y {hi}.')
    return value


def _text(value, label, maximum=200):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum or any(ord(c) < 32 for c in value):
        raise ValueError(label + ': texto vacío, demasiado largo o con controles.')
    return value


def _array(value, maximum, label):
    if not isinstance(value, list) or len(value) > maximum:
        raise ValueError(label + ': lista inválida o demasiado grande.')
    return value


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Clave JSON duplicada: ' + key)
        result[key] = value
    return result


def validate_document(content):
    """Return a detached document; optional unknown fields survive validation."""
    if not isinstance(content, str) or len(content.encode('utf-8')) > MAX_BYTES:
        raise ValueError('El JSON DGD debe ocupar como máximo 5 MB.')
    try:
        doc = json.loads(content, object_pairs_hook=_pairs,
                         parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Número JSON inválido.')))
    except (json.JSONDecodeError, RecursionError) as exc:
        raise ValueError('JSON DGD inválido o demasiado anidado.') from exc
    _object(doc, 'Documento')
    if doc.get('format') != 'PokeJuz.DefinitiveGameData' or type(doc.get('schemaVersion')) is not int or doc['schemaVersion'] != 1:
        raise ValueError('Se requiere Definitive Game Data con schemaVersion 1.')
    producer = _object(doc.get('producer'), 'Productor')
    if producer.get('id') != 'DefinitiveRandomizer':
        raise ValueError('Productor DGD no compatible.')
    _text(producer.get('version'), 'Versión del productor')
    game = _object(doc.get('game'), 'Juego')
    if not isinstance(game.get('id'),str) or game['id'] not in GAMES or type(game.get('generation')) is not int or game['generation'] != 7:
        raise ValueError('Esta entrega admite únicamente Ultra Sol y Ultra Luna.')
    if game.get('titleId') != GAMES[game['id']][1]:
        raise ValueError('El Title ID no coincide con el juego declarado.')
    if 'revision' not in game or (game.get('revisionStatus'), game.get('revision')) not in (('known', '1.0'), ('unknown', None)):
        raise ValueError('Revisión incompatible: se admite 1.0 o revisión desconocida con confirmación.')
    source = _object(doc.get('source'), 'Origen')
    if source.get('kind') != 'saved-project' or source.get('fingerprintAlgorithm') != 'SHA-256' or source.get('scope') != 'personal,moves,evolutions,gametext':
        raise ValueError('Origen o alcance del fingerprint no compatible.')
    if not isinstance(source.get('fingerprint'), str) or not re.fullmatch(r'[a-fA-F0-9]{64}', source['fingerprint']):
        raise ValueError('Fingerprint SHA-256 inválido.')
    if doc.get('coverage') != 'exported-records':
        raise ValueError('Cobertura DGD no compatible.')
    indexes = {}
    for section, maximum, hi in (('types', 18, 17), ('abilities', 234, 233)):
        rows = _array(doc.get(section), maximum, section)
        if not rows or section=='types' and len(rows)!=18:
            raise ValueError('Se requieren los 18 tipos y al menos una habilidad.')
        seen = set()
        for row in rows:
            _object(row, section)
            key = _integer(row.get('id'), 0, hi, section + '.id')
            if key in seen:
                raise ValueError('ID duplicado en ' + section)
            seen.add(key)
            _text(row.get('name'), section + '.name')
        indexes[section] = seen
    seen = set()
    species_rows = _array(doc.get('species'), 4096, 'species')
    if not species_rows:raise ValueError('Falta la tabla de especies.')
    for row in species_rows:
        _object(row, 'Especie')
        key = (_integer(row.get('speciesId'), 1, 807, 'speciesId'),
               _integer(row.get('formId'), 0, 31, 'formId'))
        if key in seen:
            raise ValueError('Especie/forma duplicada.')
        seen.add(key)
        _integer(row.get('personalIndex'), 1, 4095, 'personalIndex')
        # Several cosmetic forms can legitimately share one Personal record.
        _text(row.get('name'), 'Nombre de especie')
        for field, length, allowed in (('types', 2, indexes['types']), ('abilities', 3, indexes['abilities'])):
            values = _array(row.get(field), length, field)
            if len(values) != length or any(type(i) is not int or i not in allowed for i in values):
                raise ValueError('Referencias inválidas en especie.' + field)
        stats = _object(row.get('baseStats'), 'Estadísticas base')
        for field in STAT_KEYS:
            _integer(stats.get(field), 0, 255, 'baseStats.' + field)
    species_keys = seen
    seen = set()
    move_rows = _array(doc.get('moves'), 729, 'moves')
    if not move_rows:raise ValueError('Falta la tabla de movimientos.')
    for row in move_rows:
        _object(row, 'Movimiento')
        key = _integer(row.get('id'), 0, 728, 'move.id')
        if key in seen:
            raise ValueError('Movimiento duplicado.')
        seen.add(key)
        _text(row.get('name'), 'Nombre del movimiento')
        if type(row.get('typeId')) is not int or row['typeId'] not in indexes['types']:
            raise ValueError('Tipo del movimiento inválido.')
        for field, lo, hi in (('category', 0, 2), ('power', 0, 255), ('accuracy', 0, 255),
                              ('pp', 0, 255), ('priority', -8, 8)):
            _integer(row.get(field), lo, hi, 'move.' + field)
    seen = set()
    for row in _array(doc.get('evolutions'), 4096, 'evolutions'):
        _object(row, 'Evoluciones')
        key = (_integer(row.get('speciesId'), 1, 807, 'evolution.speciesId'),
               _integer(row.get('formId'), 0, 31, 'evolution.formId'))
        if key in seen:
            raise ValueError('Evoluciones de especie/forma duplicadas.')
        if key not in species_keys:
            raise ValueError('El origen de evolución no figura en la tabla de especies/formas.')
        seen.add(key)
        for route in _array(row.get('routes'), 8, 'Rutas de evolución'):
            _object(route, 'Ruta de evolución')
            for field, lo, hi in (('method', 1, 42), ('argument', 0, 65535),
                                  ('targetSpeciesId', 1, 807), ('targetFormId', -1, 127), ('level', 0, 100)):
                _integer(route.get(field), lo, hi, 'evolution.' + field)
    return doc


# --- Optional playerLevelCaps block (version 1) -------------------------------------------
# State of the Randomizer's Player Level Caps patch in the exported project. It is a mechanical
# restriction of that ROM, never the stages of a run: the tracker only offers it as a proposal.
# A block that is malformed, from a newer version or inconsistent is ignored on its own; it never
# invalidates the rest of the document, so data accepted by Tracker 1.4.0 stays accepted.
LEVEL_CAPS_BLOCK_VERSION = 1
LEVEL_CAPS_MAX_CHECKPOINTS = 128
LEVEL_CAPS_STATUSES = ('installed', 'not-detected', 'unsupported', 'inconsistent', 'legacy-format')
LEVEL_CAPS_HOOKS = ('stock', 'applied', 'applied-legacy', 'unrecognized', 'missing')
LEVEL_CAPS_STATUS_TEXT = {
    'not-detected': 'El proyecto exportado no tiene instalado el parche Player Level Caps de Definitive Randomizer.',
    'unsupported': 'El Randomizer no pudo reconocer el estado de Player Level Caps en el proyecto exportado.',
    'inconsistent': 'Las dos copias del parche Player Level Caps (experiencia y Caramelo Raro) no coinciden en el proyecto exportado.',
    'legacy-format': 'El proyecto exportado tiene Player Level Caps en un formato anterior, que no se puede importar.',
}
_SHA256 = re.compile(r'[0-9A-F]{64}\Z')


def _keys(value, allowed, label):
    _object(value, label)
    if set(value) - set(allowed):
        raise ValueError(label + ': campos no admitidos.')
    return value


def level_caps_table_sha256(checkpoints):
    """SHA-256 of the runtime table: 6 bytes per checkpoint and the Lv100 terminator."""
    data = bytearray()
    for point in checkpoints:
        condition = point['condition']
        if condition['kind'] == 'event-flag-set':
            data += struct.pack('<BBHH', 0, point['cap'], condition['byte'], condition['mask'])
        else:
            data += struct.pack('<BBHH', 1, point['cap'], condition['index'], condition['minimum'])
    data += bytes((0xFF, 100, 0, 0, 0, 0))
    return hashlib.sha256(bytes(data)).hexdigest().upper()


def _level_caps_condition(value):
    _object(value, 'Condición')
    kind = value.get('kind')
    if kind == 'event-flag-set':
        _keys(value, ('kind', 'byte', 'mask'), 'Condición')
        return {'kind': kind, 'byte': _integer(value.get('byte'), 0, 619, 'condition.byte'),
                'mask': _integer(value.get('mask'), 1, 255, 'condition.mask')}
    if kind == 'event-work-at-least':
        _keys(value, ('kind', 'index', 'minimum'), 'Condición')
        return {'kind': kind, 'index': _integer(value.get('index'), 0, 999, 'condition.index'),
                'minimum': _integer(value.get('minimum'), 1, 65535, 'condition.minimum')}
    raise ValueError('Tipo de condición no admitido.')


def validated_level_caps_block(block):
    """Strict check of a version 1 block (shape, status rules and installed-table rules); raises ValueError."""
    _keys(block, ('version', 'status', 'hooks', 'detail', 'evaluation', 'enforcement', 'ceiling', 'source', 'checkpoints'),
          'playerLevelCaps')
    if type(block.get('version')) is not int or block['version'] != LEVEL_CAPS_BLOCK_VERSION:
        raise ValueError('Versión del bloque no admitida.')
    status = block.get('status')
    if not isinstance(status, str) or status not in LEVEL_CAPS_STATUSES:
        raise ValueError('Estado del parche no admitido.')
    hooks = _keys(block.get('hooks'), ('battleCro', 'codeBin'), 'hooks')
    pair = (hooks.get('battleCro'), hooks.get('codeBin'))
    if set(hooks) != {'battleCro', 'codeBin'} or any(not isinstance(h, str) or h not in LEVEL_CAPS_HOOKS for h in pair):
        raise ValueError('Estado de una copia del parche no admitido.')
    unusable = any(h in ('unrecognized', 'missing') for h in pair)
    expected = {'installed': pair == ('applied', 'applied'),
                'not-detected': pair == ('stock', 'stock'),
                'inconsistent': all(h in ('stock', 'applied') for h in pair) and pair != ('stock', 'stock'),
                'legacy-format': not unusable and 'applied-legacy' in pair,
                'unsupported': unusable}[status]
    if not expected:
        raise ValueError('El estado no corresponde a las copias del parche.')
    detail = block.get('detail')
    if 'detail' in block and (not isinstance(detail, str) or not 1 <= len(detail) <= 500):
        raise ValueError('Detalle del productor inválido.')
    installed = status == 'installed'
    source = block.get('source')
    if 'source' in block or status != 'unsupported':
        _keys(source, ('fingerprintAlgorithm', 'scope', 'fingerprint', 'tableSha256'), 'source')
        if source.get('fingerprintAlgorithm') != 'SHA-256' or source.get('scope') != 'battle.cro,code.bin':
            raise ValueError('Origen del bloque no compatible.')
        for field in ('fingerprint',) + (('tableSha256',) if installed else ()):
            if not isinstance(source.get(field), str) or not _SHA256.match(source[field]):
                raise ValueError('SHA-256 del bloque inválido.')
        if not installed and 'tableSha256' in source:
            raise ValueError('Solo un parche instalado lleva el hash de su tabla.')
    result = {'version': LEVEL_CAPS_BLOCK_VERSION, 'status': status,
              'hooks': {'battleCro': pair[0], 'codeBin': pair[1]}, 'detail': detail,
              'fingerprint': source['fingerprint'] if isinstance(source, dict) else None,
              'tableSha256': None, 'checkpoints': []}
    if not installed:
        if any(field in block for field in ('evaluation', 'enforcement', 'ceiling', 'checkpoints')):
            raise ValueError('Solo un parche instalado lleva una lista de puntos.')
        return result
    if (block.get('evaluation') != 'ordered-first-incomplete' or block.get('enforcement') != ['exp-gain', 'rare-candy']
            or type(block.get('ceiling')) is not int or block['ceiling'] != 100):
        raise ValueError('Reglas del parche instalado no compatibles.')
    points = block.get('checkpoints')
    if not isinstance(points, list) or not 1 <= len(points) <= LEVEL_CAPS_MAX_CHECKPOINTS:
        raise ValueError('Lista de puntos inválida.')
    checkpoints, seen, previous = [], set(), 0
    for position, point in enumerate(points, 1):
        _keys(point, ('order', 'cap', 'condition', 'label', 'labelSource'), 'Punto')
        if _integer(point.get('order'), 1, LEVEL_CAPS_MAX_CHECKPOINTS, 'order') != position:
            raise ValueError('El orden de los puntos debe ser 1..n en el orden de la lista.')
        cap = _integer(point.get('cap'), 1, 100, 'cap')
        if cap < previous:
            raise ValueError('Los límites de los puntos no pueden bajar.')
        previous = cap
        condition = _level_caps_condition(point.get('condition'))
        key = tuple(sorted(condition.items()))
        if key in seen:
            raise ValueError('Cada condición debe aparecer una sola vez.')
        seen.add(key)
        label = point.get('label')
        if ('label' in point) != ('labelSource' in point):
            raise ValueError('La etiqueta y su origen van siempre juntos.')
        if 'label' in point:
            if (point.get('labelSource') != 'randomizer-catalog' or not isinstance(label, str) or not 1 <= len(label) <= 60
                    or label != label.strip() or any(ord(c) < 32 or ord(c) == 127 for c in label)):
                raise ValueError('Etiqueta de un punto inválida.')
        checkpoints.append({'order': position, 'cap': cap, 'condition': condition, 'label': label})
    if level_caps_table_sha256(checkpoints) != source['tableSha256']:
        raise ValueError('El hash de la tabla no coincide con los puntos.')
    result.update(tableSha256=source['tableSha256'], checkpoints=checkpoints)
    return result


def level_caps_condition_text(condition):
    if condition['kind'] == 'event-flag-set':
        return f"Event Flag · byte 0x{condition['byte']:04X}, máscara 0x{condition['mask']:02X}"
    return f"Event Work {condition['index']} ≥ {condition['minimum']}"


def level_caps_stage_name(point):
    """Stage name for a checkpoint: its catalog label, or its condition when it has none."""
    label = point.get('label')
    if isinstance(label, str) and 1 <= len(label) <= MAX_STAGE_NAME and not _CONTROL_CHARACTERS.search(label):
        return label
    return level_caps_condition_text(point['condition'])


def level_caps_summary(document):
    """What the tracker may do with the block of a validated document. Never raises.

    ``state``: ``absent`` (no block), ``ignored`` (newer version, malformed or inconsistent block),
    ``unavailable`` (valid block, patch not installed), ``rejected`` (more points than a run admits;
    never truncated) or ``proposal``. Only ``proposal`` carries ``stages``.
    """
    summary = {'state': 'absent', 'status': None, 'reason': None, 'detail': None, 'hooks': None,
               'fingerprint': None, 'tableSha256': None, 'ceiling': None, 'count': 0, 'maxStages': MAX_STAGES,
               'checkpoints': [], 'stages': []}
    if not isinstance(document, dict) or 'playerLevelCaps' not in document:
        return summary
    block = document['playerLevelCaps']
    version = block.get('version') if isinstance(block, dict) else None
    if type(version) is int and version > LEVEL_CAPS_BLOCK_VERSION:
        summary.update(state='ignored', reason=f'El archivo trae límites del Randomizer en un formato más nuevo (versión {version}). '
                       'Esta versión del Tracker los ignora; el resto de los datos se usa con normalidad.')
        return summary
    try:
        valid = validated_level_caps_block(block)
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        summary.update(state='ignored', reason='Los límites del Randomizer incluidos en el archivo no son válidos y se ignoran ('
                       + str(exc)[:200].rstrip('.') + '). El resto de los datos se usa con normalidad.')
        return summary
    summary.update(status=valid['status'], detail=valid['detail'], hooks=valid['hooks'], fingerprint=valid['fingerprint'])
    if valid['status'] != 'installed':
        summary.update(state='unavailable', reason=LEVEL_CAPS_STATUS_TEXT[valid['status']])
        return summary
    points = [{**point, 'name': level_caps_stage_name(point), 'conditionText': level_caps_condition_text(point['condition'])}
              for point in valid['checkpoints']]
    summary.update(tableSha256=valid['tableSha256'], ceiling=100, count=len(points), checkpoints=points)
    if len(points) > MAX_STAGES:
        summary.update(state='rejected', reason=f'El parche tiene {len(points)} puntos y una partida admite como máximo {MAX_STAGES} etapas. '
                       'La lista no se recorta: no se ofrece como propuesta.')
        return summary
    summary.update(state='proposal', stages=[{'name': point['name'], 'cap': point['cap']} for point in points])
    return summary


class GameDataManager:
    """One import per run directory, activated only for its compatible game."""
    def __init__(self, path):
        self.path = Path(path)
        self.document = None
        self.error = None
        self._pending = None
        self._lock = threading.RLock()
        if self.path.is_file():
            try:
                if self.path.stat().st_size > MAX_BYTES:
                    raise ValueError('DGD guardado demasiado grande.')
                self.document = validate_document(self.path.read_text(encoding='utf-8'))
            except (OSError, ValueError, UnicodeError) as exc:
                self.error = 'No se pudo cargar DGD: ' + str(exc)
        self._index_document()

    def _index_document(self):
        doc = self.document or {}
        self._records = {section: {((r['speciesId'], r['formId']) if section != 'moves' else r['id']): r
                                  for r in doc.get(section, [])}
                         for section in ('species', 'moves', 'evolutions')}
        self._level_caps = level_caps_summary(self.document)
        self._profile_provenance = profile_provenance_summary(self.document)

    def level_caps(self, game):
        """Summary of the optional playerLevelCaps block for ``game``; None when the import is not active."""
        with self._lock:
            return copy.deepcopy(self._level_caps) if self.active(game) else None

    def active(self, game):
        return self.document is not None and GAMES[self.document['game']['id']][0] == game

    def status(self, game):
        with self._lock:
            doc = self.document
            return {'loaded': doc is not None, 'active': self.active(game), 'error': self.error,
                    'game': GAMES[doc['game']['id']][0] if doc else None,
                    'revision': doc['game']['revision'] if doc else None,
                    'revisionStatus': doc['game']['revisionStatus'] if doc else None,
                    'producer': copy.deepcopy(doc['producer']) if doc else None,
                    'fingerprint': doc['source']['fingerprint'] if doc else None,
                    'counts': {s: len(doc[s]) if doc else 0 for s in ('species', 'moves', 'evolutions')},
                    'levelCaps': self.level_caps(game),
                    'profileProvenance': copy.deepcopy(self._profile_provenance) if self.active(game) else None,
                    'warning': 'El fingerprint identifica datos exportados; no comprueba la ROM cargada en el emulador.'}

    def species(self, species, form, game):
        return self._record('species', (species, form), game)

    def _record(self, section, key, game):
        if not self.active(game):
            return None
        return self._records[section].get(key)

    def move(self, ident, game):
        row = self._record('moves', ident, game)
        if row is None:
            return None
        return {'name': row['name'], 'type': TYPE_NAMES[row['typeId']],
                'category': ['Estado', 'Físico', 'Especial'][row['category']],
                **{k: row[k] for k in ('power', 'accuracy', 'pp', 'priority')},
                'source': SOURCE, 'rom_override': True}

    def ability_name(self, ident, game):
        if not self.active(game):
            return None
        return next((r['name'] for r in self.document['abilities'] if r['id'] == ident), None)

    def evolutions(self, species, form, game, catalog):
        row = self._record('evolutions', (species, form), game)
        if row is None:
            return None  # Distinct from an explicit empty evolution list.
        output = []
        for route in row['routes']:
            stream = io.StringIO()
            writer = csv.writer(stream)
            writer.writerow(['Source', 'Target', 'Method', 'Level', 'Argument', 'Form'])
            writer.writerow([species, route['targetSpeciesId'], route['method'], route['level'] or '',
                             route['argument'], route['targetFormId']])
            parsed = evolutions_csv(stream.getvalue(), catalog)[str(species)][0]
            output.append({**parsed, 'source': SOURCE,
                           'target_form': form if route['targetFormId'] == -1 else route['targetFormId']})
        return output

    def preview(self, content, game, comparison):
        with self._lock:
            doc = validate_document(content)
            if game not in {g[0] for g in GAMES.values()} or GAMES[doc['game']['id']][0] != game:
                raise ValueError('El JSON no corresponde al juego seleccionado de esta partida.')
            token = secrets.token_urlsafe(24)
            differences = comparison(doc)
            self._pending = (token, doc, game)
            return {'previewToken': token, 'game': game, 'revision': doc['game']['revision'],
                    'requiresRevisionAcknowledgement': doc['game']['revisionStatus'] == 'unknown',
                    'counts': {s: len(doc[s]) for s in ('species', 'moves', 'evolutions')},
                    'differences': differences[:20], 'replacesExisting': self.document is not None,
                    'profileProvenance': profile_provenance_summary(doc),
                    'warning': 'Se importarán datos informativos para esta partida. No se verifica ni modifica la ROM o la memoria del emulador.'}

    def apply(self, token, game, acknowledge_unknown=False):
        with self._lock:
            if self._pending is None or self._pending[0] != token or self._pending[2] != game:
                raise ValueError('La vista previa caducó o pertenece a otro juego. Vuelve a previsualizar.')
            doc = self._pending[1]
            if doc['game']['revisionStatus'] == 'unknown' and acknowledge_unknown is not True:
                raise ValueError('Confirma que la revisión del proyecto es desconocida antes de importar.')
            raw = json.dumps(doc, ensure_ascii=False, separators=(',', ':'))
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_name(self.path.name + '.' + secrets.token_hex(8) + '.tmp')
            try:
                temporary.write_text(raw, encoding='utf-8')
                os.replace(temporary, self.path)
            finally:
                temporary.unlink(missing_ok=True)
            self.document = doc
            self._index_document()
            self.error = None
            self._pending = None
            return self.status(game)

    def remove(self, game):
        with self._lock:
            self.path.unlink(missing_ok=True)
            self.document = None
            self._index_document()
            self.error = None
            self._pending = None
            return self.status(game)
