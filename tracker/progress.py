"""Local, durable run annotations; independent of emulator and browser sessions."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import secrets
import shutil
from collections import Counter
from datetime import datetime, timezone
from collections.abc import Mapping
from pathlib import Path
from typing import Any


ORIGIN_CATEGORIES = ('route', 'fossil', 'gift', 'egg', 'trade')
ORIGIN_KEY_PATTERN = re.compile(r'[0-9]{1,3}:[0-9]{1,10}\Z')
MAX_ENCOUNTERS = 1200
# Pokémon dict from tracker/pokemon.py and the persisted history (JSON).
Pokemon = Mapping[str, Any]
JSONDict = dict[str, Any]
# Identity and encounter place only: never persist a full PK7 or expose ROM bytes.
ENCOUNTER_FIELDS = ('species_id', 'species', 'nickname', 'origin_version',
                    'encryption_constant', 'met_location_id', 'met_location',
                    'egg_location_id', 'egg')

# Manual level caps of one run and game. The player defines every stage: the
# tracker ships no official or default caps for any game, romhack or challenge.
LEVEL_CAPS_VERSION = 1
LEVEL_CAP_ACTIONS = ('level_caps_set', 'level_caps_current', 'level_caps_show',
                     'level_caps_accept_proposal', 'level_caps_dismiss_proposal')
MAX_STAGES = 64
MAX_STAGE_NAME = 60
STAGE_ID_PATTERN = re.compile(r'[A-Za-z0-9_-]{1,32}\Z')
# In-memory marker set while loading when a damaged block was moved aside; never written to disk.
_LEVEL_CAPS_ISOLATED = '_level_caps_isolated_now'
_CONTROL_CHARACTERS = re.compile(r'[\x00-\x1f\x7f-\x9f  ]')


class _Keep:
    """Sentinel: keep the current stage (by id) when replacing the stage list."""

    def __repr__(self) -> str:
        return 'KEEP_CURRENT'


KEEP_CURRENT: Any = _Keep()


def _stage_name(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError('El nombre de la etapa debe ser texto.')
    name = value.strip()
    if not 1 <= len(name) <= MAX_STAGE_NAME:
        raise ValueError(f'El nombre de la etapa debe tener entre 1 y {MAX_STAGE_NAME} caracteres.')
    if _CONTROL_CHARACTERS.search(name):
        raise ValueError('El nombre de la etapa contiene caracteres de control.')
    return name


def _stage_cap(value: Any) -> int:
    # bool is an int subclass: True must not become level 1.
    if type(value) is not int or not 1 <= value <= 100:
        raise ValueError('El límite de nivel debe ser un entero entre 1 y 100.')
    return value


def _stage_id(value: Any) -> str:
    if not isinstance(value, str) or STAGE_ID_PATTERN.fullmatch(value) is None:
        raise ValueError('Identificador de etapa inválido.')
    return value


def normalized_stages(stages: Any, allow_new: bool) -> list[JSONDict]:
    """Validated copy of a stage list, in the given order; raises ValueError.

    With ``allow_new`` a stage without ``id`` is accepted (a command creating
    it); it receives an id in :meth:`RunProgress.set_level_caps`. Stored
    stages always carry their id.
    """
    if not isinstance(stages, list):
        raise ValueError('Las etapas deben ser una lista.')
    if len(stages) > MAX_STAGES:
        raise ValueError(f'Como máximo {MAX_STAGES} etapas por partida y juego.')
    result: list[JSONDict] = []
    seen: set[str] = set()
    for stage in stages:
        if not isinstance(stage, dict) or set(stage) - {'id', 'name', 'cap'}:
            raise ValueError('Etapa con un formato inválido.')
        item: JSONDict = {'name': _stage_name(stage.get('name')), 'cap': _stage_cap(stage.get('cap'))}
        if 'id' in stage or not allow_new:
            stage_id = _stage_id(stage.get('id'))
            if stage_id in seen:
                raise ValueError('Hay etapas con el mismo identificador.')
            seen.add(stage_id)
            item = {'id': stage_id, **item}
        result.append(item)
    return result


def validated_level_caps(block: Any) -> JSONDict:
    """Stored level-caps block, normalized; raises ValueError when damaged.

    A block written by a newer tracker (higher ``version``) is kept untouched:
    it is neither validated nor rewritten, and it cannot be edited here.
    """
    if not isinstance(block, dict):
        raise ValueError('Bloque de límites de nivel inválido.')
    version = block.get('version')
    if type(version) is not int or version < 1:
        raise ValueError('Versión de límites de nivel inválida.')
    if version > LEVEL_CAPS_VERSION:
        return block
    if set(block) - {'version', 'stages', 'current', 'show', 'updated_at', 'removed_current'}:
        raise ValueError('Bloque de límites de nivel con campos desconocidos.')
    stages = normalized_stages(block.get('stages'), allow_new=False)
    current = block.get('current')
    if current is not None and current not in {s['id'] for s in stages}:
        raise ValueError('La etapa vigente no existe.')
    if type(block.get('show')) is not bool:
        raise ValueError('Opción de mostrar los límites inválida.')
    updated = block.get('updated_at')
    if updated is not None and (not isinstance(updated, str) or len(updated) > 40):
        raise ValueError('Fecha de los límites de nivel inválida.')
    removed = block.get('removed_current')
    if removed is not None:
        if not isinstance(removed, dict) or set(removed) != {'id', 'name', 'cap'}:
            raise ValueError('Etapa vigente eliminada inválida.')
        removed = {'id': _stage_id(removed['id']), 'name': _stage_name(removed['name']),
                   'cap': _stage_cap(removed['cap'])}
    return {'version': LEVEL_CAPS_VERSION, 'stages': stages, 'current': current, 'show': block['show'],
            'updated_at': updated, 'removed_current': removed}


def decreasing_stage_ids(stages: list[JSONDict]) -> list[str]:
    """Stages whose cap is lower than the previous stage: allowed, only reported."""
    return [stage['id'] for previous, stage in zip(stages, stages[1:]) if stage['cap'] < previous['cap']]


def stages_revision(stages: list[JSONDict]) -> str:
    """Short fingerprint of a saved stage list (ids, names, caps and order).

    It lets a confirmation refer to the exact list that was reviewed; it is derived, never stored in the block.
    """
    raw = json.dumps([[s['id'], s['name'], s['cap']] for s in stages], ensure_ascii=False, separators=(',', ':'))
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]


def level_caps_view(data: Mapping[str, Any]) -> JSONDict:
    """Read-only summary for the interface. Never feeds RAM reading, deaths or encounters."""
    block = data.get('level_caps')
    view: JSONDict = {'status': 'none', 'configured': False, 'show': False, 'stages': [], 'current': None,
                      'current_index': None, 'current_cap': None, 'current_name': None, 'total': 0,
                      'decreasing': [], 'removed_current': None, 'revision': stages_revision([]),
                      'rejected_kept': isinstance(data.get('level_caps_rejected'), dict)}
    if block is None:
        return view
    if not isinstance(block, dict) or block.get('version') != LEVEL_CAPS_VERSION:
        view['status'] = 'unsupported'
        return view
    stages: list[JSONDict] = block['stages']
    index = next((i for i, s in enumerate(stages) if s['id'] == block['current']), None)
    view.update({'status': 'ok', 'configured': bool(stages), 'show': block['show'],
                 'stages': copy.deepcopy(stages), 'current': block['current'], 'current_index': index,
                 'current_cap': None if index is None else stages[index]['cap'],
                 'current_name': None if index is None else stages[index]['name'], 'total': len(stages),
                 'decreasing': decreasing_stage_ids(stages), 'revision': stages_revision(stages),
                 'removed_current': copy.deepcopy(block.get('removed_current'))})
    return view


# Shareable stage list: names, caps and order only. It never carries stage ids, the current
# stage, display options or anything else from the run, so it is safe to hand to other players.
STAGE_LIST_FORMAT = 'progressive-tracker-stage-list'
STAGE_LIST_VERSION = 1


def stage_list_export(view: Mapping[str, Any]) -> JSONDict:
    """Portable document for the saved stage list of a level-caps view; raises ValueError.

    Reads the view only: nothing is changed and nothing else from the run is included.
    """
    if view.get('status') != 'ok':
        raise ValueError('Esta partida no tiene límites de nivel que se puedan exportar.')
    stages = [{'name': stage['name'], 'cap': stage['cap']} for stage in view.get('stages') or []]
    if not stages:
        raise ValueError('Esta partida no tiene etapas que exportar.')
    return {'format': STAGE_LIST_FORMAT, 'version': STAGE_LIST_VERSION, 'stages': stages}


def origin_category(pokemon: Pokemon, overrides: Mapping[str | None, str] | None = None) -> str:
    """Conservative classification; never infer a fossil/gift from species or location.

    The game preserves the egg acquisition location even after hatching.
    All other mechanisms need an explicit override from the player.
    """
    key = pokemon_key(pokemon)
    chosen = (overrides or {}).get(key)
    if chosen is not None and chosen in ORIGIN_CATEGORIES:
        return chosen
    if pokemon.get('egg') is True or (
        type(pokemon.get('egg_location_id')) is int
        and pokemon['egg_location_id'] > 0
    ):
        return 'egg'
    return 'route'


def pokemon_key(p: Pokemon) -> str | None:
    # EC stays unchanged when a Pokémon evolves, is renamed or changes slots.
    ec = p.get('encryption_constant')
    if type(ec) is not int:
        return None
    return f"{p.get('origin_version', 33)}:{ec}"


class RunProgress:
    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = Path(path)
        # recovered_from: None (normal load), 'backup' or 'empty' after a
        # corrupt file was quarantined. dirty: in-memory changes not on disk.
        self.recovered_from: str | None = None
        self.dirty = False
        self.last_save_error: str | None = None
        # Only a file this instance loaded or wrote may become the .bak copy.
        self.disk_verified = False
        # True when this load moved a damaged level-caps block aside (the rest loaded normally).
        self.level_caps_isolated = False
        self.data: JSONDict = self.empty_data()
        if self.path.exists():
            # OSError while reading (locked file) propagates on purpose:
            # starting empty would later overwrite a valid history.
            raw = self.path.read_bytes()
            try:
                self.data = self.validated(json.loads(raw.decode('utf-8')))
                self.disk_verified = True
            except (ValueError, TypeError, AttributeError, RecursionError):
                self.quarantine()
                backup = self.load_backup()
                self.recovered_from = 'empty' if backup is None else 'backup'
                self.data = self.validated(self.empty_data()) if backup is None else backup
                self.level_caps_isolated = bool(self.data.pop(_LEVEL_CAPS_ISOLATED, False))
                self.persist()
        else:
            self.data = self.validated(self.data)
        self.level_caps_isolated = bool(self.data.pop(_LEVEL_CAPS_ISOLATED, False)) or self.level_caps_isolated

    @staticmethod
    def empty_data() -> JSONDict:
        return {'deaths': {}, 'missed_routes': [], 'origins': {}, 'encounters': {}, 'route_marks': {}, 'traded_routes': []}

    @property
    def backup_path(self) -> Path:
        return self.path.with_name(self.path.name + '.bak')

    def quarantine(self) -> None:
        """Keep the damaged file for manual inspection; never delete it."""
        stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        target = self.path.with_name(f'{self.path.name}.corrupt-{stamp}')
        counter = 1
        while target.exists():
            target = self.path.with_name(f'{self.path.name}.corrupt-{stamp}-{counter}')
            counter += 1
        try:
            os.replace(self.path, target)
        except OSError:
            try:
                shutil.copy2(self.path, target)
            except OSError:
                pass

    def load_backup(self) -> JSONDict | None:
        try:
            return self.validated(json.loads(self.backup_path.read_text(encoding='utf-8')))
        except (OSError, ValueError, TypeError, AttributeError, RecursionError):
            return None

    @staticmethod
    def validated(data: Any) -> JSONDict:
        """Return the normalized history or raise ValueError/TypeError."""
        if not isinstance(data, dict):
            raise ValueError('El registro de la aventura no tiene un formato válido.')
        if not isinstance(data.get('deaths'), dict) or not isinstance(data.get('missed_routes'), list):
            raise ValueError('El registro de la aventura no tiene un formato válido.')
        origins = data.setdefault('origins', {})
        if not isinstance(origins, dict) or any(
            not isinstance(key, str) or re.fullmatch(r'[0-9]{1,3}:[0-9]{1,10}', key) is None or
            value not in ORIGIN_CATEGORIES for key, value in origins.items()
        ):
            raise ValueError('Clasificaciones de origen inválidas')
        encounters = data.setdefault('encounters', {})
        marks = data.setdefault('route_marks', {})
        if (not isinstance(encounters, dict) or len(encounters) > MAX_ENCOUNTERS or
            not isinstance(marks, dict) or len(marks) > MAX_ENCOUNTERS):
            raise ValueError('Historial de rutas inválido')
        for key, member in encounters.items():
            if (not isinstance(key, str) or ORIGIN_KEY_PATTERN.fullmatch(key) is None
                or not isinstance(member, dict) or
                type(member.get('species_id')) is not int or
                not 1 <= member['species_id'] <= 1025):
                raise ValueError('Registro de encuentro inválido')
        for key, mark in marks.items():
            if (not isinstance(key, str) or ORIGIN_KEY_PATTERN.fullmatch(key) is None
                or not isinstance(mark, dict) or mark.get('kind') not in ('trade', 'fossil')
                or not isinstance(mark.get('pokemon'), dict)
                or type(mark['pokemon'].get('species_id')) is not int
                or not 1 <= mark['pokemon']['species_id'] <= 1025):
                raise ValueError('Marca de ruta inválida')
        traded = data.setdefault('traded_routes', [])
        if (not isinstance(traded,list) or len(traded)>200 or any(
            not isinstance(route,str) or not route.isdigit() or len(route)>10
            for route in traded)):
            raise ValueError('Rutas intercambiadas inválidas')
        baseline = data.setdefault('full_scan_baseline', {})
        if not isinstance(baseline,dict) or len(baseline)>MAX_ENCOUNTERS or any(
            not isinstance(key,str) or ORIGIN_KEY_PATTERN.fullmatch(key) is None
            or (value is not None and (type(value) is not int or not 0<=value<=0xffffffff))
            for key,value in baseline.items()):
            raise ValueError('Lectura histórica de cajas inválida')
        data.setdefault('revived_pending', [])
        data.setdefault('death_count', len(data['deaths']))
        RunProgress.isolate_level_caps(data)
        result: JSONDict = data
        return result

    @staticmethod
    def isolate_level_caps(data: JSONDict) -> None:
        """A damaged level-caps block never quarantines deaths, encounters or routes.

        It is moved aside unchanged (``level_caps_rejected``) for manual
        inspection and the rest of the history loads normally.
        """
        if 'level_caps' not in data:
            return
        if data['level_caps'] is None:
            del data['level_caps']
            return
        try:
            data['level_caps'] = validated_level_caps(data['level_caps'])
        except (ValueError, TypeError, KeyError, AttributeError):
            data['level_caps_rejected'] = {'rejected_at': datetime.now(timezone.utc).isoformat(),
                                           'data': data.pop('level_caps')}
            data[_LEVEL_CAPS_ISOLATED] = True

    # ---- manual level caps ------------------------------------------------------------------------------------------
    def _level_caps_block(self) -> JSONDict:
        block = self.data.get('level_caps')
        if block is None:
            return {'version': LEVEL_CAPS_VERSION, 'stages': [], 'current': None, 'show': True,
                    'updated_at': None, 'removed_current': None}
        if block.get('version') != LEVEL_CAPS_VERSION:
            raise ValueError('Los límites de nivel de esta partida los creó una versión más nueva del tracker; '
                             'no se modifican aquí.')
        return copy.deepcopy(block)

    def check_level_caps_editable(self) -> None:
        """Raise ValueError when the stored block belongs to a newer tracker (read-only here)."""
        self._level_caps_block()

    def _commit_level_caps(self, before: JSONDict, after: JSONDict) -> bool:
        same = {k: v for k, v in before.items() if k != 'updated_at'} == {k: v for k, v in after.items() if k != 'updated_at'}
        if same and 'level_caps' in self.data:
            return False
        after['updated_at'] = datetime.now(timezone.utc).isoformat()
        self.data['level_caps'] = after
        self.persist()
        return True

    def check_level_caps(self, stages: Any, current: Any = KEEP_CURRENT) -> list[JSONDict]:
        """Validate a full replacement without changing anything; raises ValueError."""
        self._level_caps_block()  # refuses a block written by a newer tracker
        result = normalized_stages(stages, allow_new=True)
        if current is not KEEP_CURRENT and current is not None and current not in {s.get('id') for s in result}:
            raise ValueError('La etapa vigente debe ser una de las etapas existentes de la lista.')
        return result

    def set_level_caps(self, stages: Any, current: Any = KEEP_CURRENT) -> bool:
        """Replace the stage list atomically (order, names, caps, added and removed stages).

        The current stage follows its stable id, not its position. When the
        current stage is removed, there is no current stage afterwards (never a
        neighbour picked silently) and the removed one is kept in
        ``removed_current`` until another stage is chosen.
        """
        before = self._level_caps_block()
        stages = self.check_level_caps(stages, current)
        taken = {s['id'] for s in stages if 'id' in s} | {s['id'] for s in before['stages']}
        if before.get('removed_current'):
            taken.add(before['removed_current']['id'])
        for stage in stages:
            if 'id' not in stage:
                new_id = secrets.token_hex(6)
                while new_id in taken:
                    new_id = secrets.token_hex(6)
                taken.add(new_id)
                stage['id'] = new_id
        stages = [{'id': s['id'], 'name': s['name'], 'cap': s['cap']} for s in stages]
        ids = {s['id'] for s in stages}
        after = copy.deepcopy(before)
        after['stages'] = stages
        previous = before['current']
        if current is KEEP_CURRENT:
            after['current'] = previous if previous in ids else None
        else:
            after['current'] = current
            after['removed_current'] = None
        if previous is not None and previous not in ids:
            old = next(s for s in before['stages'] if s['id'] == previous)
            after['removed_current'] = None if after['current'] is not None else copy.deepcopy(old)
        return self._commit_level_caps(before, after)

    def check_current_stage(self, stage_id: Any) -> None:
        block = self._level_caps_block()
        if stage_id is not None and stage_id not in {s['id'] for s in block['stages']}:
            raise ValueError('Esa etapa no existe en esta partida.')

    def set_current_stage(self, stage_id: Any) -> bool:
        """Choose the current stage by id, or none. Clears the notice of a removed current stage."""
        self.check_current_stage(stage_id)
        before = self._level_caps_block()
        after = copy.deepcopy(before)
        after['current'] = stage_id
        after['removed_current'] = None
        return self._commit_level_caps(before, after)

    def set_level_caps_shown(self, show: Any) -> bool:
        if type(show) is not bool:
            raise ValueError('Opción de mostrar los límites inválida.')
        before = self._level_caps_block()
        after = copy.deepcopy(before)
        after['show'] = show
        return self._commit_level_caps(before, after)

    @staticmethod
    def encounter_record(p: Any) -> JSONDict | None:
        if not isinstance(p, dict) or p.get('checksum_valid') is not True:
            return None
        key = pokemon_key(p)
        if (key is None or ORIGIN_KEY_PATTERN.fullmatch(key) is None or
            type(p.get('species_id')) is not int or not 1 <= p['species_id'] <= 1025
            or type(p.get('met_location_id')) is not int):
            return None
        return {field: copy.deepcopy(p[field]) for field in ENCOUNTER_FIELDS if field in p}

    def remember(self, party: list[Any] | None, boxes: Mapping[str, list[Any]] | None) -> bool:
        """Remember genuine, verified encounters across PC reads and trades.

        A missing Pokémon is not declared traded: the user must confirm that.
        """
        known = self.data['encounters']
        changed = False
        members = [*(party or []), *(p for box in (boxes or {}).values() for p in box)]
        for p in members:
            record = self.encounter_record(p)
            if record is None:
                continue
            key = pokemon_key(p)
            if key not in known and len(known) >= MAX_ENCOUNTERS:
                continue
            if known.get(key) != record:
                known[key] = record
                changed = True
        if changed:
            self.persist()
        return changed

    def observe_full_scan(self, party: Any, boxes: Any, box_count: int = 32) -> bool:
        """Auto-confirm only 1-for-1 trade-like replacements after TWO full verified scans.

        Neither moving to another box nor disappearing from a partial PC scan
        is proof. A different OT on the incoming Pokémon is additional evidence;
        without it, leave a human decision in the route tile.
        """
        if (box_count not in (31,32) or not isinstance(boxes,dict)
            or set(boxes)!={str(i) for i in range(1,box_count+1)}
            or any(not isinstance(v,list) or len(v)!=30 for v in boxes.values())
            or not isinstance(party,list) or len(party)!=6):
            return False
        current: dict[str, int | None] = {}
        for p in [*party,*(mon for box in boxes.values() for mon in box)]:
            rec=self.encounter_record(p)
            if rec is None:
                if p is not None:
                    return False
                continue
            key=pokemon_key(p)
            assert key is not None  # encounter_record() guarantees an identity.
            if key in current and current[key]!=p.get('ot_id'):
                return False
            ot=p.get('ot_id')
            current[key]=ot if type(ot) is int and 0<=ot<=0xffffffff else None
        previous: dict[str, int | None] = self.data.get('full_scan_baseline',{})
        if previous==current:
            return False
        if not previous:
            self.data['full_scan_baseline']=current
            self.persist()
            return False
        removed=set(previous)-set(current)
        arrived=set(current)-set(previous)
        ot_counts=Counter(ot for ot in previous.values() if ot is not None)
        owner=None
        if ot_counts:
            common=ot_counts.most_common(2)
            if common[0][1]>=2 and (len(common)==1 or common[0][1]>common[1][1]):
                owner=common[0][0]
        marked=False
        if len(removed)==1 and len(arrived)==1 and owner is not None:
            gone=next(iter(removed));new=next(iter(arrived))
            # A real trade replaces our Pokémon with one from a different OT.
            if (previous[gone]==owner and current[new] is not None
                and current[new]!=owner and gone not in self.data['deaths']
                and gone not in self.data['route_marks']
                and self.data['origins'].get(gone,'route')=='route'):
                record=self.data['encounters'].get(gone)
                if record:
                    self.mark_route({**record,'checksum_valid':True},'trade',source='auto')
                    # The new Pokémon is the counterpart of the 1-for-1 trade.
                    # Keep its original encounter location but group it as received.
                    incoming=self.data['encounters'].get(new)
                    if incoming:
                        self.set_origin(incoming,'trade')
                    marked=True
        self.data['full_scan_baseline']=current
        self.persist()
        return marked

    def set_traded_route(self, route: str, traded: bool) -> bool:
        routes=set(self.data['traded_routes'])
        prior_misses=list(self.data['missed_routes'])
        if traded:
            routes.add(route)
            # An encounter cannot be both missed and exchanged in the UI.
            self.data['missed_routes']=[r for r in prior_misses if r!=route]
        else:
            routes.discard(route)
        value=sorted(routes,key=int)
        current: list[str] = self.data['traded_routes']
        changed=(value!=current or
                 prior_misses!=self.data['missed_routes'])
        if changed:
            self.data['traded_routes']=value
            self.persist()
        return changed

    def mark_route(self, pokemon: Pokemon, kind: str, source: str = 'manual') -> bool:
        """Mark the route of an OUTGOING trade or a fossil; reversible."""
        if kind not in ('trade','fossil') or source not in ('manual','auto'):
            raise ValueError('Tipo u origen de marca inválido')
        record = self.encounter_record(pokemon)
        if record is None:
            raise ValueError('El Pokémon no tiene una lectura válida')
        key = pokemon_key(pokemon)
        marks = self.data['route_marks']
        value = {'kind': kind, 'pokemon': record, 'source': source,
                 'recorded_at': datetime.now(timezone.utc).isoformat()}
        if key not in marks and len(marks) >= MAX_ENCOUNTERS:
            raise ValueError('El historial de rutas está lleno')
        if marks.get(key, {}).get('kind') == kind:
            return False
        marks[key] = value
        self.persist()
        return True

    def clear_route_mark(self, key: str) -> bool:
        if key not in self.data['route_marks']:
            return False
        del self.data['route_marks'][key]
        self.persist()
        return True

    def observe(self, party: list[Any]) -> bool:
        changed = False
        for p in party:
            if not p or p.get('egg') or p.get('checksum_valid') is not True:
                continue
            key = pokemon_key(p)
            if key is None or key in self.data['deaths']:
                continue
            if key in self.data['revived_pending']:
                # A manual revive must not count the same ongoing faint again.
                if (p.get('hp') or 0) > 0 and (p.get('max_hp') or 0) >= p['hp']:
                    self.data['revived_pending'].remove(key)
                    changed = True
                continue
            if p.get('hp') == 0 and (p.get('max_hp') or 0) > 0:
                self.data['death_count'] += 1
                self.data['deaths'][key] = {
                    'pokemon': copy.deepcopy(p),
                    'recorded_at': datetime.now(timezone.utc).isoformat(),
                }
                changed = True
        if changed:
            self.persist()
        return changed

    def mark_dead(self, pokemon: Pokemon, source: str = 'manual') -> bool:
        """Record a death, distinguishing a partner response from a new loss.

        Soul Link responses still count as deaths, but must not trigger
        reciprocal notifications when the partner fetches this snapshot.
        """
        if source not in ('manual', 'soullink-response'):
            raise ValueError('Origen de muerte inválido')
        key = pokemon_key(pokemon)
        if key is None or key in self.data['deaths']:
            return False
        self.data['death_count'] += 1
        self.data['deaths'][key] = {
            'pokemon': copy.deepcopy(pokemon),
            'recorded_at': datetime.now(timezone.utc).isoformat(),
            'source': source,
        }
        # A manual death overrides any temporary revive safeguard.
        if key in self.data['revived_pending']:
            self.data['revived_pending'].remove(key)
        self.persist()
        return True

    def revive(self, key: str, decrement_counter: bool = False) -> None:
        if key not in self.data['deaths']:
            return
        del self.data['deaths'][key]
        if decrement_counter:
            self.data['death_count'] = max(0, self.data['death_count'] - 1)
        if key not in self.data['revived_pending']:
            self.data['revived_pending'].append(key)
        self.persist()

    def set_origin(self, pokemon: Pokemon, category: str) -> bool:
        """Persistent per-Pokémon classification; 'auto' resets the override."""
        if category != 'auto' and category not in ORIGIN_CATEGORIES:
            raise ValueError('Categoría de obtención inválida')
        key = pokemon_key(pokemon)
        if key is None:
            raise ValueError('Pokémon sin identidad válida')
        overrides = self.data['origins']
        before = overrides.get(key)
        if category == 'auto':
            overrides.pop(key, None)
        else:
            overrides[key] = category
        if before != overrides.get(key):
            self.persist()
            return True
        return False

    def set_miss(self, route: str, missed: bool) -> None:
        routes = set(self.data['missed_routes'])
        if missed:
            routes.add(route)
        else:
            routes.discard(route)
        value = sorted(routes)
        if value != self.data['missed_routes']:
            self.data['missed_routes'] = value
            self.persist()

    def save(self) -> None:
        """Atomic, durable write. Raises OSError; mutators use persist()."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix('.tmp')
        try:
            with open(temporary, 'w', encoding='utf-8') as handle:
                handle.write(json.dumps(self.data, ensure_ascii=False))
                handle.flush()
                os.fsync(handle.fileno())
            if self.disk_verified and self.path.is_file():
                # Best effort: keep the previous good version. A failing
                # backup must not block saving the current history.
                backup_tmp = self.backup_path.with_name(self.backup_path.name + '.tmp')
                try:
                    shutil.copy2(self.path, backup_tmp)
                    os.replace(backup_tmp, self.backup_path)
                except OSError:
                    try:
                        backup_tmp.unlink(missing_ok=True)
                    except OSError:
                        pass
            os.replace(temporary, self.path)
        except BaseException:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            raise
        self.disk_verified = True
        self.dirty = False
        self.last_save_error = None

    def persist(self) -> bool:
        """Save without propagating disk errors.

        The change stays in memory and is marked dirty; flush() (called by
        the service) retries it. Deaths are never counted twice because the
        in-memory record is what later observations compare against.
        """
        try:
            self.save()
            return True
        except OSError as exc:
            self.dirty = True
            self.last_save_error = str(exc)[:200]
            return False

    def flush(self) -> bool:
        """Retry a pending save. Returns True when nothing is left unsaved."""
        if not self.dirty:
            return True
        return self.persist()
