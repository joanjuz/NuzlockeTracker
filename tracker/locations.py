"""Offline Gen7 encounter-location names from PKHeX's Spanish resources."""
from pathlib import Path
DATA=Path(__file__).resolve().parent.parent/'data'
TABLES={generation:{bank:(DATA/f'Locations{generation}_{bank}.txt').read_text(encoding='utf-8-sig').splitlines() for bank in (0,30000,40000,60000)} for generation in (6,7)}
def location_name(location,origin_version=33):
    if not location:return 'Sin lugar registrado'
    # PK7 can contain Pokémon from older games: do not label their IDs as Alola.
    if origin_version in (24,25,26,27):
        generation=6
    elif origin_version in (30,31,32,33):
        generation=7
    else:
        return f'Lugar ID {location} · juego de origen {origin_version}'
    bank=next((b for b in (60000,40000,30000) if location>=b),0);index=location-bank
    names=TABLES[generation][bank]
    if index<0 or index>=len(names) or not names[index]:return f'Lugar ID {location}'
    name=names[index]
    if bank==0 and index>=6 and index%2==0 and not 194<=index<198 and index+1<len(names) and names[index+1]:name+=f' · {names[index+1]}'
    return name
