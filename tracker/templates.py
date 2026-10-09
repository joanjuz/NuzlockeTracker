"""Read-only pk3DS Progressive CSV templates. No ROM or save file is modified."""
import csv
import io
import json
import os
import unicodedata
from pathlib import Path

from .catalog import Catalog

MAX_FILE_SIZE = 180_000
TYPES = dict(zip(
    'Normal Fire Water Electric Grass Ice Fighting Poison Ground Flying Psychic Bug Rock Ghost Dragon Dark Steel Fairy'.split(),
    'Normal Fuego Agua Eléctrico Planta Hielo Lucha Veneno Tierra Volador Psíquico Bicho Roca Fantasma Dragón Siniestro Acero Hada'.split()
))
CATEGORIES = {'Physical': 'Físico', 'Special': 'Especial', 'Status': 'Estado',
              'Físico': 'Físico', 'Especial': 'Especial', 'Estado': 'Estado'}


def normalize(name):
    return ''.join(c for c in unicodedata.normalize('NFKD', name.casefold()) if not unicodedata.combining(c)).replace(' ', '').replace('-', '').replace("'", '')


def rows(text, required):
    if not isinstance(text, str) or len(text.encode('utf-8')) > MAX_FILE_SIZE:
        raise ValueError('La plantilla supera el límite permitido (180 KB).')
    # pk3DS balance templates include comments, blank rows, and extra columns.
    filtered = '\n'.join(line for line in text.lstrip('\ufeff').splitlines()
                         if line.strip() and not line.lstrip().startswith('#'))
    reader = csv.DictReader(io.StringIO(filtered), restkey='_extra')
    if not reader.fieldnames or not set(required).issubset(reader.fieldnames):
        raise ValueError('Columnas incorrectas; se requiere plantilla CSV pk3DS de ' + ', '.join(required))
    for n, entry in enumerate(reader, 2):
        if n > 5000:
            raise ValueError('Demasiadas filas en la plantilla.')
        if not any(str(v or '').strip() for k, v in entry.items() if k and k != '_extra'):
            continue
        yield {k: str(v or '').strip() for k, v in entry.items() if k and k != '_extra'}


def number(value, low, high, field):
    try:
        result = int(value)
    except (TypeError, ValueError):
        raise ValueError(f'{field} debe ser numérico: {value!r}') from None
    if not low <= result <= high:
        raise ValueError(f'{field} fuera de rango: {result}')
    return result


def moves_csv(text):
    output = {}
    keys = {'Power': ('power', 0, 255), 'Accuracy': ('accuracy', 0, 100),
            'PP': ('pp', 1, 64), 'Priority': ('priority', -7, 7)}
    for entry in rows(text, {'Move', 'Power', 'PP'}):
        if not entry.get('Move'):
            continue
        id = number(entry['Move'], 1, 728, 'Move')
        changes = {}
        for col, (dest, lo, hi) in keys.items():
            if entry.get(col):
                changes[dest] = number(entry[col], lo, hi, col)
        if entry.get('Type'):
            if entry['Type'] not in TYPES and entry['Type'] not in TYPES.values():
                raise ValueError('Tipo desconocido: ' + entry['Type'])
            changes['type'] = TYPES.get(entry['Type'], entry['Type'])
        if entry.get('Category'):
            if entry['Category'] not in CATEGORIES:
                raise ValueError('Categoría desconocida: ' + entry['Category'])
            changes['category'] = CATEGORIES[entry['Category']]
        # Advanced CSV-only/ Battle.cro fields are documentation, not simulated game behavior.
        if entry.get('Notes'):
            changes['template_notes'] = entry['Notes'][:300]
        if entry.get('BattlePatch'):
            changes['battle_patch'] = entry['BattlePatch'][:80]
        if changes:
            output[str(id)] = changes
    return output


def stats_csv(text, catalog):
    result = {}
    known = {normalize(catalog.name('species', id)): id for id in range(1, 808)}
    for row in rows(text, {'Entry', 'Pokemon', 'HP', 'ATK', 'DEF', 'SPA', 'SPD', 'SPE'}):
        if not row.get('Entry') and not row.get('Pokemon'):
            continue
        id = (number(row['Entry'], 1, 807, 'Entry') if row.get('Entry') else
              known.get(normalize(row['Pokemon'])))
        if not id:
            raise ValueError('Pokémon desconocido en estadísticas: ' + row.get('Pokemon', ''))
        stats = {name: number(row[name], 1, 255, name) for name in ('HP', 'ATK', 'DEF', 'SPA', 'SPD', 'SPE') if row.get(name)}
        if stats:
            result[str(id)] = stats
    return result


def evolutions_csv(text):
    result = {}
    for row in rows(text, {'Source', 'Target', 'Method', 'Level', 'Argument', 'Form'}):
        if not row.get('Source'):
            continue
        source = number(row['Source'], 1, 807, 'Source')
        target = number(row['Target'], 1, 807, 'Target')
        form = number(row.get('Form') or '-1', -1, 255, 'Form')
        level = number(row['Level'], 1, 100, 'Level') if row.get('Level') else None
        method = row.get('Method')
        if not method or len(method) > 60:
            raise ValueError('Method es obligatorio y debe ser breve.')
        argument = row.get('Argument', '')
        if argument:
            number(argument, 0, 65535, 'Argument')
        item = (row.get('AltItemName') or row.get('ItemName') or '')[:70]
        if method.casefold() == 'level':
            description = 'Subir de nivel' + (f' al nivel {level}' if level else '')
        elif method.casefold() == 'useditem':
            description = 'Usar ' + (item or 'objeto ID ' + argument)
        elif method in ('19', '20'):
            # Verified against pk3DS EvolutionEditor7 evolutionMethods (0-based).
            # 19: Level Up with Held Item (Day); 20: (...) (Night).
            moment = 'de día' if method == '19' else 'de noche'
            description = 'Subir de nivel ' + moment + ' llevando ' + (item or 'objeto ID ' + argument)
        else:
            description = 'Método pk3DS ' + method + (f' · {item}' if item else
                                                       f' · argumento {argument}' if argument else '')
            if level:
                description += f' · nivel {level}'
        entry = {'target': target, 'method': description, 'raw_method': method,
                 'form': form, 'source': 'pk3DS Progressive'}
        if item:
            entry['item'] = item
        result.setdefault(str(source), []).append(entry)
    return result


class TemplateManager:
    """Atomic validation, per-profile persistence, and evolution overlays."""
    def __init__(self, path, catalog=None):
        self.path = Path(path)
        self.catalog = catalog or Catalog()
        self.baseline = json.loads((Path(__file__).resolve().parent.parent/'data'/'Evolutions_Reference_Gen7.json').read_text(encoding='utf-8'))['evolutions']
        self.data = {'moves': {}, 'stats': {}, 'evolutions': {}}
        if self.path.is_file():
            try:
                saved = json.loads(self.path.read_text(encoding='utf-8'))
                if saved.get('schema_version') == 1 and all(isinstance(saved.get(k), dict) for k in self.data):
                    self.data = {k: saved[k] for k in self.data}
            except (ValueError, OSError, AttributeError):
                pass

    def status(self):
        return {'counts': {key: len(value) for key, value in self.data.items()},
                'loaded': any(self.data.values())}

    def import_csv(self, content):
        if not isinstance(content, dict) or not content or not set(content).issubset({'moves', 'stats', 'evolutions'}):
            raise ValueError('Selecciona una o más plantillas compatibles.')
        parsed = {}
        for section, text in content.items():
            parsed[section] = {'moves': moves_csv, 'stats': lambda x: stats_csv(x, self.catalog),
                               'evolutions': evolutions_csv}[section](text)
        updated = dict(self.data)
        updated.update(parsed)
        raw = json.dumps({'schema_version': 1, **updated}, ensure_ascii=False, separators=(',', ':'))
        if len(raw.encode('utf-8')) > 320_000:
            raise ValueError('Las plantillas importadas superan el límite combinado.')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix('.tmp')
        tmp.write_text(raw, encoding='utf-8')
        os.replace(tmp, self.path)
        self.data = updated
        return self.status()

    def evolutions(self, species, form=0):
        source = str(species)
        original = list(self.baseline.get(source, []))
        entries = self.data['evolutions'].get(source, [])
        by_target = {}
        # Use form-specific rows if present for the same target, otherwise generic.
        for row in entries:
            if row['form'] not in (-1, form):
                continue
            target = row['target']
            by_target.setdefault(target, []).append(row)
        if not by_target:
            return original
        new = [e for e in original if e['target'] not in by_target]
        for variants in by_target.values():
            chosen = [v for v in variants if v['form'] == form] or [v for v in variants if v['form'] == -1]
            new.extend({'target': v['target'], 'method': v['method'], 'source': 'pk3DS Progressive'} for v in chosen)
        return new
