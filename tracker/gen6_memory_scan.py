"""Bounded, read-only PK6 PC discovery near an independently sourced Gen6 base.

Never expose raw bytes or Pokémon details in diagnostics. A valid isolated
PK6 is a *hint*; publishing boxes still requires an unambiguous complete
31x30 contiguous structure validated with two equal reads per box.
"""
from .pokemon import decode_slot
from .boxes import read_box, decode_box

WINDOW_RADIUS=0x80000
CHUNK=0x10000
MAX_VERIFY=24

def search_pc_memory(reader, reference, radius=WINDOW_RADIUS):
    if not isinstance(reference,int) or not 0x08000000<=reference<0x10000000:
        raise ValueError('Referencia de memoria Gen6 no válida')
    if not 0x1000<=radius<=WINDOW_RADIUS:
        raise ValueError('Rango de búsqueda inválido')
    start=max(0x08000000,(reference-radius)&~3)
    stop=min(0x10000000,(reference+radius+3)&~3)
    found=set()
    read_errors=0
    scanned=0
    tail=b''
    for address in range(start,stop,CHUNK):
        count=min(CHUNK,stop-address)
        try:
            data=reader.read(address,count)
            if len(data)!=count:raise ValueError('Bloque incompleto')
        except (ValueError,ConnectionError,OSError):
            read_errors+=1
            tail=b''
            continue
        scanned+=count
        combined=tail+data
        absolute=address-len(tail)
        # All Gen6 PK6 slot addresses in a PC are 4-byte aligned.
        begin=(-absolute)%4
        for pos in range(begin,len(combined)-231,4):
            if (combined[pos+4] or combined[pos+5] or
                not any(combined[pos:pos+4]) or
                not any(combined[pos+6:pos+8])):
                continue
            addr=absolute+pos
            try:
                pokemon=decode_slot(bytes(128)+combined[pos:pos+232],0,max_species=721)
                if pokemon is not None and pokemon.get('checksum_valid') is True:
                    found.add(addr)
            except (ValueError,IndexError):
                continue
        tail=combined[-231:]
    candidates=sorted(found,key=lambda addr:(abs(addr-reference),addr))
    confirmed=[]
    attempted=0
    for base in candidates[:MAX_VERIFY]:
        attempted+=1
        boxes={}
        try:
            for number in range(1,32):
                one=read_box(reader,number,base,box_count=31)
                if one!=read_box(reader,number,base,box_count=31):
                    raise ValueError('Lectura inconsistente')
                boxes[str(number)]=decode_box(one,max_species=721)
            if boxes['1'][0] is None:
                continue
            if not any(mon for box in boxes.values() for mon in box):
                continue
            confirmed.append((base,boxes))
            if len(confirmed)>1:
                break
        except (ValueError,ConnectionError,OSError):
            continue
    result={'scan_bytes':scanned,'read_errors':read_errors,
            'valid_pk6_hits':len(candidates),'candidate_addresses':
            [hex(x) for x in candidates[:12]],'bases_checked':attempted,
            'fully_verified_bases':[hex(a) for a,_ in confirmed[:2]],
            'ambiguous':len(confirmed)>1}
    if len(confirmed)==1 and (len(candidates)<=MAX_VERIFY):
        base,boxes=confirmed[0]
        return base,boxes,result
    # More than one plausible alignment or too many candidates: fail closed.
    return None,None,result
