"""Local, durable run annotations; independent of emulator and browser sessions."""
import copy
import json
import os
from datetime import datetime, timezone
from pathlib import Path


def pokemon_key(p):
    # EC stays unchanged when a Pokémon evolves, is renamed or changes slots.
    ec = p.get('encryption_constant')
    if type(ec) is not int:
        return None
    return f"{p.get('origin_version', 33)}:{ec}"


class RunProgress:
    def __init__(self, path):
        self.path = Path(path)
        self.data = {'deaths': {}, 'missed_routes': []}
        if self.path.exists():
            data = json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(data.get('deaths'), dict) or not isinstance(data.get('missed_routes'), list):
                raise ValueError('El registro de la aventura no tiene un formato válido.')
            self.data = data
        self.data.setdefault('revived_pending', [])

    def observe(self, party):
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
                self.data['deaths'][key] = {
                    'pokemon': copy.deepcopy(p),
                    'recorded_at': datetime.now(timezone.utc).isoformat(),
                }
                changed = True
        if changed:
            self.save()
        return changed

    def revive(self, key):
        if key not in self.data['deaths']:
            return
        del self.data['deaths'][key]
        if key not in self.data['revived_pending']:
            self.data['revived_pending'].append(key)
        self.save()

    def set_miss(self, route, missed):
        routes = set(self.data['missed_routes'])
        if missed:
            routes.add(route)
        else:
            routes.discard(route)
        value = sorted(routes)
        if value != self.data['missed_routes']:
            self.data['missed_routes'] = value
            self.save()

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix('.tmp')
        temporary.write_text(json.dumps(self.data, ensure_ascii=False), encoding='utf-8')
        os.replace(temporary, self.path)
