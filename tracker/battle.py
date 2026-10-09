"""USUM 1.0 battle HP, validated against Ultra Moon and Ultra Sun captures."""
import struct

BATTLE_START=0x3000975C  # species, max HP, current HP; stride 816
STRIDE=816
LENGTH=5*STRIDE+16


def apply_battle_hp(reader,party,game):
    if game not in ('Ultra Moon 1.0','Ultra Sun 1.0') or not any(party):
        return party,False
    try:
        data=reader.read(BATTLE_START,LENGTH)
        # Reject a structure being allocated/freed or updated between reads.
        if data!=reader.read(BATTLE_START,LENGTH):return party,False
    except (OSError,ConnectionError,ValueError):
        return party,False
    values=[]
    for i,p in enumerate(party):
        offset=i*STRIDE
        species,maximum,hp=struct.unpack_from('<3H',data,offset)
        if p is None:
            if species or maximum or hp:return party,False
            values.append(None);continue
        ability=struct.unpack_from('<H',data,offset+10)[0]
        level=data[offset+12]
        # Match the entire roster in order. Transformations/reordered layouts fall back.
        if p.get('egg') or (species,maximum,level,ability)!=(p['species_id'],p['max_hp'],p['level'],p['ability_id']) or maximum<=0 or hp>maximum:
            return party,False
        values.append(hp)
    return [dict(p,hp=values[i],hp_source='battle') if p else None for i,p in enumerate(party)],True
