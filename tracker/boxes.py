"""USUM box reader. RAM base is a candidate until checked against user's PC."""
from .pokemon import decode_slot
BOX_BASE = 0x33015AB0
SLOTS = 30
STORED_SIZE = 232
BOX_SIZE = SLOTS * STORED_SIZE

def read_box(reader, number, base=BOX_BASE):
    if type(number) is not int or not 1 <= number <= 32:
        raise ValueError('Número de caja inválido: usa 1 a 32.')
    return reader.read(base + (number-1)*BOX_SIZE, BOX_SIZE)

def decode_box(data):
    if len(data) != BOX_SIZE: raise ValueError('La captura de caja debe tener 6960 bytes.')
    result=[]
    for i in range(SLOTS):
        # Same encrypted stored PK7 structure; box Pokémon have no party stats.
        snapshot=bytes(128)+data[i*STORED_SIZE:(i+1)*STORED_SIZE]
        try:
            p=decode_slot(snapshot,0)
            if p is not None: p['slot']=i+1
            result.append(p)
        except ValueError as exc:
            raise ValueError(f'Caja no válida en slot {i+1}: {exc}') from exc
    return result
