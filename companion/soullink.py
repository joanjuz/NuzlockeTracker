"""Opt-in, local-only Soul Link death suggestions.

A remote death never edits the local party automatically. Seen events and
unresolved suggestions survive a restart without syncing a new cloud schema.
"""
from __future__ import annotations
import hashlib
import json
import os
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from tracker.progress import pokemon_key


def route_name(value):
    text = unicodedata.normalize('NFKD', str(value or '').casefold())
    return ' '.join(''.join(c for c in text if not unicodedata.combining(c)).split())


def same_route(source, target):
    """Require a real encounter location; no species/slot-only false links."""
    if not isinstance(source, dict) or not isinstance(target, dict):
        return False
    a, b = source.get('met_location_id'), target.get('met_location_id')
    if type(a) is int and type(b) is int and a > 0 and a == b:
        return True
    a_name, b_name = route_name(source.get('met_location')), route_name(target.get('met_location'))
    return bool(a_name and b_name and
                a_name not in ('desconocido', 'sin lugar registrado') and
                a_name == b_name)


def event_identifier(key, record):
    raw = json.dumps([key, record.get('recorded_at', '')], ensure_ascii=False)
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()[:24]


class SoulLinkEvents:
    def __init__(self, path):
        self.path = Path(path)
        self.pair_id = None
        self.enabled = False
        self.initialized = False
        self.seen = []
        self.pending = []
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding='utf-8'))
                if isinstance(data, dict):
                    self.pair_id = data.get('pair_id')
                    self.enabled = data.get('enabled') is True
                    self.initialized = data.get('initialized') is True
                    self.seen = [x for x in data.get('seen', []) if isinstance(x, str)][:1500]
                    self.pending = [e for e in data.get('pending', []) if isinstance(e, dict) and
                                    isinstance(e.get('id'), str)][:40]
            except (ValueError, OSError, TypeError):
                pass

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {'schema_version':1, 'pair_id':self.pair_id, 'enabled':self.enabled,
                'initialized':self.initialized, 'seen':self.seen[-1500:],
                'pending':self.pending[-40:]}
        tmp = self.path.with_suffix('.tmp')
        tmp.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
        os.replace(tmp, self.path)

    def set_pair(self, pair_id):
        if pair_id != self.pair_id:
            self.pair_id = pair_id
            self.initialized = False
            self.seen = []
            self.pending = []
            self.save()

    def enable(self, value, remote=None):
        if type(value) is not bool:
            raise ValueError('El interruptor Soul Link debe activarse o desactivarse')
        self.enabled = value
        # Enabling must not reopen old deaths as unsolicited notifications.
        if value and remote is not None:
            self.seed(remote)
        self.save()

    @staticmethod
    def records(remote):
        state = remote.get('state') if isinstance(remote, dict) else None
        deaths = (state.get('progress') or {}).get('deaths', {}) if isinstance(state, dict) else {}
        if not isinstance(deaths, dict):
            return {}
        return {event_identifier(key, value):value for key,value in deaths.items()
                if isinstance(key, str) and isinstance(value, dict) and
                isinstance(value.get('pokemon'), dict)}

    def seed(self, remote):
        records = self.records(remote)
        self.seen = list(dict.fromkeys([*self.seen, *records]))[-1500:]
        self.initialized = True
        self.save()

    def observe(self, remote):
        if not self.enabled:
            return
        records = self.records(remote)
        if not self.initialized:
            self.seed(remote)
            return
        known = set(self.seen)
        changed = False
        for identifier, record in records.items():
            if identifier in known:
                continue
            mon = record['pokemon']
            self.seen.append(identifier)
            known.add(identifier)
            if len(self.pending) < 40:
                self.pending.append({
                    'id':identifier,
                    'pokemon':{k:mon.get(k) for k in ('species_id','species','nickname','met_location',
                             'met_location_id','origin_version')},
                    'recorded_at':str(record.get('recorded_at') or '')[:40],
                    'received_at':datetime.now(timezone.utc).isoformat()
                })
            changed = True
        if changed:
            self.seen = self.seen[-1500:]
            self.save()

    @staticmethod
    def choices(source, state):
        if not isinstance(state, dict):
            return []
        raw = [*state.get('party', []), *(p for box in (state.get('boxes') or {}).values() for p in box)]
        unique = set()
        matches = []
        for p in raw:
            if not p or p.get('egg') or p.get('checksum_valid') is not True:
                continue
            key = pokemon_key(p)
            if key is None or key in unique:
                continue
            unique.add(key)
            if same_route(source, p):
                matches.append({'key':key,'species_id':p.get('species_id'),
                                'name':p.get('nickname') or p.get('species') or 'Pokémon',
                                'route':p.get('met_location') or 'Ruta registrada',
                                'already_dead':key in (state.get('progress') or {}).get('deaths', {})})
        matches.sort(key=lambda p: (p['already_dead'],p['name']))
        return matches

    def status(self, state):
        if not self.enabled:
            return []
        return [{**event, 'choices':self.choices(event['pokemon'], state)}
                for event in self.pending[:12]]

    def decide(self, event_id, decision, candidate_key, service):
        if not self.enabled or decision not in ('mark','ignore'):
            raise ValueError('Soul Link no está activo o decisión inválida')
        event = next((x for x in self.pending if x.get('id') == event_id), None)
        if event is None:
            raise ValueError('Ese aviso ya se resolvió')
        if decision == 'mark':
            choices = self.choices(event['pokemon'], service.snapshot())
            if not any(c['key'] == candidate_key and not c['already_dead'] for c in choices):
                raise ValueError('Selecciona un Pokémon vivo capturado en la misma ruta')
            service.mark_dead({'key':candidate_key})
        self.pending = [x for x in self.pending if x['id'] != event_id]
        self.save()
