"""Conservative Generation 6 battle HP probe. Never writes memory.

Candidate addresses taken from Citra-Tracker-v2 getaddresses()/hpnum (Gen6).
No health value is trusted unless full decoded battle roster + EC + levels,
abilities and max HP match the validated overworld team, twice.
"""
import struct
from dataclasses import replace
from .pokemon import decode_party
from .profiles import capture_party, GEN6_GAMES, PROFILES

STRIDE=580

# (battle-party PK6 header, battle stat array pointer reference)
XY_CANDIDATES=((142625392,136331232),(142622504,136338160))
ORAS_CANDIDATES=(
    (0x08CF727C-6000000+812440,0x08CF727C-0x0AF2F5C-20),
    (0x08CF727C-6000000+809556,0x08CF727C-0x0AF2F5C-20+6928)
)

def candidate_pairs(game):
    if game in ('Pokémon X 1.0','Pokémon Y 1.0'):
        return XY_CANDIDATES
    if game in ('Omega Ruby 1.0','Alpha Sapphire 1.0'):
        return ORAS_CANDIDATES
    return ()

def _read_confirmed_hp(reader,base,party):
    # At reference pointer ppadd: maxHP @ -266, currentHP @ -264,
    # ability @ -258 and level @ -256 (Gen6, reverse engineered).
    # Read from the memory reader only, never from a saved dump.
    def sample():
        result=[]
        for i,p in enumerate(party):
            if p is None:
                result.append(None)
                continue
            block=reader.read(base+i*STRIDE-266,12)
            maximum,current=struct.unpack_from('<HH',block,0)
            ability=block[8]
            level=block[10]
            if (maximum!=p.get('max_hp') or not 1<=maximum<=714 or current>maximum or
                level!=p.get('level') or ability!=p.get('ability_id')):
                return None
            result.append(current)
        return result
    first=sample()
    if first is None:return None
    return first if sample()==first else None

def apply_gen6_battle_hp(reader, party, game, party_address):
    """Return (party, in_battle), refusing unverified and partially changed data."""
    if game not in GEN6_GAMES or not any(party):
        return party,False
    original=PROFILES[game].party_address
    delta=party_address-original
    for battle_base,hp_base in candidate_pairs(game):
        try:
            battle_raw=capture_party(reader,replace(PROFILES[game],party_address=battle_base+delta))
            roster=decode_party(battle_raw,max_species=721)
            if len(roster)!=len(party):
                continue
            for original_mon,battle_mon in zip(party,roster):
                if (original_mon is None)!=(battle_mon is None):
                    break
                if original_mon and any(original_mon.get(field)!=battle_mon.get(field) for field in
                    ('species_id','encryption_constant','level','max_hp','ability_id')):
                    break
            else:
                values=_read_confirmed_hp(reader,hp_base+delta,party)
                if values is None:
                    continue
                return [dict(mon,hp=values[i],hp_source='battle_gen6_candidate')
                        if mon else None for i,mon in enumerate(party)],True
        except (ValueError,ConnectionError,OSError,struct.error):
            continue
    return party,False
