"""Windows read-only 3DS emulator connector (experimental on Azahar/Citra)."""
import ctypes as C
from ctypes import wintypes as W
import os,struct,time
from .pokemon import decode_party
from .boxes import decode_box,BOX_BASE,BOX_SIZE
PARTY=0x33F7FA44
LINEAR=0x30000000
SIGNATURE_OFFSET=68
NEEDLE=struct.pack('<III',PARTY+128,PARTY+472,PARTY+408)

class DiscoveryError(ConnectionError):
    def __init__(self,message,diagnostic=None):
        super().__init__(message);self.diagnostic=diagnostic

class DiscoveryCancelled(ConnectionError):
    pass

class ProcessEntry(C.Structure):
    _fields_=[('dwSize',W.DWORD),('cntUsage',W.DWORD),('th32ProcessID',W.DWORD),('th32DefaultHeapID',C.c_size_t),('th32ModuleID',W.DWORD),('cntThreads',W.DWORD),('th32ParentProcessID',W.DWORD),('pcPriClassBase',W.LONG),('dwFlags',W.DWORD),('szExeFile',W.WCHAR*260)]
class MemoryInfo(C.Structure):
    _fields_=[('BaseAddress',C.c_void_p),('AllocationBase',C.c_void_p),('AllocationProtect',W.DWORD),('PartitionId',W.WORD),('RegionSize',C.c_size_t),('State',W.DWORD),('Protect',W.DWORD),('Type',W.DWORD)]

def windows_api():
    if os.name!='nt' or C.sizeof(C.c_void_p)!=8:raise DiscoveryError('Este conector requiere Windows y Python de 64 bits.')
    api=C.WinDLL('kernel32',use_last_error=True)
    for name,args,result in [
        ('CreateToolhelp32Snapshot',[W.DWORD,W.DWORD],W.HANDLE),
        ('Process32FirstW',[W.HANDLE,C.POINTER(ProcessEntry)],W.BOOL),
        ('Process32NextW',[W.HANDLE,C.POINTER(ProcessEntry)],W.BOOL),
        ('OpenProcess',[W.DWORD,W.BOOL,W.DWORD],W.HANDLE),
        ('CloseHandle',[W.HANDLE],W.BOOL),
        ('ReadProcessMemory',[W.HANDLE,C.c_void_p,C.c_void_p,C.c_size_t,C.POINTER(C.c_size_t)],W.BOOL),
        ('VirtualQueryEx',[W.HANDLE,C.c_void_p,C.POINTER(MemoryInfo),C.c_size_t],C.c_size_t),
        ('GetExitCodeProcess',[W.HANDLE,C.POINTER(W.DWORD)],W.BOOL)]:
        fn=getattr(api,name);fn.argtypes=args;fn.restype=result
    return api

def supported_emulator(name):
    """Process-name discovery only; RAM layout must still validate per emulator."""
    if not isinstance(name, str):
        return False
    value = name.lower()
    return value.endswith('.exe') and value.startswith(('lime3ds', 'azahar', 'citra'))


def list_lime_processes(api):
    handle=api.CreateToolhelp32Snapshot(2,0)
    if handle in (None,C.c_void_p(-1).value):raise C.WinError(C.get_last_error())
    entries=[]
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
    def __init__(self,pid=None):
        self.api=windows_api();processes=list_lime_processes(self.api)
        if pid is not None:
            processes=[p for p in processes if p[0]==pid]
        if not processes:raise DiscoveryError('No se encontró Lime3DS, Azahar ni Citra. Abre un emulador y carga la partida.')
        if len(processes)>1:raise DiscoveryError('Hay varios emuladores abiertos. Introduce el PID: '+', '.join(str(p[0]) for p in processes))
        self.pid,self.name=processes[0]
        # VirtualQueryEx requires PROCESS_QUERY_INFORMATION (0x0400), while
        # ReadProcessMemory requires PROCESS_VM_READ (0x0010). Do not request
        # PROCESS_ALL_ACCESS or attempt to bypass Windows security.
        self.handle=self.api.OpenProcess(0x0400|0x0010,False,self.pid)
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
    def read(self,address,length):
        buffer=C.create_string_buffer(length);received=C.c_size_t()
        ok=self.api.ReadProcessMemory(self.handle,C.c_void_p(address),buffer,length,C.byref(received))
        if not ok or received.value!=length:raise DiscoveryError(f'No se pudo leer memoria del proceso (error {C.get_last_error()}).')
        return buffer.raw
    def regions(self):
        address=0
        while address<0x7fffffffffff:
            info=MemoryInfo()
            if not self.api.VirtualQueryEx(self.handle,C.c_void_p(address),C.byref(info),C.sizeof(info)):break
            base,size=info.BaseAddress or 0,info.RegionSize
            if size==0 or base+size<=address:break
            # Committed, readable, no guard; exclude code/image mappings.
            if info.State==0x1000 and not info.Protect&0x100 and info.Protect&0xff in (2,4,8,32,64,128) and info.Type in (0x20000,0x40000):yield base,size
            address=base+size
    def alive(self):
        code=W.DWORD()
        return bool(self.handle and self.api.GetExitCodeProcess(self.handle,C.byref(code)) and code.value==259)
    def close(self):
        if self.handle:self.api.CloseHandle(self.handle);self.handle=None

def validate_anchor(process,anchor):
    data=process.read(anchor,2914)
    if data[SIGNATURE_OFFSET:SIGNATURE_OFFSET+4]!=NEEDLE[:4]:raise DiscoveryError('Firma de equipo inválida.')
    party=decode_party(data)
    if not any(p is not None for p in party):raise DiscoveryError('No hay Pokémon para validar la RAM.')
    base=anchor-(PARTY-LINEAR)
    if base<=0:raise DiscoveryError('Base de RAM inválida.')
    decode_box(process.read(base+(BOX_BASE-LINEAR),BOX_SIZE))
    return base

def discover_ram(process,progress=None,timeout=60,budget=4*1024**3,cancel=None):
    started=time.monotonic();scanned=0;matches=[]
    regions=sorted(process.regions(),key=lambda r:r[1],reverse=True)
    report={'schema_version':1,'pid':getattr(process,'pid',None),'process':getattr(process,'name',None),
            'readable_regions':len(regions),'readable_bytes':sum(size for _,size in regions),
            'regions_scanned':0,'bytes_scanned':0,'read_errors':0,'signatures_found':0,
            'rejections':[],'elapsed_seconds':0,'candidates':[]}
    def fail(message):
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
    def __init__(self,pid=None,progress=None,dynamic=False,cancel=None):
        self.process=WindowsProcess(pid);self.base=None;self.party_address=PARTY
        try:
            if dynamic:self.base,self.party_address=discover_dynamic_ram(self.process,progress,cancel=cancel)
            else:self.base=discover_ram(self.process,progress,cancel=cancel)
        except Exception:self.process.close();raise
    def identify(self):return f'Windows · PID {self.process.pid} · RAM localizada'
    def resume(self):pass # No debugger: does not pause or resume the emulator.
    def read(self,address,length):
        if not LINEAR<=address or address+length>LINEAR+256*1024**2 or not 1<=length<=65536:raise ValueError('Lectura fuera de la RAM lineal permitida.')
        if not self.process.alive():raise DiscoveryError('El emulador se cerró.')
        # Signature catches a cleared/moved RAM allocation after an internal restart.
        if self.process.read(self.base+getattr(self,'party_address',PARTY)-LINEAR+SIGNATURE_OFFSET,4)!=struct.pack('<I',getattr(self,'party_address',PARTY)+128):
            raise DiscoveryError('Partida reiniciada o RAM trasladada. Esperando para localizarla nuevamente.')
        return self.process.read(self.base+address-LINEAR,length)
    def close(self):self.process.close()


def discover_dynamic_ram(process,progress=None,timeout=90,budget=4*1024**3,cancel=None):
    """Find self-referencing party wrappers without assuming the guest party address."""
    import re
    # Two nearby guest pointers; secondary wrapper offsets may differ.
    # Validate the self-reference and the complete decoded party.
    pattern=re.compile(rb'(?=(.{3}[\x30-\x3f].{3}[\x30-\x3f]))',re.DOTALL)
    report={'schema_version':2,'mode':'dynamic','bytes_scanned':0,'read_errors':0,'wrappers':0,'rejections':[],'candidates':[]}
    start_time=time.monotonic();matches={}
    for start,size in sorted(process.regions(),key=lambda r:r[1],reverse=True):
        if cancel and cancel():raise DiscoveryCancelled('Búsqueda cancelada por una nueva solicitud.')
        tail=b''
        for offset in range(0,size,4*1024**2):
            if cancel and cancel():raise DiscoveryCancelled('Búsqueda cancelada por una nueva solicitud.')
            if time.monotonic()-start_time>timeout or report['bytes_scanned']>=budget:
                raise DiscoveryError('Búsqueda dinámica alcanzó su límite. Guarda diagnóstico.',report)
            length=min(4*1024**2,size-offset,budget-report['bytes_scanned'])
            try:data=process.read(start+offset,length)
            except (OSError,DiscoveryError):report['read_errors']+=1;tail=b'';continue
            report['bytes_scanned']+=length;block=tail+data;begin=start+offset-len(tail)
            for match in pattern.finditer(block):
                position=begin+match.start()
                if position%4:continue
                pk,stats=struct.unpack('<II',match.group(1))
                if not 0<=stats-pk<=512:continue
                if time.monotonic()-start_time>timeout:raise DiscoveryError('Búsqueda dinámica alcanzó su límite. Guarda diagnóstico.',report)
                report['wrappers']+=1
                anchor=position-68;guest=pk-128;base=anchor-(guest-LINEAR)
                if not LINEAR<=guest<LINEAR+256*1024**2-2914 or base<=0:continue
                try:
                    raw=process.read(anchor,2914);party=decode_party(raw)
                    count=sum(p is not None for p in party)
                    if not party[0] or not count:continue
                    if struct.unpack_from('<I',raw,68)[0]!=pk:continue
                    matches[(base,guest)]=count
                except (OSError,ValueError,DiscoveryError) as exc:
                    if len(report['rejections'])<16:report['rejections'].append(str(exc))
            tail=block[-7:]
            if progress:progress(f'Localizando RAM dinámica: {report["bytes_scanned"]//1024**2} MB · {len(matches)} equipos válidos')
        if matches:
            best=max(matches.values());choices=[key for key,count in matches.items() if count==best]
            report['candidates']=[{'base':hex(base),'party':hex(guest),'pokemon':count} for (base,guest),count in matches.items()]
            if len(choices)!=1:raise DiscoveryError('Varias copias de equipo válidas. Guarda diagnóstico.',report)
            process.discovery_report=report
            return choices[0]
    raise DiscoveryError('No se encontró un equipo válido. Guarda diagnóstico.',report)
