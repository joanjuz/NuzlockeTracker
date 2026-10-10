"""Read-only Gen6 diagnostic: trace a known Pokémon moved into PC Box 1 Slot 1.

We require the encrypted EC + species of a party member BEFORE depositing,
then search 0x08000000..0x0FFFFFFF for an exact stored PK6 record AFTER.
Only a complete, stable 31-box PC is accepted. No raw Pokémon data is exported.
"""
import struct
from .pokemon import decode_slot
from .boxes import read_box,decode_box

START=0x08000000
END=0x10000000
CHUNK=65536


def find_deposited_box(reader, encryption_constant, species_id, progress=None,
                       start=START, end=END, max_hits=96):
    if type(encryption_constant) is not int or not 0<encryption_constant<=0xffffffff:
        raise ValueError('EC de Pokémon inválido')
    if type(species_id) is not int or not 1<=species_id<=721:
        raise ValueError('Especie Gen6 inválida')
    if not START<=start<end<=END or max_hits not in range(1,257):
        raise ValueError('Rango de búsqueda fuera de memoria Gen6')
    needle=struct.pack('<I',encryption_constant)
    read_errors=0
    bytes_scanned=0
    hits=[]
    candidates=[]
    seen=set()
    for address in range(start,end,CHUNK):
        size=min(CHUNK,end-address)
        try:
            block=reader.read(address,size)
            if len(block)!=size:
                raise ValueError('Lectura incompleta')
        except (ValueError,OSError,ConnectionError):
            read_errors+=1
            continue
        bytes_scanned+=size
        pos=block.find(needle)
        while pos>=0:
            absolute=address+pos
            if absolute%4==0 and absolute not in seen:
                seen.add(absolute)
                hits.append(absolute)
                try:
                    raw=reader.read(absolute,232)
                    pk=decode_slot(bytes(128)+raw,0,max_species=721)
                    if pk is not None and pk['species_id']==species_id and pk['encryption_constant']==encryption_constant:
                        candidates.append(absolute)
                except (ValueError,OSError,ConnectionError):
                    pass
                if len(hits)>=max_hits:
                    break
            pos=block.find(needle,pos+1)
        if len(hits)>=max_hits:
            break
        if progress and (address-start)%(16*1024**2)==0:
            progress('PC Gen6: '+str((address-start)//(1024**2))+
                     ' MiB · coincidencias EC '+str(len(hits)))
    confirmed=[]
    validation=[]
    for addr in candidates:
        error=None
        verified={}
        try:
            for n in range(1,32):
                first=read_box(reader,n,addr,box_count=31)
                if first!=read_box(reader,n,addr,box_count=31):
                    raise ValueError('lecturas inconsistentes')
                verified[str(n)]=decode_box(first,max_species=721)
            first=verified['1'][0]
            if first is None or first['encryption_constant']!=encryption_constant or first['species_id']!=species_id:
                raise ValueError('casilla 1 no coincide con el Pokémon depositado')
            confirmed.append(addr)
        except (ValueError,OSError,ConnectionError) as exc:
            error=str(exc)[:100]
        validation.append({'address':hex(addr),'verified':error is None,
                           'rejection':error})
    unique=len(confirmed)==1 and len(hits)<max_hits
    return {
        'stage':'gen6_box1_slot1',
        'range_start':hex(start),'range_end':hex(end),
        'bytes_scanned':bytes_scanned,'read_errors':read_errors,
        'ec_match_count':len(hits),
        'valid_stored_pk6_addresses':[hex(addr) for addr in candidates[:24]],
        'tested_bases':validation[:32],
        'complete_box_base':hex(confirmed[0]) if unique else None,
        'ambiguous':len(confirmed)>1 or len(hits)>=max_hits,
        'note':'No se incluyen bytes de memoria, nombres, OT, ni datos del guardado.'
    }
