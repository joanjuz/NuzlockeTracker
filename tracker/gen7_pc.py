"""Incremental, bounded, read-only validation of the complete USUM PC.

Empty bytes cannot prove a PC address. Only a unique populated 32-box layout
with equal repeated reads and valid PK7 checksums can be published.
"""
from .boxes import BOX_BASE,read_box,decode_box


class Gen7BoxProbe:
    def __init__(self,base_addresses=(BOX_BASE,),cancel=None):
        if isinstance(base_addresses,(int,bool)):base_addresses=(base_addresses,)
        self.addresses=tuple(dict.fromkeys(base_addresses))
        if not 1<=len(self.addresses)<=4 or any(type(a) is not int or not 0x30000000<=a<=0x40000000-32*6960 for a in self.addresses):
            raise ValueError('Direcciones de PC Gen7 inválidas')
        self.cancel=cancel;self.boxes={a:{} for a in self.addresses};self.errors={}
        self.last_index=0;self.status='pending';self._result=None

    def read(self,reader,number):
        if type(number) is not int or not 1<=number<=32:
            raise ValueError('La caja Gen7 debe estar entre 1 y 32')
        # A finished probe is immutable; duplicate polls never repeat its scan.
        if number<=self.last_index:return
        if number!=self.last_index+1:raise ValueError('La lectura de cajas Gen7 debe hacerse en orden')
        for address in self.addresses:
            if address in self.errors:continue
            if self.cancel and self.cancel():
                from .process_memory import DiscoveryCancelled
                raise DiscoveryCancelled('Verificación de PC cancelada.')
            try:
                one=read_box(reader,number,address)
                if self.cancel and self.cancel():
                    from .process_memory import DiscoveryCancelled
                    raise DiscoveryCancelled('Verificación de PC cancelada.')
                two=read_box(reader,number,address)
                if self.cancel and self.cancel():
                    from .process_memory import DiscoveryCancelled
                    raise DiscoveryCancelled('Verificación de PC cancelada.')
                if one!=two:raise ValueError('Caja cambió entre lecturas')
                slots=decode_box(one)
                if self.cancel and self.cancel():
                    from .process_memory import DiscoveryCancelled
                    raise DiscoveryCancelled('Verificación de PC cancelada.')
                self.boxes[address][str(number)]=slots
            except (ValueError,ConnectionError,OSError) as exc:
                from .process_memory import DiscoveryCancelled
                if isinstance(exc,DiscoveryCancelled):raise
                self.errors[address]={'box':number,'reason':str(exc)[:130]}
        self.last_index=number

    def finish(self):
        if self.cancel and self.cancel():
            from .process_memory import DiscoveryCancelled
            raise DiscoveryCancelled('Verificación de PC cancelada.')
        if self.last_index!=32:raise ValueError('Escaneo Gen7 incompleto')
        if self._result is not None:return self._result
        valid=[];empty=False
        for address,boxes in self.boxes.items():
            if address in self.errors or len(boxes)!=32:continue
            if any(p is not None for members in boxes.values() for p in members):valid.append((address,boxes))
            else:empty=True
        if len(valid)==1:self.status='verified';self._result=valid[0]
        else:
            self.status='ambiguous' if len(valid)>1 else 'pending_empty' if empty else 'invalid'
            self._result=(None,None)
        return self._result

    def diagnostic(self):
        return {'status':self.status,'completed':self.last_index,'candidates':[
            {'box_address':hex(a),'completed':len(self.boxes[a]),
             'pokemon_verified':sum(p is not None for box in self.boxes[a].values() for p in box),
             'first_rejection':self.errors.get(a)} for a in self.addresses]}
