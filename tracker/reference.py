"""Reference data, distinct from live PK7 values and randomizer metadata."""
import copy,json
from pathlib import Path
from .species_reference import SpeciesReference
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
    def __init__(self):
        self.analysis=json.loads((DATA/'Analysis_USUM.json').read_text(encoding='utf-8'))
        self.moves=json.loads((DATA/'MoveDetails_USUM.json').read_text(encoding='utf-8'))['moves']
        self.species_reference=SpeciesReference()
    template_moves = None
    game_data = None
    game_provider = None
    def mega_preview(self,p,catalog,game):
        """Informational projection for a matching held stone, never actual battle stats."""
        if p.get('form',0)!=0:return None
        stone=self.species_reference.mega_stone(p.get('item_id'))
        if stone is None or stone['species']!=p.get('species_id'):return None
        reference=self.species_reference.lookup(stone['species'],stone['form'],game)
        if reference is None:return None
        source=reference['source'];stats=reference['base_stats'];types=reference['types'];ability_id=reference['abilities'][0]
        imported=self.game_data.species(stone['species'],stone['form'],game) if self.game_data is not None else None
        if imported is not None:
            from .game_data import TYPE_NAMES,STAT_KEYS,SOURCE
            source=SOURCE
            stats={label:imported['baseStats'][key] for key,label in STAT_KEYS.items()}
            types=list(dict.fromkeys(TYPE_NAMES[index] for index in imported['types']))
            ability_id=imported['abilities'][0]
        ability=(self.game_data.ability_name(ability_id,game) if self.game_data is not None else None) or catalog.name('abilities',ability_id)
        return {'form':stone['form'],'label':stone['label'],'base_stats':stats,'base_stats_source':source,
                'types':types,'ability_id':ability_id,'ability':ability,'sprite_id':stone['sprite_id'],
                'item_id':p['item_id'],'source':'Simulación mega · '+source,'reference_only':imported is None}
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
        if self.game_data is not None and self.game_provider is not None:
            imported=self.game_data.move(id,self.game_provider())
            if imported is not None:result.update(imported)
        return result
    def routes(self,game):
        if game not in ROUTE_PROFILES:return {'schema_version':1,'game':game,'routes':[]}
        filename,game_key=ROUTE_PROFILES[game]
        result=json.loads((DATA/filename).read_text(encoding='utf-8'))
        result['game']=game
        result['game_key']=game_key
        return result

    def pokemon_types(self,species,form):
        if self.game_data is not None and self.game_provider is not None:
            from .game_data import TYPE_NAMES
            row=self.game_data.species(species,form,self.game_provider())
            if row is not None:return list(dict.fromkeys(TYPE_NAMES[i] for i in row['types']))
        return self.analysis['pokemon'].get(f'{species}:{form}',self.analysis['pokemon'].get(f'{species}:0',[]))
