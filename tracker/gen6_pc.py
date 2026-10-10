"""Read-only candidate scanner for Gen6 PC boxes.

A dynamic Citra/Lime3DS memory discovery can shift the guest team's offset.
Probe the documented box base and exactly the same shift, independently.
Never commit partial boxes or infer presence from unvalidated bytes.
"""
from .boxes import read_box, decode_box


class Gen6BoxProbe:
    def __init__(self, base_address, party_shift=0):
        if not isinstance(base_address,int) or not 0x08000000<=base_address<=0x0fffffff:
            raise ValueError('Dirección base del PC Gen6 inválida')
        addresses=(base_address,base_address+party_shift)
        self.addresses=tuple(dict.fromkeys(x for x in addresses if 0x08000000<=x<=0x0fffffff))
        self.boxes={addr:{} for addr in self.addresses}
        self.errors={}
        self.last_index=0

    def read(self, reader, number):
        if number!=self.last_index+1 or number<1 or number>31:
            raise ValueError('La lectura de cajas Gen6 debe hacerse en orden')
        self.last_index=number
        for addr in self.addresses:
            if addr in self.errors:continue
            try:
                raw=read_box(reader,number,addr,box_count=31)
                if raw!=read_box(reader,number,addr,box_count=31):
                    raise ValueError('Caja cambió entre lecturas')
                slots=decode_box(raw,max_species=721)
                self.boxes[addr][str(number)]=slots
            except (ValueError,ConnectionError,OSError) as exc:
                # Only sanitized reason and box number, not captured PK6 data.
                self.errors[addr]=(number,str(exc)[:130])

    def finish(self):
        if self.last_index!=31:raise ValueError('Escaneo Gen6 incompleto')
        valid=[(addr,boxes) for addr,boxes in self.boxes.items()
               if addr not in self.errors and len(boxes)==31
               and any(p is not None for members in boxes.values() for p in members)]
        if len(valid)>1 and any(valid[0][1]!=candidate for _,candidate in valid[1:]):
            return None,None
        return valid[0] if valid else (None,None)

    def diagnostic(self):
        result=[]
        for address in self.addresses:
            boxes=self.boxes[address]
            pokemons=sum(p is not None for box in boxes.values() for p in box)
            issue=self.errors.get(address)
            result.append({
                'box_address':hex(address),
                'completed':len(boxes),
                'pokemon_verified':pokemons,
                'first_rejection_box':issue[0] if issue else None,
                'first_rejection':issue[1] if issue else None,
            })
        return result
