"""Headless tracker: one memory worker, versioned JSON snapshots."""
import copy,json,os,queue,threading,time
from datetime import datetime, timezone
from dataclasses import replace
from pathlib import Path
from .process_memory import LimeProcessMemory,DiscoveryCancelled
from .connectors import LimeGDB
from .profiles import capture_party, PROFILES, ULTRA_MOON_10
from .pokemon import decode_party
from .boxes import read_box,decode_box
from .catalog import Catalog
from .locations import location_name
from .reference import ReferenceData
from .progress import RunProgress
from .battle import apply_battle_hp
from .templates import TemplateManager

class TrackerService:
    def __init__(self,output,connector_factory=None):
        self.output=Path(output);self.catalog=Catalog();self.reference=ReferenceData();self.factory=connector_factory
        self.templates=TemplateManager(self.output.with_name('pk3ds-templates.json'),self.catalog)
        self.reference.template_moves=self.templates.data['moves']
        self.session_path=self.output.with_name('session-profile.json')
        self.condition=threading.Condition();self.commands=queue.Queue();self.stop=threading.Event();self.connection_generation=0;self.connection_lock=threading.Lock()
        self.state={'schema_version':1,'revision':0,'game':'Ultra Moon 1.0','connection':{'status':'disconnected','message':'Conecta con la partida cargada.'},'party':[None]*6,'boxes':{},'selected_box':1,'scan':{'active':False,'completed':0},'stale':True}
        # Restore the last known party AND boxes after a restart. They remain
        # stale and can never be mistaken for a live emulator reading.
        if self.output.is_file():
            try:
                saved=json.loads(self.output.read_text(encoding='utf-8'))
                if isinstance(saved,dict) and saved.get('game') in PROFILES and isinstance(saved.get('boxes'),dict):
                    boxes=saved['boxes']
                    if len(boxes)<=32 and all(isinstance(k,str) and k.isdigit() and 1<=int(k)<=32 and isinstance(v,list) and len(v)==30 and all(m is None or isinstance(m,dict) for m in v) for k,v in boxes.items()):
                        self.state['game']=saved['game']
                        self.state['boxes']=copy.deepcopy(boxes)
                        party=saved.get('party')
                        if isinstance(party,list) and len(party)==6 and all(mon is None or isinstance(mon,dict) and type(mon.get('species_id')) is int and 1<=mon['species_id']<=807 for mon in party):
                            self.state['party']=copy.deepcopy(party)
                        self.state['box_verified']=saved.get('box_verified') is not False
                        if type(saved.get('selected_box')) is int and 1<=saved['selected_box']<=32:
                            self.state['selected_box']=saved['selected_box']
        # A damaged local cache must never prevent the tracker from starting.
            except (OSError,ValueError,TypeError):
                pass
        suffix='-ultra-sun' if self.state['game']=='Ultra Sun 1.0' else ''
        self.progress=RunProgress(self.output.with_name(self.output.stem+suffix+'-progress.json'))
        self.state['progress']=copy.deepcopy(self.progress.data)
        self.profile=PROFILES[self.state['game']]
        self.reader=None;self.config=None;self.retry_at=0;self.scan_next=None;self.diagnostic=None;self.sun_box_base=None
        self.next_box_refresh_at=0.0
        # Companion credentials already persist independently. Restore the emulator
        # selection without requiring the user to re-pair on every launch.
        if self.session_path.is_file():
            try:
                saved=json.loads(self.session_path.read_text(encoding='utf-8'))
                if saved.get('schema_version')==1:
                    self.config=self.valid_connection(saved.get('connection'))
            except (OSError, ValueError, AttributeError):
                pass
        self.state['session_saved']=self.session_path.is_file() and self.config is not None
        self.state['templates']=self.templates.status()
        self.state['party']=[self.refresh_template(p) for p in self.state['party']]
        self.state['boxes']={k:[self.refresh_template(p) for p in box] for k,box in self.state['boxes'].items()}
    @staticmethod
    def valid_connection(config):
        if not isinstance(config,dict) or config.get('game') not in PROFILES or config.get('mode') not in ('memory','gdb'):
            raise ValueError('Configuración de conexión no válida')
        pid=config.get('pid')
        port=config.get('port',24689)
        if pid is not None and (type(pid) is not int or not 1<=pid<=2**32-1):
            raise ValueError('PID inválido')
        if type(port) is not int or not 1<=port<=65535:
            raise ValueError('Puerto GDB inválido')
        return {'game':config['game'],'mode':config['mode'],'pid':pid,'port':port}

    def save_session(self):
        if not self.config:
            raise ValueError('Conecta primero un juego para guardar esta sesión')
        data={'schema_version':1,'connection':self.valid_connection(self.config)}
        self.session_path.parent.mkdir(parents=True,exist_ok=True)
        tmp=self.session_path.with_suffix('.tmp')
        tmp.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
        os.replace(tmp,self.session_path)
        self.update(session_saved=True)

    def refresh_template(self,p):
        if not isinstance(p,dict):return p
        data=dict(p)
        species=p.get('species_id')
        data['base_stats']=self.templates.data['stats'].get(str(species))
        evolutions=[]
        for evo in self.templates.evolutions(species,p.get('form',0)):
            target=evo['target']
            result_form=evo.get('target_form',0)
            name=self.catalog.name('species',target)
            if result_form==1 and target in (20,26,28,38,51,53,75,76,89,103,105):
                name+=' de Alola'
            # PokeAPI maintains regional forms under distinct Pokémon IDs.
            regional_sprites={20:10092,26:10100,28:10102,38:10104,51:10106,53:10108,75:10110,76:10111,89:10113,103:10114,105:10115}
            evo_data={**evo,'target_name':name,'sprite_id':regional_sprites.get(target,target) if result_form==1 else target}
            evolutions.append(evo_data)
        data['evolutions']=evolutions
        moves=p.get('moves')
        if isinstance(moves,list) and len(moves)==4:
            data['analysis_moves']=[self.reference.move(i,self.catalog) if i else None for i in moves]
        return data

    def import_templates(self, files):
        result=self.templates.import_csv(files)
        self.reference.template_moves=self.templates.data['moves']
        state=self.snapshot()
        party=[self.refresh_template(p) for p in state['party']]
        boxes={k:[self.refresh_template(p) for p in members] for k,members in state['boxes'].items()}
        self.update(party=party,boxes=boxes,templates=result)
        return result

    def session_export(self):
        """Portable user-selected backup: local Pokémon/progress only, no cloud tokens."""
        state=self.snapshot()
        return {
            'schema_version':1,
            'exported_at':datetime.now(timezone.utc).isoformat(),
            'game':state['game'],
            'party':copy.deepcopy(state.get('party') or [None]*6),
            'boxes':copy.deepcopy(state.get('boxes') or {}),
            'progress':copy.deepcopy(state.get('progress') or {}),
            'selected_box':state.get('selected_box',1),
            'box_verified':state.get('box_verified',False),
        }

    def diagnostic_export(self):
        state=self.snapshot()
        return {'schema_version':1,
                'created_at':datetime.now(timezone.utc).isoformat(),
                'game':state['game'],'connection':state['connection'],
                'diagnostic':copy.deepcopy(self.diagnostic) if self.diagnostic else
                              {'message':'No hay un diagnóstico de conexión disponible.'}}

    def save_diagnostic(self):
        """Write a diagnostic without relying on WebView2's download support.

        Never include ROM bytes, save games, partner tokens or other secrets.
        """
        data=self.diagnostic_export()
        folder=self.output.parent / 'diagnosticos'
        folder.mkdir(parents=True,exist_ok=True)
        name='diagnostico_'+datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')+'.json'
        path=folder / name
        tmp=folder / (name+'.tmp')
        try:
            tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
            os.replace(tmp,path)
        finally:
            if tmp.exists():
                tmp.unlink()
        return str(path.resolve())

    def request_connection_change(self):
        with self.connection_lock:
            self.connection_generation+=1
            return self.connection_generation
    def snapshot(self):
        with self.condition:return copy.deepcopy(self.state)
    def update(self,**changes):
        with self.condition:
            if 'party' in changes and not changes.get('stale',self.state['stale']):
                self.progress.observe(changes['party'])
            changes['progress']=copy.deepcopy(self.progress.data)
            if all(self.state.get(k)==v for k,v in changes.items()):return False
            self.state.update(changes);self.state['revision']+=1
            self.output.parent.mkdir(parents=True,exist_ok=True)
            temporary=self.output.with_suffix('.tmp');temporary.write_text(json.dumps(self.state,ensure_ascii=False),encoding='utf-8');os.replace(temporary,self.output)
            self.condition.notify_all();return True
    def enrich(self,p):
        if p is None:return None
        p=dict(p);p['types']=self.catalog.metadata('species',p['species_id']).get('types',self.reference.pokemon_types(p['species_id'],p.get('form',0)))
        p['type_source']='Catálogo ROM' if self.catalog.metadata('species',p['species_id']).get('types') else 'Referencia USUM'
        p['analysis_moves']=[self.reference.move(m,self.catalog) if m else None for m in p['moves']]
        p['species']=self.catalog.name('species',p['species_id'])
        p['ability']=self.catalog.name('abilities',p['ability_id']);p['item']=self.catalog.name('items',p['item_id'])
        p['met_location']=location_name(p.get('met_location_id',0),p.get('origin_version',33))
        p['egg_location']=location_name(p.get('egg_location_id',0),p.get('origin_version',33))
        p['move_names']=[self.catalog.name('moves',m) if m else '—' for m in p['moves']]
        return self.refresh_template(p)
    def close_reader(self):
        if self.reader:
            try:self.reader.close()
            except Exception:pass
        self.reader=None
    def connect(self):
        self.close_reader()
        profile=PROFILES[self.config.get('game','Ultra Moon 1.0')]
        if profile.name!=self.profile.name:
            self.profile=profile
            suffix='-ultra-sun' if profile.name=='Ultra Sun 1.0' else ''
            self.progress=RunProgress(self.output.with_name(self.output.stem+suffix+'-progress.json'))
            self.update(game=profile.name,party=[None]*6,boxes={},stale=True)
        self.profile=profile;self.sun_box_base=None
        self.update(connection={'status':'connecting','message':'Localizando RAM…'},stale=True,scan={'active':False,'completed':0})
        mode=self.config['mode']
        if self.factory:self.reader=self.factory(self.config)
        elif mode=='memory':
            generation=self.config.get('_connection_generation',self.connection_generation)
            self.reader=LimeProcessMemory(self.config.get('pid'),lambda msg:self.update(connection={'status':'connecting','message':msg}),dynamic=self.profile.name=='Ultra Sun 1.0',cancel=lambda:generation!=self.connection_generation or self.stop.is_set())
            self.profile=replace(self.profile,party_address=self.reader.party_address)
            self.diagnostic={'game':self.profile.name,
                             'party_address':hex(self.profile.party_address),
                             'discovery_mode':getattr(self.reader,'discovery_mode','unknown'),
                             'discovery':getattr(self.reader.process,'discovery_report',{})}
        else:
            self.reader=LimeGDB(self.config.get('port',24689));self.reader.identify();self.reader.resume()
        # Start a complete box scan as soon as a game is connected.
        # Refresh periodically to detect changes made while playing.
        self.scan_next=1
        self.next_box_refresh_at=time.monotonic()+180.0
        self.update(connection={'status':'connected','message':'Conectado · '+('Windows sin GDB' if mode=='memory' else 'GDB')},scan={'active':True,'completed':0})
        self.save_session()
    def poll(self):
        party=[self.enrich(p) for p in decode_party(capture_party(self.reader,self.profile))]
        party,in_battle=apply_battle_hp(self.reader,party,self.profile.name)
        number=self.scan_next or self.snapshot()['selected_box']
        boxes=self.snapshot()['boxes'];box_verified=True
        if self.profile.name=='Ultra Sun 1.0' or getattr(self.reader,'discovery_mode',None)=='dynamic':
            # Dynamic RAM relocation can affect box addresses on Azahar/Citra
            # for Ultra Moon too. Probe both offsets, never assume static RAM.
            box_verified=False
            # Test the old and equally shifted addresses, accepting only real PK7 records.
            delta=self.profile.party_address-ULTRA_MOON_10.party_address
            for address in dict.fromkeys([self.sun_box_base] if self.sun_box_base else [self.profile.box_address,ULTRA_MOON_10.box_address+delta]):
                try:raw_box=decode_box(read_box(self.reader,number,address))
                except (ValueError,OSError,ConnectionError):continue
                if any(raw_box) or self.sun_box_base==address:
                    self.sun_box_base=address
                    self.profile=replace(self.profile,box_address=address)
                    boxes[str(number)]=[self.enrich(p) for p in raw_box];box_verified=True;break
        else:
            boxes[str(number)]=[self.enrich(p) for p in decode_box(read_box(self.reader,number,self.profile.box_address))]
        changes={'party':party,'boxes':boxes,'stale':False,'battle_hp':in_battle,'box_verified':box_verified}
        if self.snapshot()['connection']['status']!='connected' or self.snapshot()['stale']:
            changes['connection']={'status':'connected','message':'Conectado · '+('Windows sin GDB' if (self.config or {}).get('mode','memory')=='memory' else 'GDB')}
        if self.scan_next:
            changes['scan']={'active':number<32,'completed':number};self.scan_next=number+1 if number<32 else None
        if self.diagnostic is not None:self.diagnostic.update(box_address=hex(self.profile.box_address),box_verified=box_verified,battle_hp=in_battle)
        self.update(**changes)
    def handle(self,cmd):
        action=cmd['action']
        if action=='save_session':
            self.save_session()
        elif action=='mark_dead':
            self.mark_dead(cmd)
        elif action=='revive':
            self.revive(cmd)
        elif action=='route_miss':
            self.set_route_miss(cmd)
        elif action=='set_origin':
            self.set_origin(cmd)
        elif action=='connect':self.config=cmd;self.retry_at=0;self.scan_next=None;self.connect()
        elif action=='disconnect':
            self.config=None;self.scan_next=None;self.close_reader();self.update(connection={'status':'disconnected','message':'Desconectado'},stale=True,scan={'active':False,'completed':0})
        elif action=='box':self.update(selected_box=cmd['number'])
        elif action=='scan':
            if not self.reader:raise ValueError('Conecta el tracker antes de leer las cajas.')
            self.scan_next=1;self.update(scan={'active':True,'completed':0})
        elif action=='cancel':self.scan_next=None;self.update(scan={'active':False,'completed':self.snapshot()['scan']['completed']})
    def validate_mark_dead(self,cmd):
        key=cmd.get('key')
        if cmd.get('source','manual') not in ('manual','soullink-response'):
            raise ValueError('Origen de muerte inválido')
        if not isinstance(key,str) or len(key)>64:
            raise ValueError('Pokémon inválido para marcar muerte')
        state=self.snapshot()
        members=[*state.get('party',[]),*(p for box in state.get('boxes',{}).values() for p in box)]
        from .progress import pokemon_key
        target=next((p for p in members if p and pokemon_key(p)==key and not p.get('egg') and p.get('checksum_valid') is True),None)
        if target is None:
            raise ValueError('No se encontró el Pokémon en tu equipo o cajas guardadas')
        if key in self.progress.data['deaths']:
            raise ValueError('Ese Pokémon ya está registrado en Muertos')
        return target
    def mark_dead(self,cmd):
        target=self.validate_mark_dead(cmd)
        if self.progress.mark_dead(target,source=cmd.get('source','manual')):
            self.update()

    def validate_revive(self,cmd):
        key=cmd.get('key')
        if not isinstance(key,str) or len(key)>64 or key not in self.progress.data['deaths'] and key not in self.progress.data['revived_pending']:
            raise ValueError('Pokémon no registrado en Muertos')
    def revive(self,cmd):
        self.validate_revive(cmd)
        if type(cmd.get('decrement_counter',False)) is not bool:
            raise ValueError('Opción de contador inválida')
        self.progress.revive(cmd['key'],cmd.get('decrement_counter',False))
        snapshot=self.snapshot()
        # A healed, current party member can be rearmed immediately.
        self.update(party=snapshot['party'],stale=snapshot['stale'])
    def validate_set_origin(self,cmd):
        """Only annotate a known member; never allow arbitrary cache injection."""
        from .progress import ORIGIN_CATEGORIES, pokemon_key
        key=cmd.get('key')
        category=cmd.get('category')
        if not isinstance(key,str) or not 1<=len(key)<=64:
            raise ValueError('Identidad de Pokémon inválida')
        if category!='auto' and category not in ORIGIN_CATEGORIES:
            raise ValueError('Categoría de obtención inválida')
        state=self.snapshot()
        members=[*state.get('party',[]),
                 *(p for box in state.get('boxes',{}).values() for p in box),
                 *(entry.get('pokemon') for entry in (state.get('progress',{}).get('deaths',{}) or {}).values()
                   if isinstance(entry,dict))]
        target=next((p for p in members if isinstance(p,dict) and pokemon_key(p)==key
                     and p.get('checksum_valid') is True),None)
        if target is None:
            raise ValueError('Pokémon no encontrado en equipo, cajas o Muertos')
        return target

    def set_origin(self,cmd):
        target=self.validate_set_origin(cmd)
        if self.progress.set_origin(target,cmd['category']):
            self.update()

    def validate_route_miss(self,cmd):
        ids={str(r['id']) for r in self.reference.routes(self.state['game'])['routes']}
        if cmd.get('route') not in ids or type(cmd.get('missed')) is not bool:
            raise ValueError('Ruta o estado Miss inválido')
    def set_route_miss(self,cmd):
        self.validate_route_miss(cmd)
        self.progress.set_miss(cmd['route'],cmd['missed'])
        self.update()
    def run(self):
        while not self.stop.is_set():
            try:
                try:cmd=self.commands.get(timeout=.15);self.handle(cmd)
                except queue.Empty:pass
                if self.config and not self.reader and time.monotonic()>=self.retry_at:self.connect()
                if self.reader:
                    if self.scan_next is None and time.monotonic()>=self.next_box_refresh_at:
                        self.scan_next=1
                        self.next_box_refresh_at=time.monotonic()+180.0
                        self.update(scan={'active':True,'completed':0})
                    self.poll()
            except DiscoveryCancelled:
                self.close_reader();self.scan_next=None;self.retry_at=0
            except ValueError as exc:
                # A torn RAM snapshot must not tear down a healthy transport.
                self.update(connection={'status':'connected' if self.reader else 'error','message':str(exc)},stale=True)
            except Exception as exc:
                details=getattr(exc,'diagnostic',None) or {}
                self.diagnostic={'game':self.profile.name,'mode':(self.config or {}).get('mode'),
                                 'error':str(exc),**details}
                self.close_reader();self.scan_next=None;self.retry_at=time.monotonic()+3
                self.update(connection={'status':'retrying' if self.config else 'error','message':str(exc)},stale=True,scan={'active':False,'completed':0})
            self.stop.wait(.35 if self.scan_next else .85)
        self.close_reader()
