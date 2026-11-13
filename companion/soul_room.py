"""Privacy-first Soul Link rooms, separate from the legacy room protocol."""
from __future__ import annotations

import copy
import hmac
import json
import secrets
import time
from collections.abc import Callable

from .room import MAX_ROOM_BYTES, OFFLINE_SECONDS, Room, digest, member_identity, room_view, sequence
from .room_links import captures, family, links, routes
from .snapshot import JSONDict, shared_state, safe_text

PROTOCOL = 3
FEATURES = ['private-views-v1', 'shared-invite-v1', 'capture-links-v1']
VIEW_SECONDS = 12
MAX_SOUL_BYTES = 32_000


def soul_from_snapshot(state: JSONDict | None, chosen: dict[str, str],
                       previous: JSONDict | None = None) -> JSONDict:
    """Only explicitly linked capture identity and event state leave a private run."""
    result: JSONDict = {'captures': {}, 'missed_routes': []}
    old = (previous or {}).get('captures', {})
    if state is None:
        result['captures'] = {route: copy.deepcopy(old[route]) for route, key in chosen.items()
                              if route in old and old[route]['key'] == key}
        return result
    available = captures(state['game'], state)
    progress = state['progress']
    all_mons = [p for p in state['party'] if p]
    all_mons += [p for box in state['boxes'].values() for p in box if p]
    by_key = {f"{p.get('origin_version', 33)}:{p['encryption_constant']}": p
              for p in all_mons if type(p.get('encryption_constant')) is int}
    by_key.update({key: d['pokemon'] for key, d in progress['deaths'].items()})
    by_key.update({key: d['pokemon'] for key, d in progress['route_marks'].items()})
    canonical = routes(state['game'])
    missed = {f"{family(state['game'])}:{canonical.get(int(r))}" for r in progress['missed_routes'] if r.isdecimal()}
    for route, key in chosen.items():
        if key not in available.get(route, set()):
            if route in old and old[route]['key'] == key:
                result['captures'][route] = {**copy.deepcopy(old[route]), 'status': 'missing',
                                             'death_at': '', 'response': False}
            continue
        mon = by_key[key]
        version, ec = (int(n) for n in key.split(':'))
        minimal = {'species_id': mon['species_id'], 'origin_version': version,
                   'encryption_constant': ec, 'met_location_id': mon['met_location_id']}
        death = progress['deaths'].get(key)
        mark = progress['route_marks'].get(key)
        result['captures'][route] = {'key': key, 'pokemon': minimal,
            'status': 'dead' if death else 'traded' if mark and mark['kind'] == 'trade' else 'alive',
            'death_at': str(death.get('recorded_at', '')) if death else '',
            'response': bool(death and death.get('source') == 'soullink-response')}
        if route in missed:
            result['missed_routes'].append(route)
    return result


def minimal_soul(value: object, game: str, chosen: dict[str, str]) -> JSONDict:
    if not isinstance(value, dict) or len(json.dumps(value, ensure_ascii=False).encode()) > MAX_SOUL_BYTES:
        raise ValueError('Datos Soul Link inválidos o demasiado grandes')
    records, missed = value.get('captures'), value.get('missed_routes')
    if not isinstance(records, dict) or len(records) > 200 or not isinstance(missed, list) or len(missed) > 200:
        raise ValueError('Capturas Soul Link inválidas')
    result: JSONDict = {'captures': {}, 'missed_routes': []}
    versions = {'xy': (24, 25), 'oras': (26, 27), 'alola': (30, 31, 32, 33)}[family(game)]
    for route, record in records.items():
        if not isinstance(record, dict) or route not in chosen or record.get('key') != chosen[route]:
            raise ValueError('Captura no enlazada')
        mon = record.get('pokemon')
        if not isinstance(mon, dict) or any(type(mon.get(k)) is not int for k in
                                          ('species_id', 'origin_version', 'encryption_constant', 'met_location_id')):
            raise ValueError('Identidad de captura inválida')
        if (not 1 <= mon['species_id'] <= (807 if family(game) == 'alola' else 721)
                or mon['origin_version'] not in versions or not 0 <= mon['encryption_constant'] <= 0xffffffff
                or f"{mon['origin_version']}:{mon['encryption_constant']}" != record['key']
                or f"{family(game)}:{routes(game).get(mon['met_location_id'])}" != route
                or record.get('status') not in ('alive', 'dead', 'traded', 'missing')
                or not safe_text(record.get('death_at'), 40) or type(record.get('response')) is not bool):
            raise ValueError('Estado de captura inválido')
        result['captures'][route] = {'key': record['key'], 'pokemon': {k: mon[k] for k in
            ('species_id', 'origin_version', 'encryption_constant', 'met_location_id')},
            'status': record['status'], 'death_at': record['death_at'], 'response': record['response']}
    for route in missed:
        if not isinstance(route, str) or route not in chosen:
            raise ValueError('Ruta no enlazada')
        if route not in result['missed_routes']:
            result['missed_routes'].append(route)
    return result


class SoulRoom(Room):
    def __init__(self, host: JSONDict, clock: Callable[[], float] = time.monotonic) -> None:
        super().__init__(host, 4, clock)
        self.common_invite: str | None = secrets.token_urlsafe(32)
        self.retired: set[str] = set()

    def _add(self, data: JSONDict) -> None:
        super()._add(data)
        self.members[data['player_id']].update(sharing=False, soul={'captures': {}, 'missed_routes': []})

    def invite(self, player_id: str | None = None) -> str:
        if player_id is not None:
            raise ValueError('La reconexión requiere la credencial individual del jugador')
        # Explicit regeneration, never called as a side effect of entry.
        self.common_invite = secrets.token_urlsafe(32)
        return self.common_invite

    def revoke_invites(self) -> None:
        self.common_invite = None

    def join(self, secret: str, data: JSONDict) -> JSONDict:
        if (type(data.get('protocol')) is not int or data['protocol'] != PROTOCOL
                or data.get('features') != FEATURES):
            raise ValueError('Versiones incompatibles; actualiza ambos Trackers')
        if not self.common_invite or not isinstance(secret, str) or not hmac.compare_digest(secret, self.common_invite):
            raise ValueError('La invitación fue revocada o pertenece a otra sala')
        person = member_identity(data)
        if person['player_id'] in self.retired or len(self.retired) >= 4096:
            raise ValueError('Esa identidad ya salió de la sala; entra como una participación nueva')
        if person['player_id'] in self.members:
            raise ValueError('Esta plaza está reservada; usa tu conexión guardada para recuperarla')
        if len(self.members) >= 4:
            raise ValueError('La sala está llena (4/4)')
        self._add(person)
        token = secrets.token_urlsafe(32)
        self.tokens[person['player_id']] = token
        return {'token': token, 'room': self.view()}

    def resume(self, token: str, data: JSONDict) -> JSONDict:
        pid = self.authenticate(token)
        person = member_identity(data)
        member = self.members[pid]
        if (data.get('protocol') != PROTOCOL or data.get('features') != FEATURES
                or any(person[k] != member[k] for k in ('player_id', 'run_id', 'game'))
                or data.get('session_id') != self.session_id or data.get('epoch') != self.epoch):
            raise ValueError('La conexión guardada corresponde a otra partida o sala')
        rotated = secrets.token_urlsafe(32)
        self.tokens[pid] = rotated
        member.update(name=person['name'], sequence=0, sharing=False, state=None, source_live=False)
        self.hashes[pid] = ''
        self.last_seen[pid] = self.clock()
        self._event('reconnected', pid)
        return {'token': rotated, 'room': self.view()}

    def exchange(self, pid: str, data: JSONDict) -> JSONDict:
        if (type(data.get('protocol')) is not int or data['protocol'] != PROTOCOL
                or data.get('session_id') != self.session_id or data.get('epoch') != self.epoch
                or pid not in self.members or data.get('run_id') != self.members[pid]['run_id']):
            raise ValueError('La sesión o partida no coincide')
        member = self.members[pid]
        seq = sequence(data.get('sequence'))
        sharing, live = data.get('sharing'), data.get('source_live')
        if type(sharing) is not bool or type(live) is not bool:
            raise ValueError('Permiso de compartición inválido')
        if not sharing and data.get('state') is not None:
            raise ValueError('Una partida privada no puede enviar su vista completa')
        incoming = copy.deepcopy(shared_state(data.get('state')))
        if incoming is not None and (not live or incoming['game'] != member['game']):
            raise ValueError('La lectura no corresponde a esta partida')
        chosen = links(data.get('links', {}), member['game'])
        soul = minimal_soul(data.get('soul'), member['game'], chosen)
        fingerprint = digest({'state': incoming, 'sharing': sharing, 'source_live': live,
                              'links': chosen, 'soul': soul})
        if seq < member['sequence'] or (seq == member['sequence'] and fingerprint != self.hashes[pid]):
            raise ValueError('Estado antiguo o secuencia reutilizada')
        if seq == member['sequence']:
            return self.view()  # A replay never renews a view lease or presence.
        self.last_seen[pid] = self.clock()
        if seq > member['sequence']:
            before = member['soul']['captures']
            for route, record in soul['captures'].items():
                prior = before.get(route)
                if (prior and prior['key'] == record['key'] and record['status'] == 'dead'
                        and (prior['status'] != 'dead' or prior['death_at'] != record['death_at'])):
                    self._event('death', pid, pokemon_key=record['key'], response=record['response'])
                elif prior and prior['status'] == 'dead' and record['status'] == 'alive':
                    self._event('revived', pid, pokemon_key=record['key'])
            for route, key in chosen.items():
                if member['links'].get(route) != key:
                    self._event('linked', pid, route=route, pokemon_key=key)
            for route in member['links'].keys() - chosen.keys():
                self._event('unlinked', pid, route=route)
            member.update(sequence=seq, sharing=sharing, state=incoming if sharing else None,
                          source_live=live, links=chosen, soul=soul)
            self.hashes[pid] = fingerprint
            self.revision += 1
        return self.view()

    def leave(self, pid: str) -> None:
        if pid == self.host_id or pid not in self.members:
            raise ValueError('Jugador no disponible')
        self._event('left', pid)
        self.tokens.pop(pid, None)
        self.retired.add(pid)
        del self.members[pid]
        self.hashes.pop(pid, None)
        self.last_seen.pop(pid, None)

    def remove(self, pid: str) -> None:
        self.leave(pid)

    def view(self) -> JSONDict:
        now = self.clock()
        members = []
        for pid, member in self.members.items():
            remaining = max(0, int((VIEW_SECONDS - (now - self.last_seen[pid])) * 1000))
            if not remaining or not member['sharing'] or not member['source_live']:
                member['state'] = None
            members.append({**copy.deepcopy(member), 'left': False,
                'online': now - self.last_seen[pid] < OFFLINE_SECONDS,
                'view_ttl_ms': remaining if member['state'] is not None else 0})
        return {'protocol': PROTOCOL, 'features': list(FEATURES), 'session_id': self.session_id,
                'epoch': self.epoch, 'capacity': 4, 'host_id': self.host_id,
                'revision': self.revision, 'members': members, 'events': copy.deepcopy(self.events)}


def soul_view(value: object, *, offline: bool = False) -> JSONDict:
    if not isinstance(value, dict) or value.get('protocol') != PROTOCOL or value.get('features') != FEATURES:
        raise ValueError('Sala Soul Link incompatible; actualiza ambos Trackers')
    if type(value.get('protocol')) is not int or value.get('capacity') != 4:
        raise ValueError('Sala Soul Link inválida')
    if len(json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode()) > MAX_ROOM_BYTES:
        raise ValueError('Sala demasiado grande')
    members = value.get('members')
    if not isinstance(members, list):
        raise ValueError('Participantes inválidos')
    for m in members:
        if not isinstance(m, dict) or type(m.get('sharing')) is not bool:
            raise ValueError('Privacidad inválida')
        ttl = m.get('view_ttl_ms')
        if type(ttl) is not int or not 0 <= ttl <= VIEW_SECONDS * 1000:
            raise ValueError('Vista caducada o inválida')
        if m.get('state') is not None and (not m['sharing'] or not ttl or not m.get('source_live')):
            raise ValueError('No se admite una vista privada o caducada')
    # Reuse the established roster/event/snapshot validators, never accept new
    # arbitrary fields simply because the privacy protocol changed.
    clean = room_view({**value, 'protocol': 2}, offline=offline)
    for original, member in zip(members, clean['members']):
        member.update(sharing=original['sharing'],
                      soul=minimal_soul(original.get('soul'), member['game'], member['links']),
                      view_ttl_ms=0 if offline else original['view_ttl_ms'])
        if offline:
            member['state'] = None
    clean.update(protocol=PROTOCOL, features=list(FEATURES), capacity=4)
    return clean
