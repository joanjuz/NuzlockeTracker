"""Bounded, transport-independent Soul Link room state. Never writes a local run.

Credentials live only in memory. Callers serialize access with their host lock.
Snapshots remain subject to the existing companion allowlist.
"""
from __future__ import annotations

import copy
import hashlib
import hmac
import json
import secrets
import time
import uuid
from collections.abc import Callable
from typing import Any

from .room_links import captures, links
from .snapshot import JSONDict, SUPPORTED_GAMES, safe_text, shared_state

PROTOCOL = 2
MAX_SEQUENCE = 2 ** 53 - 1
INVITE_SECONDS = 600
OFFLINE_SECONDS = 20
MAX_EVENTS = 100
MAX_ROOM_BYTES = 2_800_000


def identifier(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError('Identidad inválida')
    try:
        if str(uuid.UUID(value)) != value:
            raise ValueError()
    except (ValueError, AttributeError):
        raise ValueError('Identidad inválida') from None
    return value


def member_identity(data: JSONDict) -> JSONDict:
    name, game = data.get('name'), data.get('game')
    if (not isinstance(name, str) or not 1 <= len(name.strip()) <= 32
            or any(ord(c) < 32 or c in '<>' for c in name)
            or not isinstance(game, str) or game not in SUPPORTED_GAMES):
        raise ValueError('Jugador o juego inválido')
    return {'player_id': identifier(data.get('player_id')),
            'run_id': identifier(data.get('run_id')), 'name': name.strip(), 'game': game}


def sequence(value: object) -> int:
    if type(value) is not int or not 0 <= value <= MAX_SEQUENCE:
        raise ValueError('Secuencia inválida')
    return value


def digest(state: JSONDict | None) -> str:
    return hashlib.sha256(json.dumps(state, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=False).encode('utf-8')).hexdigest()


class Room:
    def __init__(self, host: JSONDict, capacity: int,
                 clock: Callable[[], float] = time.monotonic) -> None:
        if type(capacity) is not int or capacity not in (2, 3, 4):
            raise ValueError('La sala admite 2, 3 o 4 jugadores')
        host = member_identity(host)
        self.clock = clock
        self.session_id = str(uuid.uuid4())
        self.epoch = str(uuid.uuid4())
        self.capacity = capacity
        self.host_id = host['player_id']
        self.members: dict[str, JSONDict] = {}
        self.tokens: dict[str, str] = {}
        self.invites: dict[str, tuple[float, str | None]] = {}
        self.last_seen: dict[str, float] = {}
        self.hashes: dict[str, str] = {}
        self.events: list[JSONDict] = []
        self.revision = 0
        self._add(host)

    def _add(self, data: JSONDict) -> None:
        pid = data['player_id']
        self.members[pid] = {**data, 'sequence': 0, 'state': None,
                             'source_live': False, 'left': False, 'links': {}}
        self.last_seen[pid] = self.clock()
        self.hashes[pid] = digest({'state': None, 'links': self.members[pid]['links']})
        self._event('joined', pid)

    def _event(self, kind: str, player_id: str, **extra: Any) -> None:
        self.revision += 1
        self.events.append({'id': self.revision, 'kind': kind, 'player_id': player_id,
                            'run_id': self.members[player_id]['run_id'], **extra})
        self.events = self.events[-MAX_EVENTS:]

    def invite(self, player_id: str | None = None) -> str:
        """A new invitation revokes earlier unused invitations (at most one)."""
        if player_id is not None:
            if player_id == self.host_id or player_id not in self.members:
                raise ValueError('Jugador no disponible')
        elif len(self.members) >= self.capacity:
            raise ValueError('Sala completa; elimina una plaza para invitar')
        token = secrets.token_urlsafe(32)
        self.invites = {token: (self.clock() + INVITE_SECONDS, player_id)}
        return token

    def revoke_invites(self) -> None:
        self.invites.clear()

    def join(self, secret: str, data: JSONDict) -> JSONDict:
        if type(data.get('protocol')) is not int or data['protocol'] != PROTOCOL:
            raise ValueError('Protocolo de sala incompatible')
        invitation = next((v for k, v in self.invites.items()
                           if hmac.compare_digest(k, secret)), None)
        if invitation is None or self.clock() >= invitation[0]:
            raise ValueError('Invitación inválida o caducada')
        person = member_identity(data)
        pid = person['player_id']
        target = invitation[1]
        if target is None:
            if pid in self.members or len(self.members) >= self.capacity:
                raise ValueError('Identidad duplicada o sala completa')
        elif (pid != target or person['run_id'] != self.members[target]['run_id']
              or person['game'] != self.members[target]['game']):
            raise ValueError('La invitación corresponde a otra partida')
        token = secrets.token_urlsafe(32)
        if target is None:
            self._add(person)
        else:
            self.members[pid].update(name=person['name'], sequence=0, left=False)
            self.hashes[pid] = digest({'state': None, 'links': self.members[pid]['links']})
            self.last_seen[pid] = self.clock()
            self._event('reconnected', pid)
        self.tokens[pid] = token
        self.invites.clear()
        return {'token': token, 'room': self.view()}

    def authenticate(self, secret: str) -> str:
        for pid, token in self.tokens.items():
            if hmac.compare_digest(token, secret):
                return pid
        raise ValueError('Sesión inválida o revocada')

    def exchange(self, pid: str, data: JSONDict) -> JSONDict:
        if (data.get('protocol') != PROTOCOL or type(data.get('protocol')) is not int
                or data.get('session_id') != self.session_id or data.get('epoch') != self.epoch
                or pid not in self.members or self.members[pid]['left']
                or data.get('run_id') != self.members[pid]['run_id']):
            raise ValueError('La sesión o partida no coincide')
        seq = sequence(data.get('sequence'))
        incoming = copy.deepcopy(shared_state(data.get('state')))
        member = self.members[pid]
        if incoming is not None and incoming['game'] != member['game']:
            raise ValueError('Juego incompatible con la partida')
        chosen = links(data.get('links', member['links']), member['game'])
        available = captures(member['game'], incoming if incoming is not None else member['state'])
        for route, key in chosen.items():
            if member['links'].get(route) != key and key not in available.get(route, set()):
                raise ValueError('Elige una captura de tu propia partida y ruta')
        incoming_hash = digest({'state': incoming, 'links': chosen})
        previous = member['sequence']
        if seq < previous or (seq == previous and incoming_hash != self.hashes[pid]):
            raise ValueError('Estado antiguo o secuencia reutilizada')
        self.last_seen[pid] = self.clock()
        if seq > previous:
            if incoming is not None:
                old = member['state']
                if old is not None:
                    before = old['progress']['deaths']
                    after = incoming['progress']['deaths']
                    for key, death in after.items():
                        if key not in before or before[key] != death:
                            self._event('death', pid, pokemon_key=key,
                                        response=death.get('source') == 'soullink-response')
                    for key in before.keys() - after.keys():
                        self._event('revived', pid, pokemon_key=key)
                    for route in set(incoming['progress']['missed_routes']) - set(old['progress']['missed_routes']):
                        self._event('missed', pid, route=route)
                member['state'] = incoming
            for route, key in chosen.items():
                if member['links'].get(route) != key:
                    self._event('linked', pid, route=route, pokemon_key=key)
            for route in member['links'].keys() - chosen.keys():
                self._event('unlinked', pid, route=route)
            member.update(sequence=seq, source_live=incoming is not None, links=chosen)
            self.hashes[pid] = incoming_hash
            self.revision += 1
        return self.view()

    def leave(self, pid: str) -> None:
        if pid == self.host_id or pid not in self.members:
            raise ValueError('Jugador no disponible')
        self.tokens.pop(pid, None)
        self.members[pid].update(left=True, source_live=False)
        self._event('left', pid)

    def remove(self, pid: str) -> None:
        """Explicit host action; freed slots never inherit the previous identity."""
        self.leave(pid)
        del self.members[pid]
        self.last_seen.pop(pid, None)
        self.hashes.pop(pid, None)
        self.revoke_invites()

    def view(self) -> JSONDict:
        now = self.clock()
        members = [{**copy.deepcopy(member),
                    'online': not member['left'] and now - self.last_seen[pid] < OFFLINE_SECONDS}
                   for pid, member in self.members.items()]
        return {'protocol': PROTOCOL, 'features': ['capture-links-v1'], 'session_id': self.session_id, 'epoch': self.epoch,
                'capacity': self.capacity, 'host_id': self.host_id, 'revision': self.revision,
                'members': members, 'events': copy.deepcopy(self.events)}


def room_view(value: object, *, offline: bool = False) -> JSONDict:
    """Validate untrusted aggregate replies and offline caches; drop unknown fields."""
    if not isinstance(value, dict) or len(json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode()) > MAX_ROOM_BYTES:
        raise ValueError('Sala inválida o demasiado grande')
    if type(value.get('protocol')) is not int or value['protocol'] != PROTOCOL:
        raise ValueError('Protocolo de sala incompatible')
    capacity = value.get('capacity')
    members = value.get('members')
    if type(capacity) is not int or capacity not in (2, 3, 4) or not isinstance(members, list) or not 1 <= len(members) <= capacity:
        raise ValueError('Número de jugadores inválido')
    result: JSONDict = {'protocol': PROTOCOL, 'session_id': identifier(value.get('session_id')),
                       'epoch': identifier(value.get('epoch')), 'capacity': capacity,
                       'host_id': identifier(value.get('host_id')), 'revision': sequence(value.get('revision'))}
    clean = []
    ids = set()
    for member in members:
        if not isinstance(member, dict):
            raise ValueError('Jugador inválido')
        person = member_identity(member)
        if person['player_id'] in ids:
            raise ValueError('Jugador duplicado')
        ids.add(person['player_id'])
        state = shared_state(member.get('state'))
        if state is not None and state['game'] != person['game']:
            raise ValueError('Juego incompatible')
        flags = {}
        for name in ('source_live', 'left', 'online'):
            if type(member.get(name)) is not bool:
                raise ValueError('Estado de conexión inválido')
            flags[name] = False if offline and name != 'left' else member[name]
        clean.append({**person, **flags, 'sequence': sequence(member.get('sequence')), 'state': state,
                      'links': links(member.get('links', {}), person['game'])})
    if result['host_id'] not in ids:
        raise ValueError('Anfitrión ausente')
    events = value.get('events')
    if not isinstance(events, list) or len(events) > MAX_EVENTS:
        raise ValueError('Historial inválido')
    cleaned_events = []
    last = 0
    for event in events:
        if not isinstance(event, dict) or event.get('kind') not in ('joined', 'reconnected', 'left', 'death', 'revived', 'missed', 'linked', 'unlinked'):
            raise ValueError('Evento inválido')
        eid = sequence(event.get('id'))
        if not last < eid <= result['revision']:
            raise ValueError('Orden de eventos inválido')
        last = eid
        item = {'id': eid, 'kind': event['kind'], 'player_id': identifier(event.get('player_id')),
                'run_id': identifier(event.get('run_id'))}
        if event['kind'] in ('death', 'revived', 'linked'):
            key = event.get('pokemon_key')
            if not safe_text(key, 70):
                raise ValueError('Pokémon inválido')
            item['pokemon_key'] = key
            if event['kind'] == 'death':
                if type(event.get('response')) is not bool:
                    raise ValueError('Evento inválido')
                item['response'] = event['response']
        if event['kind'] in ('missed', 'linked', 'unlinked'):
            route = event.get('route')
            if not safe_text(route, 20):
                raise ValueError('Ruta inválida')
            item['route'] = route
        cleaned_events.append(item)
    features = value.get('features', [])
    if not isinstance(features, list) or len(features) > 8 or any(not safe_text(f, 40) for f in features):
        raise ValueError('Capacidades de sala inválidas')
    return {**result, 'members': clean, 'events': cleaned_events,
            'features': [f for f in features if f == 'capture-links-v1']}
