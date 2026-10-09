"""Local, durable run annotations; independent of emulator and browser sessions."""
import copy
import json
import os
from datetime import datetime, timezone
from pathlib import Path


ORIGIN_CATEGORIES = ('route', 'fossil', 'gift', 'egg', 'trade')


def origin_category(pokemon, overrides=None):
    """Conservative classification; never infer a fossil/gift from species or location.

    The game preserves the egg acquisition location even after hatching.
    All other mechanisms need an explicit override from the player.
    """
    key = pokemon_key(pokemon)
    chosen = (overrides or {}).get(key)
    if chosen in ORIGIN_CATEGORIES:
        return chosen
    if pokemon.get('egg') is True or (
        type(pokemon.get('egg_location_id')) is int
        and pokemon['egg_location_id'] > 0
    ):
        return 'egg'
    return 'route'


def pokemon_key(p):
    # EC stays unchanged when a Pokémon evolves, is renamed or changes slots.
    ec = p.get('encryption_constant')
    if type(ec) is not int:
        return None
    return f"{p.get('origin_version', 33)}:{ec}"


class RunProgress:
    def __init__(self, path):
        self.path = Path(path)
        self.data = {'deaths': {}, 'missed_routes': [], 'origins': {}}
        if self.path.exists():
            data = json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(data.get('deaths'), dict) or not isinstance(data.get('missed_routes'), list):
                raise ValueError('El registro de la aventura no tiene un formato válido.')
            self.data = data
        origins = self.data.setdefault('origins', {})
        if not isinstance(origins, dict) or any(
            not isinstance(key, str) or len(key) > 64 or
            value not in ORIGIN_CATEGORIES for key, value in origins.items()
        ):
            raise ValueError('Clasificaciones de origen inválidas')
        self.data.setdefault('revived_pending', [])
        self.data.setdefault('death_count', len(self.data['deaths']))

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
                self.data['death_count'] += 1
                self.data['deaths'][key] = {
                    'pokemon': copy.deepcopy(p),
                    'recorded_at': datetime.now(timezone.utc).isoformat(),
                }
                changed = True
        if changed:
            self.save()
        return changed

    def mark_dead(self, pokemon, source='manual'):
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
        self.save()
        return True

    def revive(self, key, decrement_counter=False):
        if key not in self.data['deaths']:
            return
        del self.data['deaths'][key]
        if decrement_counter:
            self.data['death_count'] = max(0, self.data['death_count'] - 1)
        if key not in self.data['revived_pending']:
            self.data['revived_pending'].append(key)
        self.save()

    def set_origin(self, pokemon, category):
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
            self.save()
            return True
        return False

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
