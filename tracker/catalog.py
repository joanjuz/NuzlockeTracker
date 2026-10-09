"""Offline names plus explicitly loaded ROM metadata, separate from live RAM."""
import json
from pathlib import Path
DATA = Path(__file__).resolve().parent.parent / 'data'
class Catalog:
    def __init__(self):
        self.names = {key: (DATA / (filename + '.txt')).read_text(encoding='utf-8-sig').splitlines()
                      for key,filename in [('species','Species'),('moves','Moves'),('abilities','Abilities'),('items','Items')]}
        self.custom = None
    def name(self, section, id):
        custom = (self.custom or {}).get(section, {}).get(str(id), {})
        if 'name' in custom: return custom['name']
        names = self.names[section]
        return names[id] if 0 <= id < len(names) and names[id] else f'ID {id}'
    def load(self, path):
        if Path(path).stat().st_size > 5_000_000: raise ValueError('Catálogo demasiado grande.')
        value = json.loads(Path(path).read_text(encoding='utf-8-sig'))
        if not isinstance(value,dict) or value.get('schema_version') != 1 or value.get('game') != 'Ultra Moon 1.0':
            raise ValueError('Se requiere schema_version 1 y game Ultra Moon 1.0.')
        if not isinstance(value.get('label'),str) or not value['label'].strip(): raise ValueError('Falta label.')
        for section,limit in [('species',807),('moves',728),('abilities',233),('items',959)]:
            entries=value.get(section,{})
            if not isinstance(entries,dict): raise ValueError(f'{section} debe ser un objeto.')
            for key,item in entries.items():
                if not key.isdigit() or not 0 <= int(key) <= limit or not isinstance(item,dict):
                    raise ValueError(f'Entrada inválida en {section}: {key}')
                if 'name' in item and (not isinstance(item['name'],str) or not item['name'].strip()): raise ValueError('Nombre inválido.')
                if 'types' in item and (not isinstance(item['types'],list) or not 1<=len(item['types'])<=2 or not all(isinstance(t,str) and t for t in item['types'])): raise ValueError('Tipos inválidos.')
                for field in ('type','category','description'):
                    if field in item and not isinstance(item[field],str): raise ValueError(f'{field} inválido.')
                for field in ('power','accuracy','pp'):
                    if field in item and (type(item[field]) is not int or not 0 <= item[field] <= 255): raise ValueError(f'{field} inválido.')
        self.custom=value # Commit only after full validation.
    def metadata(self, section, id):
        return (self.custom or {}).get(section,{}).get(str(id),{})
