"""Conservative Generation 6 battle HP probe. Never writes memory.

Candidate addresses taken from Citra-Tracker-v2 getaddresses()/hpnum (Gen6).
No health value is trusted unless full decoded battle roster + EC + levels,
abilities and max HP match the validated overworld team, twice.
"""
import struct
from .pokemon import decode_party
from .profiles import GEN6_GAMES, PROFILES

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

def apply_gen6_battle_hp(reader, party, game, party_address, report=None):
    """Try original and party-shifted candidates; fail closed and explain why.

    Report only candidate addresses and rejection categories, never battle bytes.
    """
    if game not in GEN6_GAMES or not any(party):
        return party,False
    original=PROFILES[game].party_address
    delta=party_address-original
    attempted=[]
    rejection='no_match'
    for battle_base,hp_base in candidate_pairs(game):
        for offset in dict.fromkeys((delta,0)):
            candidate=battle_base+offset
            try:
                # Gen6 battle read_party() has *no 128-byte overworld header*.
                # Source: Citra-Tracker-v2 read_party(): PK6 starts at candidate,
                # party stats are found at +344 within each 484-byte slot.
                # Prefix 128 zeroes solely to adapt to our validated decoder.
                battle_raw=bytes(128)+reader.read(candidate,484*5+366)
                roster=decode_party(battle_raw,max_species=721)
                if len(roster)!=len(party):
                    rejection='party_size_mismatch'
                    attempted.append(hex(candidate))
                    continue
                for original_mon,battle_mon in zip(party,roster):
                    if (original_mon is None)!=(battle_mon is None):
                        rejection='roster_slots_mismatch'
                        break
                    if original_mon and any(original_mon.get(field)!=battle_mon.get(field)
                        for field in ('species_id','encryption_constant','level','max_hp','ability_id')):
                        rejection='roster_identity_mismatch'
                        break
                else:
                    values=_read_confirmed_hp(reader,hp_base+offset,party)
                    if values is None:
                        rejection='battle_hp_validation_failed'
                        attempted.append(hex(candidate))
                        continue
                    if report is not None:
                        report.update(battle_probe='verified',
                                      battle_candidate=hex(candidate),
                                      battle_party_shift=offset)
                    return [dict(mon,hp=values[i],hp_source='battle_gen6_candidate')
                            if mon else None for i,mon in enumerate(party)],True
            except (ValueError,ConnectionError,OSError,struct.error) as exc:
                rejection='battle_roster_unavailable'
            attempted.append(hex(candidate))
    if report is not None:
        report.update(battle_probe=rejection,
                      battle_candidates_attempted=attempted[:4],
                      battle_party_shift=delta)
        report.pop('battle_candidate',None)
    return party,False
