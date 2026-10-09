"""Read-only pk3DS Progressive CSV templates. No ROM or save file is modified."""
import csv
import io
import json
import os
import re
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


# USUM items are already translated in data/Items.txt. These aliases cover
# PokeAPI's English reference descriptions and user-entered CSV labels.
ITEM_NAMES = {
    'fire stone': 'Piedra fuego', 'water stone': 'Piedra agua',
    'thunder stone': 'Piedra trueno', 'leaf stone': 'Piedra hoja',
    'ice stone': 'Piedra hielo', 'moon stone': 'Piedra lunar',
    'sun stone': 'Piedra solar', 'dusk stone': 'Piedra noche',
    'dawn stone': 'Piedra alba', 'shiny stone': 'Piedra día',
    'kings rock': 'Roca del Rey', "king's rock": 'Roca del Rey',
    'reaper cloth': 'Tela Terrible', 'metal coat': 'Revestimiento Metálico',
    'prism scale': 'Escama Bella', 'deep sea scale': 'Escama Marina',
    'deep sea tooth': 'Diente Marino', 'protector': 'Protector',
    'electirizer': 'Electrizador', 'magmarizer': 'Magmatizador',
    'dubious disc': 'Disco Extraño', 'upgrade': 'Mejora',
    'razor fang': 'Colmillo Agudo', 'razor claw': 'Garra Afilada',
    'oval stone': 'Piedra Oval', 'whipped dream': 'Dulce de Nata',
    'sachet': 'Saquito Fragante', 'dragon scale': 'Escama Dragón',
    'water stone ': 'Piedra agua',
}

# The Gen7 pk3DS editor uses indexes (NOT PokeAPI evolution trigger IDs).
EVOLUTION_METHODS = {
    '1': 'Subir de nivel con amistad alta',
    '2': 'Subir de nivel de día con amistad alta',
    '3': 'Subir de nivel de noche con amistad alta',
    '4': 'Subir de nivel',
    '5': 'Intercambiar',
    '6': 'Intercambiar llevando',
    '7': 'Intercambio especial',
    '8': 'Usar',
    '9': 'Subir de nivel con Ataque mayor que Defensa',
    '10': 'Subir de nivel con Ataque igual a Defensa',
    '11': 'Subir de nivel con Ataque menor que Defensa',
    '16': 'Subir de nivel con belleza alta',
    '17': 'Usar objeto (macho)',
    '18': 'Usar objeto (hembra)',
    '19': 'Subir de nivel de día llevando',
    '20': 'Subir de nivel de noche llevando',
    '21': 'Subir de nivel con movimiento conocido',
    '22': 'Subir de nivel con Pokémon específico en el equipo',
    '23': 'Subir de nivel (macho)', '24': 'Subir de nivel (hembra)',
    '25': 'Subir de nivel en zona eléctrica',
    '26': 'Subir de nivel en bosque especial',
    '27': 'Subir de nivel en zona fría',
    '28': 'Subir de nivel con consola invertida',
    '31': 'Subir de nivel con lluvia',
    '32': 'Subir de nivel por la mañana',
    '33': 'Subir de nivel por la noche',
    '40': 'Subir de nivel al atardecer',
    '41': 'Subir de nivel en el Ultraumbral',
    '42': 'Usar objeto en el Ultraumbral',
}


def spanish_item(name):
    if not name:
        return ''
    text = name.replace('_', ' ').replace('-', ' ').strip()
    return ITEM_NAMES.get(text.casefold(), text)


def argument_item(row, catalog):
    """Resolve object numeric ID against USUM (not a PokeAPI item index)."""
    ident = row.get('Argument', '')
    try:
        key = int(ident)
        if 1 <= key <= 959:
            name = catalog.name('items', key)
            if not name.startswith('ID '):
                return name
    except (TypeError, ValueError):
        pass
    return spanish_item(row.get('AltItemName') or row.get('ItemName') or '')


def pretty_reference(method):
    """Translate the PokeAPI reference without leaking internal IDs."""
    parts = method.split(' · ', 1)
    trigger = parts[0]
    info = parts[1] if len(parts) > 1 else ''
    props = {}
    for part in info.split('; '):
        if ': ' in part:
            k, v = part.split(': ', 1)
            props[k] = v
    item_used = spanish_item(props.get('Objeto usado', ''))
    item_held = spanish_item(props.get('Objeto equipado', ''))
    if item_used:
        result = 'Usar ' + item_used.lower() if item_used.lower().startswith('piedra ') else 'Usar ' + item_used
    elif trigger.startswith('Subir de nivel'):
        result = trigger
    elif trigger == 'Intercambio':
        result = 'Intercambiar'
    else:
        result = trigger
    if item_held:
        result += ' llevando ' + item_held
    notes = []
    fields = {
        'Momento': 'de día/noche', 'Amistad mínima': 'amistad mínima',
        'Lugar (ID)': 'lugar especial', 'Movimiento conocido (ID)': 'movimiento específico',
        'Género': 'sexo requerido', 'Belleza mínima': 'belleza mínima',
        'Afecto mínimo': 'afecto mínimo', 'Con lluvia': 'lluvia',
    }
    for key, desc in fields.items():
        if key in props:
            value = props[key]
            notes.append(desc + (f' ({value})' if value.isdigit() and key not in ('Lugar (ID)', 'Movimiento conocido (ID)') else ''))
    if notes:
        result += ' · ' + ', '.join(notes)
    return result


def evolution_form(row):
    """Form in pk3DS EvolutionSet7 denotes the RESULT, -1 inherits source."""
    return row['form'] if row['form'] >= 0 else None

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


def evolutions_csv(text, catalog=None):
    catalog = catalog or Catalog()
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
        item = argument_item(row, catalog)
        normalized = method.casefold()
        if normalized in ('level', '4'):
            description = 'Subir de nivel' + (f' al nivel {level}' if level else
                                               f' al nivel {argument}' if argument else '')
        elif normalized in ('useditem', '8'):
            description = 'Usar ' + (item.lower() if item.lower().startswith('piedra ') else item or 'un objeto especial')
        elif method in ('19', '20'):
            moment = 'de día' if method == '19' else 'de noche'
            description = 'Subir de nivel ' + moment + ' llevando ' + (item or 'un objeto especial')
        else:
            base = EVOLUTION_METHODS.get(method)
            if base:
                description = base
                if method in ('6', '17', '18', '42') and item:
                    description += ' ' + item
                if level and method not in ('6', '17', '18', '42'):
                    description += f' al nivel {level}'
            else:
                description = 'Método especial pk3DS ' + method
                if level:
                    description += f' · nivel {level}'
                if item:
                    description += ' · ' + item
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
                               'evolutions': lambda x: evolutions_csv(x, self.catalog)}[section](text)
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
        original = self.baseline.get(source, [])
        # PokeAPI reference has alternate same-species regional evolutions, e.g.
        # regular Vulpix -> Ninetales (Fire Stone) and Alolan -> Alolan (Ice Stone).
        # Required Pokémon form 10205 is Alolan Vulpix. Never display both paths
        # for a single Vulpix form.
        output = []
        for record in original:
            line = record.get('method', '')
            required = re.search(r'Forma requerida \(ID\): (\d+)', line)
            regional = required is not None
            if int(species) in (27, 37) and ((int(form or 0) == 1) != regional):
                continue
            cleaned = {**record, 'method': pretty_reference(line)}
            if regional and int(species) in (27, 37):
                cleaned['target_form'] = 1
            else:
                cleaned['target_form'] = int(form or 0) if int(species) in (27, 37) and int(form or 0) == 1 else 0
            output.append(cleaned)
        source_form = int(form or 0)
        mods = self.data['evolutions'].get(source, [])
        # The CSV field Form represents the resulting species' form; -1
        # inherits the source form. Filter alternate same-target variants for
        # the current source form without conflating target form with source.
        grouped = {}
        for row in mods:
            result_form = source_form if row['form'] == -1 else row['form']
            if source_form in (0, 1) and int(species) in (27, 37) and result_form != source_form:
                continue
            entry = {**row, 'target_form': result_form}
            grouped.setdefault(row['target'], []).append(entry)
        if not grouped:
            return output
        output = [entry for entry in output if entry['target'] not in grouped]
        for variants in grouped.values():
            output.extend(variants)
        return output
