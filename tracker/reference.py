"""Reference data, distinct from live PK7 values and randomizer metadata."""
import copy,json
from pathlib import Path
DATA=Path(__file__).resolve().parent.parent/'data'
ROUTE_PROFILES={'Ultra Moon 1.0':'Routes_UltraMoon.json','Ultra Sun 1.0':'Routes_UltraMoon.json'}
class ReferenceData:
    def __init__(self):self.analysis=json.loads((DATA/'Analysis_USUM.json').read_text(encoding='utf-8'));self.moves=json.loads((DATA/'MoveDetails_USUM.json').read_text(encoding='utf-8'))['moves']
    def move(self,id,catalog):
        result=copy.deepcopy(self.moves.get(str(id)))
        if result is None:raise ValueError('Movimiento fuera del catálogo USUM.')
        custom=catalog.metadata('moves',id)
        if custom:
            result.update(custom);result['source']='Catálogo ROM · '+catalog.custom['label'];result['rom_override']=True
        else:result['rom_override']=False
        return result
    def routes(self,game):
        if game not in ROUTE_PROFILES:return {'schema_version':1,'game':game,'routes':[]}
        result=json.loads((DATA/ROUTE_PROFILES[game]).read_text(encoding='utf-8'))
        result['game']=game
        result['game_key']='ultra-sun-1.0' if game=='Ultra Sun 1.0' else 'ultra-moon-1.0'
        return result

    def pokemon_types(self,species,form):
        return self.analysis['pokemon'].get(f'{species}:{form}',self.analysis['pokemon'].get(f'{species}:0',[]))
