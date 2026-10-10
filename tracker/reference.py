"""Reference data, distinct from live PK7 values and randomizer metadata."""
import copy,json
from pathlib import Path
DATA=Path(__file__).resolve().parent.parent/'data'
ROUTE_PROFILES={
    'Ultra Moon 1.0':('Routes_UltraMoon.json','ultra-moon-1.0'),
    'Ultra Sun 1.0':('Routes_UltraMoon.json','ultra-sun-1.0'),
    'Pokémon X 1.0':('Routes_XY.json','pokemon-x-1.0'),
    'Pokémon Y 1.0':('Routes_XY.json','pokemon-y-1.0'),
    'Omega Ruby 1.0':('Routes_ORAS.json','omega-ruby-1.0'),
    'Alpha Sapphire 1.0':('Routes_ORAS.json','alpha-sapphire-1.0'),
}
class ReferenceData:
    def __init__(self):self.analysis=json.loads((DATA/'Analysis_USUM.json').read_text(encoding='utf-8'));self.moves=json.loads((DATA/'MoveDetails_USUM.json').read_text(encoding='utf-8'))['moves']
    template_moves = None
    def move(self,id,catalog):
        result=copy.deepcopy(self.moves.get(str(id)))
        if result is None:raise ValueError('Movimiento fuera del catálogo USUM.')
        custom=catalog.metadata('moves',id)
        if custom:
            result.update(custom);result['source']='Catálogo ROM · '+catalog.custom['label'];result['rom_override']=True
        else:result['rom_override']=False
        template=(self.template_moves or {}).get(str(id))
        if template:
            result.update(copy.deepcopy(template))
            result['source']='Plantilla pk3DS Progressive (datos importados)'
            result['rom_override']=True
        return result
    def routes(self,game):
        if game not in ROUTE_PROFILES:return {'schema_version':1,'game':game,'routes':[]}
        filename,game_key=ROUTE_PROFILES[game]
        result=json.loads((DATA/filename).read_text(encoding='utf-8'))
        result['game']=game
        result['game_key']=game_key
        return result

    def pokemon_types(self,species,form):
        return self.analysis['pokemon'].get(f'{species}:{form}',self.analysis['pokemon'].get(f'{species}:0',[]))
