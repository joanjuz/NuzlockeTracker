"""Read-only differential search of guest RAM. Never applies candidates to live HP."""
import struct
from .profiles import BATTLE_CANDIDATES, capture_party
from .pokemon import decode_party

START=0x30000000
END=0x40000000
CHUNK=65536


def find_u16(data,value):
    pattern=struct.pack('<H',value)
    pos=data.find(pattern)
    while pos>=0:
        if pos%2==0:
            yield pos
        pos=data.find(pattern,pos+1)


def initial_search(reader,hp,progress=None,start=START,end=END,limit=300000):
    candidates=[];errors=0
    for address in range(start,end,CHUNK):
        try:data=reader.read(address,min(CHUNK,end-address))
        except (OSError,ConnectionError):
            errors+=1;continue
        candidates.extend(address+p for p in find_u16(data,hp))
        if len(candidates)>limit:
            raise ValueError('Demasiadas coincidencias. Repite con más PS para acotar la búsqueda.')
        if progress and (address-start)%(8*1024**2)==0:
            progress(f'RAM revisada: {(address-start)//1024**2} MB · {len(candidates)} candidatos')
    return candidates,errors


def narrow(reader,candidates,hp):
    # Read by pages to avoid thousands of process calls for nearby candidates.
    pages={};result=[]
    for address in candidates:
        page=address&~4095
        if page not in pages:
            try:pages[page]=reader.read(page,4096)
            except (OSError,ConnectionError):pages[page]=None
        data=pages[page]
        if data is not None and struct.unpack_from('<H',data,address-page)[0]==hp:
            result.append(address)
    return result


def sample(reader,profile,candidates=()):
    result={'party':None,'known_candidates':{},'contexts':[]}
    try:result['party']=decode_party(capture_party(reader,profile))
    except (ValueError,OSError,ConnectionError) as exc:result['party_error']=str(exc)
    for name,address in BATTLE_CANDIDATES.items():
        try:
            raw=reader.read(address,24*816+128 if name=='battle_runtime' else 2914)
            result['known_candidates'][name]={'address':hex(address),'raw_hex':raw.hex()}
        except (OSError,ConnectionError) as exc:result['known_candidates'][name]={'error':str(exc)}
    for address in candidates[:512]:
        try:
            begin=max(START,address-64);raw=reader.read(begin,128)
            result['contexts'].append({'address':hex(address),'context_start':hex(begin),'raw_hex':raw.hex(),'u16':struct.unpack_from('<H',raw,address-begin)[0]})
        except (OSError,ConnectionError):pass
    return result
