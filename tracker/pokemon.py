"""PK7 RAM decoding; independent of the emulator transport."""
import struct
from itertools import permutations
from datetime import date
PERMUTATIONS = tuple(permutations(range(4)))
NATURES = ('Fuerte','Huraña','Audaz','Firme','Pícara','Osada','Dócil','Plácida','Agitada','Floja','Miedosa','Activa','Seria','Alegre','Ingenua','Modesta','Afable','Mansa','Tímida','Alocada','Serena','Amable','Grosera','Cauta','Rara')
SPECIES = {637:'Volcarona',350:'Milotic',282:'Gardevoir',373:'Salamence',94:'Gengar',289:'Slaking'}

def crypt(data, seed):
    if len(data) % 2: raise ValueError('Bloque incompleto.')
    result = bytearray()
    for value in struct.unpack('<' + 'H' * (len(data)//2), data):
        seed = (seed * 0x41C64E6D + 0x6073) & 0xffffffff
        result.extend(struct.pack('<H', value ^ (seed >> 16)))
    return bytes(result)

def decode_slot(snapshot, index, max_species=807):
    start = index * 484
    raw = snapshot[start+128:start+360]
    if len(raw) != 232: raise ValueError('Datos Pokémon incompletos.')
    if not any(raw): return None
    seed, sanity, checksum = struct.unpack_from('<IHH', raw)
    if sanity: raise ValueError('Estructura no válida; vuelve a leer.')
    shuffled = crypt(raw[8:], seed)
    order = PERMUTATIONS[((seed >> 13) & 31) % 24]
    data = raw[:8] + b''.join(shuffled[order.index(k)*56:(order.index(k)+1)*56] for k in range(4))
    if sum(struct.unpack('<112H', data[8:])) & 0xffff != checksum:
        raise ValueError('Checksum incorrecto; captura descartada.')
    species, item = struct.unpack_from('<HH', data, 8)
    if species == 0: return None
    if not 1 <= species <= max_species or data[28] >= 25: raise ValueError('Datos fuera del perfil Pokémon correspondiente.')
    iv = struct.unpack_from('<I', data, 116)[0]
    met_date=None
    try:met_date=date(2000+data[0xD4],data[0xD5],data[0xD6]).isoformat()
    except ValueError:pass
    result = dict(slot=index+1, species_id=species, species=SPECIES.get(species, f'Especie #{species}'),
                  nickname=data[64:88].decode('utf-16-le', errors='replace').split('\0')[0],
                  item_id=item, ability_id=data[20], nature=NATURES[data[28]],
                  moves=list(struct.unpack_from('<4H', data, 90)), move_pp=list(data[0x62:0x66]), move_pp_ups=list(data[0x66:0x6A]),
                  ev=list(data[30:36]), iv=[(iv >> (j*5)) & 31 for j in range(6)],
                  form=data[29] >> 3, egg=bool(iv & (1 << 30)), checksum_valid=True,
                  level=None, hp=None, max_hp=None, stats=None,
                  encryption_constant=seed, ot_id=struct.unpack_from('<I',data,0x0C)[0], met_location_id=struct.unpack_from('<H',data,0xDA)[0],
                  egg_location_id=struct.unpack_from('<H',data,0xD8)[0],
                  met_level=data[0xDD]&127, met_date=met_date, origin_version=data[0xDF])
    tail = snapshot[start+472:start+494]
    if len(tail) == 22:
        stats = crypt(tail, seed)
        hp, maximum, attack, defense, speed, spa, spd = struct.unpack_from('<7H', stats, 8)
        level = stats[4]
        if not 1 <= level <= 100 or maximum == 0 or hp > maximum:
            raise ValueError('Estadísticas inconsistentes; vuelve a leer.')
        result.update(level=level, hp=hp, max_hp=maximum,
                      stats=dict(ATQ=attack, DEF=defense, VEL=speed, ATE=spa, DEE=spd))
    return result

def decode_party(snapshot, max_species=807):
    return [decode_slot(snapshot, i, max_species=max_species) for i in range(6)]
