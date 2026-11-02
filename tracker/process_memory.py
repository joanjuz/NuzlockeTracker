"""Windows read-only 3DS emulator connector (experimental on Azahar/Citra)."""
from __future__ import annotations

import ctypes as C
from ctypes import wintypes as W
import os,struct,time
from collections import OrderedDict
from collections.abc import Callable,Iterable,Iterator
from threading import Lock
from typing import Any,NoReturn,Protocol,cast
from .pokemon import decode_party
from .boxes import decode_box,BOX_BASE,BOX_SIZE
PARTY=0x33F7FA44
LINEAR=0x30000000
SIGNATURE_OFFSET=68
NEEDLE=struct.pack('<III',PARTY+128,PARTY+472,PARTY+408)

Region=tuple[int,int]
"""(host base address, size in bytes) of a readable emulator mapping."""
Discovery=tuple[int,int]
"""(host base of the guest RAM window, guest party address)."""
Report=dict[str,Any]
Progress=Callable[[str],object]|None
Cancel=Callable[[],object]|None


class MemoryReader(Protocol):
    """Anything that can read raw bytes at a host address (process, budget, fake)."""
    def read(self,address:int,length:int,/)->bytes:...


class RegionReader(MemoryReader,Protocol):
    """A reader that also enumerates its readable regions."""
    discovery_report:Report
    def regions(self)->Iterable[Region]:...


class DiscoveryError(ConnectionError):
    def __init__(self,message:str,diagnostic:Report|None=None)->None:
        super().__init__(message);self.diagnostic=diagnostic

class DiscoveryCancelled(ConnectionError):
    pass

class ProcessEntry(C.Structure):
    _fields_=[('dwSize',W.DWORD),('cntUsage',W.DWORD),('th32ProcessID',W.DWORD),('th32DefaultHeapID',C.c_size_t),('th32ModuleID',W.DWORD),('cntThreads',W.DWORD),('th32ParentProcessID',W.DWORD),('pcPriClassBase',W.LONG),('dwFlags',W.DWORD),('szExeFile',W.WCHAR*260)]
class MemoryInfo(C.Structure):
    _fields_=[('BaseAddress',C.c_void_p),('AllocationBase',C.c_void_p),('AllocationProtect',W.DWORD),('PartitionId',W.WORD),('RegionSize',C.c_size_t),('State',W.DWORD),('Protect',W.DWORD),('Type',W.DWORD)]

def windows_api()->C.WinDLL:
    if os.name!='nt' or C.sizeof(C.c_void_p)!=8:raise DiscoveryError('Este conector requiere Windows y Python de 64 bits.')
    api=C.WinDLL('kernel32',use_last_error=True)
    signatures:list[tuple[str,list[Any],Any]]=[
        ('CreateToolhelp32Snapshot',[W.DWORD,W.DWORD],W.HANDLE),
        ('Process32FirstW',[W.HANDLE,C.POINTER(ProcessEntry)],W.BOOL),
        ('Process32NextW',[W.HANDLE,C.POINTER(ProcessEntry)],W.BOOL),
        ('OpenProcess',[W.DWORD,W.BOOL,W.DWORD],W.HANDLE),
        ('CloseHandle',[W.HANDLE],W.BOOL),
        ('ReadProcessMemory',[W.HANDLE,C.c_void_p,C.c_void_p,C.c_size_t,C.POINTER(C.c_size_t)],W.BOOL),
        ('VirtualQueryEx',[W.HANDLE,C.c_void_p,C.POINTER(MemoryInfo),C.c_size_t],C.c_size_t),
        ('GetExitCodeProcess',[W.HANDLE,C.POINTER(W.DWORD)],W.BOOL),
        ('GetProcessTimes',[W.HANDLE,C.POINTER(W.FILETIME),C.POINTER(W.FILETIME),C.POINTER(W.FILETIME),C.POINTER(W.FILETIME)],W.BOOL)]
    for name,args,result in signatures:
        fn=getattr(api,name);fn.argtypes=args;fn.restype=result
    return api

def supported_emulator(name:object)->bool:
    """Process-name discovery only; RAM layout must still validate per emulator."""
    if not isinstance(name, str):
        return False
    value = name.lower()
    return value.endswith('.exe') and value.startswith(('lime3ds', 'azahar', 'citra'))


def list_lime_processes(api:Any)->list[tuple[int,str]]:
    handle=api.CreateToolhelp32Snapshot(2,0)
    if handle in (None,C.c_void_p(-1).value):raise C.WinError(C.get_last_error())
    entries:list[tuple[int,str]]=[]
    try:
        entry=ProcessEntry();entry.dwSize=C.sizeof(entry)
        success=api.Process32FirstW(handle,C.byref(entry))
        while success:
            name=entry.szExeFile
            if supported_emulator(name):entries.append((entry.th32ProcessID,name))
            success=api.Process32NextW(handle,C.byref(entry))
    finally:api.CloseHandle(handle)
    return entries

class WindowsProcess:
    # Annotation only: set by the discovery functions after a successful scan.
    discovery_report:Report
    def __init__(self,pid:int|None=None)->None:
        self.api:Any=windows_api();processes=list_lime_processes(self.api)
        if pid is not None:
            processes=[p for p in processes if p[0]==pid]
        if not processes:raise DiscoveryError('No se encontró Lime3DS, Azahar ni Citra. Abre un emulador y carga la partida.')
        if len(processes)>1:raise DiscoveryError('Hay varios emuladores abiertos. Introduce el PID: '+', '.join(str(p[0]) for p in processes))
        self.pid,self.name=processes[0]
        # VirtualQueryEx requires PROCESS_QUERY_INFORMATION (0x0400), while
        # ReadProcessMemory requires PROCESS_VM_READ (0x0010). Do not request
        # PROCESS_ALL_ACCESS or attempt to bypass Windows security.
        self.handle:int|None=self.api.OpenProcess(0x0400|0x0010,False,self.pid)
        if not self.handle:
            error=C.get_last_error()
            if error==5:
                raise DiscoveryError(
                    f'Acceso denegado a {self.name} (PID {self.pid}, WinError 5). '
                    'Windows no permite leer la memoria de este proceso. '
                    'Cierra Azahar/Citra y vuelve a abrirlo normalmente, sin '
                    '«Ejecutar como administrador», igual que Pokémon Tracker. '
                    'Comprueba el PID en el Administrador de tareas. Si sigue '
                    'fallando, guarda el diagnóstico; la compatibilidad con '
                    'este emulador continúa siendo experimental.',
                    {'process':self.name,'pid':self.pid,'winerror':error,
                     'stage':'OpenProcess'})
            raise DiscoveryError(
                f'No se pudo abrir {self.name} (PID {self.pid}, error Windows {error}).',
                {'process':self.name,'pid':self.pid,'winerror':error,
                 'stage':'OpenProcess'})
        # GetProcessTimes/EnumWindows may fail after OpenProcess: never
        # leak the read-only handle in that case.
        try:self.metadata:Report=process_metadata(self)
        except BaseException:
            self.close();raise
    def read(self,address:int,length:int)->bytes:
        buffer=C.create_string_buffer(length);received=C.c_size_t()
        ok=self.api.ReadProcessMemory(self.handle,C.c_void_p(address),buffer,length,C.byref(received))
        if not ok or received.value!=length:raise DiscoveryError(f'No se pudo leer memoria del proceso (error {C.get_last_error()}).')
        return buffer.raw
    def regions(self)->Iterator[Region]:
        address=0
        while address<0x7fffffffffff:
            info=MemoryInfo()
            if not self.api.VirtualQueryEx(self.handle,C.c_void_p(address),C.byref(info),C.sizeof(info)):break
            base,size=info.BaseAddress or 0,info.RegionSize
            if size==0 or base+size<=address:break
            # Committed, readable, no guard; exclude code/image mappings.
            if info.State==0x1000 and not info.Protect&0x100 and info.Protect&0xff in (2,4,8,32,64,128) and info.Type in (0x20000,0x40000):yield base,size
            address=base+size
    def alive(self)->bool:
        code=W.DWORD()
        return bool(self.handle and self.api.GetExitCodeProcess(self.handle,C.byref(code)) and code.value==259)
    def close(self)->None:
        if self.handle:self.api.CloseHandle(self.handle);self.handle=None

def validate_anchor(process:MemoryReader,anchor:int)->int:
    data=process.read(anchor,2914)
    if data[SIGNATURE_OFFSET:SIGNATURE_OFFSET+4]!=NEEDLE[:4]:raise DiscoveryError('Firma de equipo inválida.')
    party=decode_party(data)
    if not any(p is not None for p in party):raise DiscoveryError('No hay Pokémon para validar la RAM.')
    base=anchor-(PARTY-LINEAR)
    if base<=0:raise DiscoveryError('Base de RAM inválida.')
    decode_box(process.read(base+(BOX_BASE-LINEAR),BOX_SIZE))
    return base

def discover_ram(process:RegionReader,progress:Progress=None,timeout:float=60,
                 budget:int=4*1024**3,cancel:Cancel=None)->int:
    started=time.monotonic();scanned=0;matches:list[int]=[]
    regions=sorted(process.regions(),key=lambda r:r[1],reverse=True)
    report:Report={'schema_version':1,'pid':getattr(process,'pid',None),'process':getattr(process,'name',None),
            'readable_regions':len(regions),'readable_bytes':sum(size for _,size in regions),
            'regions_scanned':0,'bytes_scanned':0,'read_errors':0,'signatures_found':0,
            'rejections':[],'elapsed_seconds':0,'candidates':[]}
    def fail(message:str)->NoReturn:
        report['bytes_scanned']=scanned;report['elapsed_seconds']=round(time.monotonic()-started,2)
        raise DiscoveryError(message,report)
    for start,size in regions:
        if cancel and cancel():raise DiscoveryCancelled('Búsqueda cancelada por una nueva solicitud.')
        tail=b'';report['regions_scanned']+=1
        for offset in range(0,size,4*1024**2):
            if cancel and cancel():raise DiscoveryCancelled('Búsqueda cancelada por una nueva solicitud.')
            if time.monotonic()-started>timeout or scanned>=budget:
                fail('Búsqueda alcanzó su límite. Guarda diagnóstico para revisar los candidatos.')
            length=min(4*1024**2,size-offset,budget-scanned)
            try:data=process.read(start+offset,length)
            except (DiscoveryCancelled,DiscoveryLimit):raise
            except (OSError,DiscoveryError):report['read_errors']+=1;tail=b'';continue
            scanned+=length;block=tail+data;begin=start+offset-len(tail)
            # The PK7 pointer is stable; secondary wrapper pointers may differ.
            pattern=NEEDLE[:4];pos=block.find(pattern)
            while pos>=0:
                report['signatures_found']+=1;anchor=begin+pos-SIGNATURE_OFFSET
                try:
                    base=validate_anchor(process,anchor)
                    if base not in matches:matches.append(base)
                except (ValueError,OSError,DiscoveryError) as exc:
                    if len(report['rejections'])<24:report['rejections'].append({'host_anchor':hex(anchor),'reason':str(exc)})
                pos=block.find(pattern,pos+1)
            tail=block[-3:]
            if progress:progress(f'Localizando RAM: {scanned//(1024**2)} MB · {report["signatures_found"]} firmas · {report["regions_scanned"]} regiones')
        if matches:
            report['candidates']=[hex(base) for base in matches]
            report['bytes_scanned']=scanned;report['elapsed_seconds']=round(time.monotonic()-started,2)
            if len(matches)!=1:fail('Varias copias de RAM válidas. Guarda diagnóstico antes de reintentar.')
            process.discovery_report=report
            return matches[0]
    fail('No se encontró una RAM válida. Guarda diagnóstico; comprueba que la partida esté cargada.')

class LimeProcessMemory:
    def __init__(self,pid:int|None=None,progress:Progress=None,dynamic:bool=False,
                 cancel:Cancel=None,generation:int=7)->None:
        if generation not in (6,7):raise ValueError('Generación inválida')
        self.generation=generation
        self.guest_start=0x08000000 if generation==6 else LINEAR
        self.guest_end=0x10000000 if generation==6 else LINEAR+256*1024**2
        self.process=WindowsProcess(pid);self.base:int|None=None;self.party_address=PARTY
        try:
            # Central policy also protects the legacy interface. The boolean
            # remains accepted for compatibility; validation decides the layout.
            self.discovery_mode = 'dynamic'
            self.base,self.party_address=discover_dynamic_ram(
                self.process,progress,cancel=cancel,generation=generation)
        except Exception:self.process.close();raise
    def identify(self)->str:return f'Windows · PID {self.process.pid} · RAM localizada'
    def resume(self)->None:pass # No debugger: does not pause or resume the emulator.
    def read(self,address:int,length:int)->bytes:
        if not getattr(self,'guest_start',LINEAR)<=address or address+length>getattr(self,'guest_end',LINEAR+256*1024**2) or not 1<=length<=65536:raise ValueError('Lectura fuera del rango de RAM del perfil.')
        if not self.process.alive():raise DiscoveryError('El emulador se cerró.')
        # base is always set once __init__ (discovery) succeeded; cast is static only.
        base=cast(int,self.base)
        # Signature catches a cleared/moved RAM allocation after an internal restart.
        if self.process.read(base+getattr(self,'party_address',PARTY)-getattr(self,'guest_start',LINEAR)+SIGNATURE_OFFSET,4)!=struct.pack('<I',getattr(self,'party_address',PARTY)+128):
            invalidate_discovery_cache(self.process,self.generation if hasattr(self,'generation') else 7)
            raise DiscoveryError('Partida reiniciada o RAM trasladada. Esperando para localizarla nuevamente.')
        return self.process.read(base+address-getattr(self,'guest_start',LINEAR),length)
    def close(self)->None:self.process.close()


def probe_gen6_region_ram(process:RegionReader,progress:Progress=None,
                          cancel:Cancel=None)->tuple[Discovery|None,Report]:
    """Fast read-only Gen6 probe using known party locations inside large RAM maps.

    Citra/Lime3DS can keep the same guest RAM map without a currently valid
    wrapper for dynamic discovery. This recognizes the *real* party PK6
    checksum instead of choosing a region solely from an address heuristic.
    """
    from .profiles import POKEMON_X_10, OMEGA_RUBY_10
    guest_base=0x08000000
    known=(POKEMON_X_10.party_address,OMEGA_RUBY_10.party_address)
    # Some builds expose a party wrapper 128 bytes before reference.
    party_addresses=tuple(dict.fromkeys(
        address+delta for address in known for delta in (0,-128,128)
    ))
    report:Report={'schema_version':2,'mode':'gen6_direct_region','generation':6,
            'pid':getattr(process,'pid',None),
            'process':getattr(process,'name',None),
            'regions_tested':0,'anchors_tested':0,
            'valid_candidates':0}
    accepted:dict[Discovery,int]={}
    regions=sorted(process.regions(),key=lambda item:item[1],reverse=True)
    for start,size in regions:
        if cancel and cancel():raise DiscoveryCancelled('Búsqueda cancelada.')
        if size<16*1024**2 or size>8*1024**3:continue
        report['regions_tested']+=1
        for skew in (0,32,64,96,128,256,512,1024,2048,4096):
            base=start+skew
            for guest in party_addresses:
                if cancel and cancel():raise DiscoveryCancelled('Búsqueda cancelada.')
                anchor=base+(guest-guest_base)
                if anchor<start or anchor+2914>start+size:continue
                report['anchors_tested']+=1
                try:
                    data=process.read(anchor,2914)
                    if struct.unpack_from('<I',data,68)[0]!=guest+128:continue
                    members=decode_party(data,max_species=721)
                    count=sum(member is not None for member in members)
                    if count==0 or not members[0]:continue
                    # Re-check to discard RAM torn by a live scene transition.
                    if process.read(anchor,2914)!=data:continue
                    accepted[(base,guest)]=count
                except DiscoveryCancelled:raise
                except (ValueError,OSError,ConnectionError,struct.error):
                    continue
    report['valid_candidates']=len(accepted)
    if not accepted:return None,report
    if len(accepted)!=1:
        report['ambiguous']=True
        return None,report
    return next(iter(accepted)),report


def _scan_dynamic_ram(process:RegionReader,progress:Progress=None,timeout:float=90,
                      budget:int=4*1024**3,cancel:Cancel=None,generation:int=7)->Discovery:
    """Find self-referencing party wrappers without assuming the guest party address."""
    import re
    # Two nearby guest pointers; secondary wrapper offsets may differ.
    # Validate the self-reference and the complete decoded party.
    if generation not in (6,7):raise ValueError('Generación inválida')
    # Gen6 PK6 resides in legacy 0x08xxxxxx guest memory. Gen7 in 0x3xxxxxxx.
    start_addr,end_addr=(0x08000000,0x10000000) if generation==6 else (LINEAR,LINEAR+256*1024**2)
    high_bytes=br'[\x08-\x0f]' if generation==6 else br'[\x30-\x3f]'
    pattern=re.compile(b'(?=(.{3}'+high_bytes+b'.{3}'+high_bytes+b'))',re.DOTALL)
    report:Report={'schema_version':2,'mode':'dynamic','generation':generation,'pid':getattr(process,'pid',None),
            'process':getattr(process,'name',None),'bytes_scanned':0,'read_errors':0,
            'wrappers':0,'rejections':[],'candidates':[],'regions_scanned':0,
            'elapsed_seconds':0}
    start_time=time.monotonic();matches:dict[Discovery,int]={}
    def failed(message:str)->NoReturn:
        report['elapsed_seconds']=round(time.monotonic()-start_time,2)
        raise DiscoveryError(message,dict(report))
    for start,size in sorted(process.regions(),key=lambda r:r[1],reverse=True):
        if cancel and cancel():raise DiscoveryCancelled('Búsqueda cancelada por una nueva solicitud.')
        report['regions_scanned']+=1
        tail=b''
        for offset in range(0,size,4*1024**2):
            if cancel and cancel():raise DiscoveryCancelled('Búsqueda cancelada por una nueva solicitud.')
            if time.monotonic()-start_time>timeout or report['bytes_scanned']>=budget:
                failed('Búsqueda dinámica alcanzó su límite. Guarda diagnóstico.')
            length=min(4*1024**2,size-offset,budget-report['bytes_scanned'])
            try:data=process.read(start+offset,length)
            except (DiscoveryCancelled,DiscoveryLimit):raise
            except (OSError,DiscoveryError):report['read_errors']+=1;tail=b'';continue
            report['bytes_scanned']+=length;block=tail+data;begin=start+offset-len(tail)
            for match in pattern.finditer(block):
                position=begin+match.start()
                if position%4:continue
                pk,stats=struct.unpack('<II',match.group(1))
                if not 0<=stats-pk<=512:continue
                if time.monotonic()-start_time>timeout:failed('Búsqueda dinámica alcanzó su límite. Guarda diagnóstico.')
                report['wrappers']+=1
                anchor=position-68;guest=pk-128;base=anchor-(guest-start_addr)
                if not start_addr<=guest<end_addr-2914 or base<=0:continue
                try:
                    raw=process.read(anchor,2914)
                    party=decode_party(raw,max_species=721 if generation==6 else 807)
                    count=sum(p is not None for p in party)
                    if not party[0] or not count:continue
                    if struct.unpack_from('<I',raw,68)[0]!=pk:continue
                    if process.read(anchor,2914)!=raw:continue
                    matches[(base,guest)]=count
                except (DiscoveryCancelled,DiscoveryLimit):raise
                except (OSError,ValueError,DiscoveryError) as exc:
                    if len(report['rejections'])<16:report['rejections'].append(str(exc))
            tail=block[-7:]
            if progress:progress(f'Localizando RAM dinámica: {report["bytes_scanned"]//1024**2} MB · {len(matches)} equipos válidos')
    if matches:
        report['candidates']=[{'base':hex(base),'party':hex(guest),'pokemon':count}
                              for (base,guest),count in matches.items()]
        if len(matches)!=1:failed('Varias copias de equipo válidas. Guarda diagnóstico.')
        report['elapsed_seconds']=round(time.monotonic()-start_time,2)
        process.discovery_report=report
        return next(iter(matches))
    failed('No se encontró un equipo válido. Guarda diagnóstico.')


def game_hint_from_title(title:str|None)->str|None:
    """A UI hint only: never infer the current game from Pokémon origin data."""
    import unicodedata
    normalized=''.join(c for c in unicodedata.normalize('NFKD',title or '')
                       if not unicodedata.combining(c)).lower()
    for needles,game in (
        (('ultra moon','ultra luna'),'Ultra Moon 1.0'),
        (('ultra sun','ultra sol'),'Ultra Sun 1.0'),
        (('omega ruby','rubi omega'),'Omega Ruby 1.0'),
        (('alpha sapphire','zafiro alfa'),'Alpha Sapphire 1.0'),
        (('pokemon x',),'Pokémon X 1.0'),(('pokemon y',),'Pokémon Y 1.0')):
        if any(needle in normalized for needle in needles):return game
    return None


def window_titles()->dict[int,str]:
    if os.name!='nt':return {}
    titles:dict[int,str]={}
    user=C.WinDLL('user32',use_last_error=True)
    callback_type=C.WINFUNCTYPE(W.BOOL,W.HWND,W.LPARAM)
    user.GetWindowThreadProcessId.argtypes=[W.HWND,C.POINTER(W.DWORD)]
    user.GetWindowTextLengthW.argtypes=[W.HWND]
    user.GetWindowTextW.argtypes=[W.HWND,W.LPWSTR,C.c_int]
    user.EnumWindows.argtypes=[callback_type,W.LPARAM]
    def visit(hwnd:int,param:int)->bool:
        length=user.GetWindowTextLengthW(hwnd)
        if length:
            pid=W.DWORD();user.GetWindowThreadProcessId(hwnd,C.byref(pid))
            title=C.create_unicode_buffer(min(length+1,1025))
            user.GetWindowTextW(hwnd,title,len(title))
            # Prefer the running-game window over auxiliary settings dialogs.
            if pid.value not in titles or game_hint_from_title(title.value):
                titles[pid.value]=title.value
        return True
    callback=callback_type(visit);user.EnumWindows(callback,0)
    return titles


def process_metadata(process:WindowsProcess,titles:dict[int,str]|None=None)->Report:
    creation,exit_time,kernel,user=(W.FILETIME() for _ in range(4))
    creation_id=None
    if process.api.GetProcessTimes(process.handle,C.byref(creation),C.byref(exit_time),C.byref(kernel),C.byref(user)):
        creation_id=str((creation.dwHighDateTime<<32)|creation.dwLowDateTime)
    title=(window_titles() if titles is None else titles).get(process.pid,'')
    return {'pid':process.pid,'name':process.name,'title':title,
            'creation_id':creation_id,'game_hint':game_hint_from_title(title)}


def list_emulator_instances()->list[Report]:
    """Read-only enumeration; access-denied entries remain selectable by PID."""
    api=windows_api();titles=window_titles();result:list[Report]=[]
    for pid,name in list_lime_processes(api):
        title=titles.get(pid,'')
        metadata:Report={'pid':pid,'name':name,'title':title,'creation_id':None,
                  'game_hint':game_hint_from_title(title)}
        process:WindowsProcess|None=None
        try:
            process=WindowsProcess(pid)
            metadata=process_metadata(process,titles)
        except (DiscoveryError,OSError):pass
        finally:
            if process is not None:process.close()
        result.append(metadata)
    return result


class DiscoveryLimit(DiscoveryError):pass


class _ReadBudget:
    """One deadline and byte quota shared by cache, probes and slow fallback."""
    # Annotation only: set by _scan_dynamic_ram when the slow scan succeeds.
    discovery_report:Report
    def __init__(self,process:RegionReader,timeout:float,budget:int,cancel:Cancel)->None:
        self.process=process;self.started=time.monotonic();self.timeout=timeout
        self.budget=budget;self.cancel=cancel;self.bytes=0;self.reads=0
        self.pid=getattr(process,'pid',None);self.name=getattr(process,'name',None)
    def check(self)->None:
        if self.cancel and self.cancel():raise DiscoveryCancelled('Búsqueda cancelada por una nueva solicitud.')
        if time.monotonic()-self.started>=self.timeout:
            raise DiscoveryLimit('Búsqueda dinámica alcanzó su límite de tiempo. Guarda diagnóstico.')
    def regions(self)->Iterator[Region]:
        for region in self.process.regions():self.check();yield region
    def read(self,address:int,length:int)->bytes:
        self.check()
        if self.bytes+length>self.budget:
            raise DiscoveryLimit('Búsqueda dinámica alcanzó su límite de lectura. Guarda diagnóstico.')
        self.bytes+=length;self.reads+=1
        data=self.process.read(address,length)
        self.check()
        return data


CacheKey=tuple[int,str,int]
"""(PID, process creation identity, generation)."""
_DISCOVERY_CACHE:OrderedDict[CacheKey,Discovery]=OrderedDict()
_CACHE_LOCK=Lock()


def _cache_key(process:object,generation:int)->CacheKey|None:
    metadata=getattr(process,'metadata',None)
    if not isinstance(metadata,dict):return None
    identity=metadata.get('creation_id');pid=metadata.get('pid')
    # Without a proven process creation identity a PID is unsafe to reuse.
    if not identity or type(pid) is not int:return None
    return (pid,str(identity),generation)


def invalidate_discovery_cache(process:object,generation:int)->None:
    key=_cache_key(process,generation)
    if key is not None:
        with _CACHE_LOCK:_DISCOVERY_CACHE.pop(key,None)


def _validate_pair(process:MemoryReader,base:int,guest:int,generation:int)->bool:
    start,end=(0x08000000,0x10000000) if generation==6 else (LINEAR,LINEAR+256*1024**2)
    if base<=0 or not start<=guest<=end-2914:return False
    anchor=base+guest-start
    raw=process.read(anchor,2914)
    if struct.unpack_from('<I',raw,68)[0]!=guest+128:return False
    party=decode_party(raw,max_species=721 if generation==6 else 807)
    return bool(party[0] and process.read(anchor,2914)==raw)


def probe_region_ram(process:RegionReader,generation:int=7)->tuple[Discovery|None,Report]:
    """Try a bounded set of known layouts, requiring unique coherent data."""
    from .profiles import POKEMON_X_10,OMEGA_RUBY_10
    guest_start=0x08000000 if generation==6 else LINEAR
    known=(POKEMON_X_10.party_address,OMEGA_RUBY_10.party_address) if generation==6 else (PARTY,)
    guests=tuple(dict.fromkeys(a+d for a in known for d in (0,-128,128)))
    accepted:set[Discovery]=set();tested=0
    for start,size in sorted(process.regions(),key=lambda item:item[1],reverse=True):
        if not 16*1024**2<=size<=8*1024**3:continue
        for skew in (0,32,64,96,128,256,512,1024,2048,4096):
            for guest in guests:
                anchor=start+skew+guest-guest_start
                if not start<=anchor or anchor+2914>start+size:continue
                tested+=1
                try:
                    if _validate_pair(process,start+skew,guest,generation):accepted.add((start+skew,guest))
                except (DiscoveryCancelled,DiscoveryLimit):raise
                except (ValueError,OSError,DiscoveryError):continue
    report:Report={'mode':'region_probe','generation':generation,'anchors_tested':tested,
            'valid_candidates':len(accepted),'ambiguous':len(accepted)>1}
    if len(accepted)>1:raise DiscoveryError('Varias copias de equipo válidas. Guarda diagnóstico.',report)
    return (next(iter(accepted)) if accepted else None),report


def discover_dynamic_ram(process:RegionReader,progress:Progress=None,timeout:float=90,
                         budget:int=4*1024**3,cancel:Cancel=None,generation:int=7)->Discovery:
    if generation not in (6,7):raise ValueError('Generación inválida')
    if timeout<=0 or budget<=0:raise ValueError('Límites de búsqueda inválidos')
    bounded=_ReadBudget(process,timeout,budget,cancel);key=_cache_key(process,generation)
    source='region_probe';report:Report={}
    try:
        bounded.check()
        with _CACHE_LOCK:cached=_DISCOVERY_CACHE.get(key) if key else None
        found:Discovery|None=None
        if cached:
            try:
                if _validate_pair(bounded,*cached,generation):found=cached;source='cache'
            except (DiscoveryCancelled,DiscoveryLimit):raise
            except (ValueError,OSError,DiscoveryError):pass
            if found is None:invalidate_discovery_cache(process,generation)
        if found is None:found,report=probe_region_ram(bounded,generation)
        if found is None:
            source='dynamic_scan'
            if progress:progress('Sonda inicial sin coincidencias; buscando RAM…')
            found=_scan_dynamic_ram(bounded,progress,timeout,budget,cancel,generation)
            report=bounded.discovery_report
        bounded.check()
        if key:
            with _CACHE_LOCK:
                bounded.check()
                # Remove stale identities for the same reused PID.
                for old in list(_DISCOVERY_CACHE):
                    if old[0]==key[0] and old[1]!=key[1]:_DISCOVERY_CACHE.pop(old)
                _DISCOVERY_CACHE[key]=found;_DISCOVERY_CACHE.move_to_end(key)
                while len(_DISCOVERY_CACHE)>16:_DISCOVERY_CACHE.popitem(last=False)
        report.update(schema_version=3,mode='dynamic',source=source,generation=generation,
                      pid=getattr(process,'pid',None),process=getattr(process,'name',None),
                      bytes_scanned=bounded.bytes,read_calls=bounded.reads,
                      elapsed_seconds=round(time.monotonic()-bounded.started,4),
                      candidates=[{'base':hex(found[0]),'party':hex(found[1])}])
        bounded.check()
        process.discovery_report=report
        return found
    except DiscoveryCancelled:
        invalidate_discovery_cache(process,generation)
        raise
    except DiscoveryError as exc:
        invalidate_discovery_cache(process,generation)
        details=dict(exc.diagnostic or report)
        details.update(mode='dynamic',generation=generation,bytes_scanned=bounded.bytes,
                       read_calls=bounded.reads,elapsed_seconds=round(time.monotonic()-bounded.started,4))
        exc.diagnostic=details
        raise
