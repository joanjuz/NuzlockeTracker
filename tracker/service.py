"""Headless tracker: one memory worker, versioned JSON snapshots."""
import copy,json,os,queue,threading,time
from collections.abc import Callable
from typing import Any
from datetime import datetime, timezone
from dataclasses import replace
from pathlib import Path
from .process_memory import LimeProcessMemory,DiscoveryCancelled,list_emulator_instances
from .connectors import LimeGDB
from .profiles import capture_party, GameProfile, PROFILES, ULTRA_MOON_10, GEN6_GAMES
from .pokemon import decode_party
from .boxes import read_box,decode_box
from .catalog import Catalog
from .locations import location_name
from .reference import ReferenceData
from .progress import KEEP_CURRENT, LEVEL_CAP_ACTIONS, MAX_STAGES, RunProgress, level_caps_view, stage_list_export
from .level_caps_source import LevelCapsSource
from .battle import apply_battle_hp
from .battle_gen6 import apply_gen6_battle_hp
from .gen6_pc import Gen6BoxProbe
from .gen7_pc import Gen7BoxProbe
from .gen6_memory_scan import search_pc_memory
from .templates import TemplateManager
from .game_data import GameDataManager, TYPE_NAMES, STAT_KEYS, SOURCE as GAME_DATA_SOURCE
from . import diaglog

LOG=diaglog.get('service')
# Optional last stage offered with a Randomizer proposal: the ceiling of the patch, not one of its checkpoints.
FINAL_STAGE_NAME='Después del último punto (techo del parche)'

# Six decoded party slots (None = empty slot), as produced by decode_party().
Party=list[dict[str,Any]|None]

class TrackerService:
    def __init__(self,output,connector_factory=None):
        self.output=Path(output);self.catalog=Catalog();self.reference=ReferenceData();self.factory=connector_factory
        self.templates=TemplateManager(self.output.with_name('pk3ds-templates.json'),self.catalog)
        self.reference.template_moves=self.templates.data['moves']
        self.game_data=GameDataManager(self.output.with_name('definitive-game-data.json'))
        self.reference.game_data=self.game_data
        self.reference.game_provider=lambda:self.state['game']
        self.session_path=self.output.with_name('session-profile.json')
        self.condition=threading.Condition();self.commands=queue.Queue();self.stop=threading.Event();self.connection_generation=0;self.connection_lock=threading.Lock()
        # Disk problems are reported as a non-fatal warning and retried; they
        # must never stop the memory worker or drop in-memory history.
        self.state_save_error=None;self.session_save_error=None;self.persist_retry_at=0.0;self.last_internal_error=None
        # state.json is a restart cache: coalesce rapid HP changes into at most
        # one write per STATE_WRITE_INTERVAL. Deaths/progress are saved separately
        # and immediately by RunProgress.
        self.state_write_interval=1.0;self.last_state_write=0.0;self.state_dirty=False
        self.last_logged_connection=None;self.connection_log_times={}
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
                        self.state['box_verified']=saved.get('box_verified') is True
                        if type(saved.get('selected_box')) is int and 1<=saved['selected_box']<=32:
                            self.state['selected_box']=saved['selected_box']
        # A damaged local cache must never prevent the tracker from starting.
            except (OSError,ValueError,TypeError):
                pass
        suffix=self.progress_suffix(self.state['game'])
        self.open_progress(suffix)
        self.state['progress']=copy.deepcopy(self.progress.data)
        self.state['level_caps']=level_caps_view(self.progress.data)
        self.state['level_caps_source']=self.level_caps_source.view(self.state['level_caps']['revision'])
        self.profile=PROFILES[self.state['game']]
        self.reader=None;self.config=None;self.retry_at=0;self.scan_next=None;self.scan_verified=set();self.gen6_pending_boxes={};self.gen6_box_failed=False;self.gen6_probe=None;self.gen6_research_done=False;self.diagnostic=None;self.sun_box_base=None
        self.next_box_refresh_at=0.0;self.gen7_probe=None
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
        self.state['game_data']=self.game_data.status(self.state['game'])
        self.state['party']=[self.refresh_template(p) for p in self.state['party']]
        self.state['boxes']={k:[self.refresh_template(p) for p in box] for k,box in self.state['boxes'].items()}
        self.refresh_persist_warning()
    def open_progress(self,suffix):
        """Adventure record of one run and game, and the separate record of where its level caps came from."""
        self.progress=RunProgress(self.output.with_name(self.output.stem+suffix+'-progress.json'))
        self.level_caps_source=LevelCapsSource(self.output.with_name(self.output.stem+suffix+'-level-caps-source.json'))
    @staticmethod
    def progress_suffix(game):
        if game=='Ultra Moon 1.0':return ''
        if game=='Ultra Sun 1.0':return '-ultra-sun'
        if game in GEN6_GAMES:
            import re
            return '-'+re.sub(r'[^a-z0-9]+','-',game.casefold()).strip('-')
        raise ValueError('Juego fuera de los perfiles conocidos')

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
        result={'game':config['game'],'mode':config['mode'],'pid':pid,'port':port}
        identity=config.get('creation_id')
        if identity is not None:
            if not isinstance(identity,str) or not identity.isascii() or not identity.isdigit() or len(identity)>30:
                raise ValueError('Identidad de proceso inválida')
            result['creation_id']=identity
        return result

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
        game=self.state['game']
        imported=self.game_data.species(species,p.get('form',0),game)
        data.pop('game_data_source',None)
        data.pop('species_abilities',None)
        data['base_stats_source']='pk3DS Progressive'
        data['base_stats']=self.templates.data['stats'].get(str(species))
        if type(species) is int:
            data['types']=self.catalog.metadata('species',species).get('types',self.reference.pokemon_types(species,p.get('form',0)))
            data['type_source']='Catálogo ROM' if self.catalog.metadata('species',species).get('types') else 'Referencia USUM'
            data['species']=self.catalog.name('species',species)
        if 'ability_id' in p:data['ability']=self.catalog.name('abilities',p['ability_id'])
        if imported is not None:
            data['types']=list(dict.fromkeys(TYPE_NAMES[i] for i in imported['types']))
            data['type_source']=GAME_DATA_SOURCE
            data['species']=imported['name']
            data['base_stats']={label:imported['baseStats'][key] for key,label in STAT_KEYS.items()}
            data['base_stats_source']=GAME_DATA_SOURCE
            data['species_abilities']=[{'id':i,'name':self.game_data.ability_name(i,game) or self.catalog.name('abilities',i)} for i in imported['abilities']]
            data['game_data_source']=GAME_DATA_SOURCE
        if 'ability_id' in p:
            data['ability']=self.game_data.ability_name(p['ability_id'],game) or data['ability']
        evolutions=[]
        imported_evolutions=self.game_data.evolutions(species,p.get('form',0),game,self.catalog)
        for evo in imported_evolutions if imported_evolutions is not None else self.templates.evolutions(species,p.get('form',0)):
            target=evo['target']
            result_form=evo.get('target_form',0)
            target_record=self.game_data.species(target,result_form,game)
            name=target_record['name'] if target_record is not None else self.catalog.name('species',target)
            if target_record is None and result_form==1 and target in (20,26,28,38,51,53,75,76,89,103,105):
                name+=' de Alola'
            # PokeAPI maintains regional forms under distinct Pokémon IDs.
            regional_sprites={20:10092,26:10100,28:10102,38:10104,51:10106,53:10108,75:10110,76:10111,89:10113,103:10114,105:10115}
            evo_data={**evo,'target_name':name,'sprite_id':regional_sprites.get(target,target) if result_form==1 else target}
            evolutions.append(evo_data)
        data['evolutions']=evolutions
        moves=p.get('moves')
        if isinstance(moves,list) and len(moves)==4:
            data['analysis_moves']=[self.reference.move(i,self.catalog) if i else None for i in moves]
            data['move_names']=[(self.game_data.move(i,game) or {}).get('name',self.catalog.name('moves',i)) if i else '—' for i in moves]
        return data

    def preview_game_data(self,content,game):
        with self.condition:
            def compare(doc):
                differences=[]
                for row in doc['species']:
                    if len(differences)>=8:break
                    current=self.refresh_template({'species_id':row['speciesId'],'form':row['formId']})
                    after=list(dict.fromkeys(TYPE_NAMES[i] for i in row['types']))
                    if current.get('types')!=after:
                        differences.append({'record':f"Pokémon {row['speciesId']} · forma {row['formId']}",'field':'Tipos','before':current.get('types'),'after':after})
                    stats={label:row['baseStats'][key] for key,label in STAT_KEYS.items()}
                    if current.get('base_stats')!=stats:
                        differences.append({'record':f"Pokémon {row['speciesId']} · forma {row['formId']}",'field':'Estadísticas base','before':current.get('base_stats') or 'Sin estadísticas base importadas','after':stats})
                for row in doc['moves']:
                    if len(differences)>=14:break
                    if row['id']==0:continue
                    old=self.reference.move(row['id'],self.catalog)
                    after={k:row[k] for k in ('power','accuracy','pp','priority')}
                    after.update(type=TYPE_NAMES[row['typeId']],category=['Estado','Físico','Especial'][row['category']])
                    before={k:old.get(k) for k in after}
                    if before!=after:differences.append({'record':f"Movimiento {row['id']}",'field':'Propiedades','before':before,'after':after})
                for row in doc['evolutions']:
                    if len(differences)>=20:break
                    current=self.refresh_template({'species_id':row['speciesId'],'form':row['formId']})
                    before=[r['target'] for r in current['evolutions']]
                    differences.append({'record':f"Pokémon {row['speciesId']} · forma {row['formId']}",'field':'Rutas de evolución (incluye métodos y niveles del JSON)','before':before,'after':copy.deepcopy(row['routes'])})
                return differences
            return self.game_data.preview(content,game,compare)

    def _refresh_game_data(self):
        state=self.snapshot()
        self.update(party=[self.refresh_template(p) for p in state['party']],
                    boxes={k:[self.refresh_template(p) for p in members] for k,members in state['boxes'].items()},
                    game_data=self.game_data.status(state['game']))

    def apply_game_data(self,preview_token,game,acknowledge_unknown=False):
        with self.condition:
            self.game_data.apply(preview_token,game,acknowledge_unknown)
            self._refresh_game_data()
            return self.game_data.status(self.state['game'])

    def remove_game_data(self):
        with self.condition:
            self.game_data.remove(self.state['game'])
            self._refresh_game_data()
            return self.game_data.status(self.state['game'])

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

    def level_caps_export(self):
        """Shareable stage list (names, caps, order); raises ValueError when there is nothing to export."""
        return stage_list_export(self.snapshot().get('level_caps') or {})

    def diagnostic_export(self):
        state=self.snapshot()
        return {'schema_version':1,
                'created_at':datetime.now(timezone.utc).isoformat(),
                'game':state['game'],'connection':state['connection'],
                'log':diaglog.recent(200),
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
    def snapshot_fields(self,*keys):
        """Isolated copies of selected state keys only (missing keys omitted).

        Cheaper than snapshot(): it does not deep-copy all PC boxes.
        """
        with self.condition:
            return {k:copy.deepcopy(self.state[k]) for k in keys if k in self.state}
    def persist_warning_text(self):
        parts=[]
        recovered=getattr(self.progress,'recovered_from',None)
        if recovered=='backup':
            parts.append('El registro de la aventura estaba dañado; se restauró la copia .bak y el archivo dañado se conservó como .corrupt.')
        elif recovered=='empty':
            parts.append('El registro de la aventura estaba dañado y no había copia válida; se empezó un registro vacío. El archivo dañado se conservó como .corrupt.')
        if getattr(self.progress,'level_caps_isolated',False):
            parts.append('Los límites de nivel guardados de esta partida estaban dañados: se apartaron sin modificarlos y el resto del registro se cargó normalmente.')
        if getattr(self.progress,'dirty',False):
            parts.append('No se pudo guardar el progreso de la aventura: '+str(self.progress.last_save_error)+'. Se reintentará automáticamente.')
        if self.state_save_error:
            parts.append('No se pudo guardar state.json: '+self.state_save_error+'. Se reintentará automáticamente.')
        if self.session_save_error:
            parts.append('No se pudo guardar la sesión: '+self.session_save_error)
        return ' '.join(parts) or None
    def refresh_persist_warning(self):
        """Set/clear state['persist_warning']; True when it changed.

        Kept outside update()'s equality check so it can never loop.
        """
        with self.condition:
            warning=self.persist_warning_text()
            if self.state.get('persist_warning')==warning:return False
            if warning is None:
                self.state.pop('persist_warning',None);LOG.info('Guardado recuperado')
            else:
                self.state['persist_warning']=warning;LOG.warning('Aviso de guardado: %s',warning)
            return True
    def write_state(self):
        """Atomic state.json write with one quick retry; never raises OSError."""
        with self.condition:
            data=json.dumps({k:v for k,v in self.state.items() if k!='persist_warning'},ensure_ascii=False)
            temporary=self.output.with_suffix('.tmp');error=None
            for attempt in range(2):
                try:
                    self.output.parent.mkdir(parents=True,exist_ok=True)
                    temporary.write_text(data,encoding='utf-8');os.replace(temporary,self.output)
                    self.state_save_error=None
                    self.last_state_write=time.monotonic();self.state_dirty=False
                    return True
                except OSError as exc:
                    error=exc
                    if attempt==0:time.sleep(.05)
            try:temporary.unlink(missing_ok=True)
            except OSError:pass
            self.state_save_error=str(error)[:200]
            self.persist_retry_at=time.monotonic()+2.0
            return False
    def schedule_state_write(self):
        with self.condition:
            if time.monotonic()-self.last_state_write>=self.state_write_interval:self.write_state()
            else:self.state_dirty=True
    def flush_state(self,force=False):
        """Write a coalesced state.json when due (or now, when stopping)."""
        with self.condition:
            if not self.state_dirty:return False
            if not force and time.monotonic()-self.last_state_write<self.state_write_interval:return False
            return self.write_state()
    def retry_persistence(self):
        """Retry pending progress/state.json writes (throttled to every 2 s)."""
        with self.condition:
            if not (getattr(self.progress,'dirty',False) or self.state_save_error):return False
            if time.monotonic()<self.persist_retry_at:return False
            if not self.progress.flush():self.persist_retry_at=time.monotonic()+2.0
            if self.state_save_error:self.write_state()
            if self.refresh_persist_warning():
                self.state['revision']+=1;self.condition.notify_all()
            return True
    def update(self,**changes):
        with self.condition:
            if 'party' in changes and not changes.get('stale',self.state['stale']):
                self.progress.observe(changes['party'])
            if ('party' in changes or 'boxes' in changes) and not changes.get('stale',self.state['stale']):
                self.progress.remember(changes.get('party',self.state['party']),
                                       changes.get('boxes',self.state['boxes']))
            scan=changes.get('scan')
            box_count=31 if self.profile.generation==6 else 32
            if (isinstance(scan,dict) and scan.get('active') is False
                and scan.get('completed')==box_count and changes.get('box_verified') is True
                and self.scan_verified==set(range(1,box_count+1))
                and not changes.get('stale',self.state['stale'])
                and self.state['connection'].get('status')=='connected'):
                self.progress.observe_full_scan(changes.get('party',self.state['party']),
                                                changes.get('boxes',self.state['boxes']),
                                                box_count=box_count)
            changes['progress']=copy.deepcopy(self.progress.data)
            # Derived, read-only summary of the manual caps; RAM reading never uses it.
            changes['level_caps']=level_caps_view(self.progress.data)
            changes['level_caps_source']=self.level_caps_source.view(changes['level_caps']['revision'])
            changed=not all(self.state.get(k)==v for k,v in changes.items())
            if changed:
                self.log_transitions(changes)
                self.state.update(changes)
            warned=self.refresh_persist_warning()
            if not changed and not warned:return False
            # Publish to waiting readers first; a locked state.json (OneDrive,
            # antivirus) must not hide the live in-memory state.
            self.state['revision']+=1
            self.condition.notify_all()
            self.schedule_state_write()
            if self.refresh_persist_warning():
                self.state['revision']+=1;self.condition.notify_all()
            return True
    def log_transitions(self,changes):
        """Record only meaningful transitions; never full Pokémon data or secrets."""
        connection=changes.get('connection')
        if isinstance(connection,dict) and connection!=self.state.get('connection'):
            status=connection.get('status')
            # RAM search reports progress every 4 MB and failed reconnects repeat
            # every 3 s: log a transition once, then at most once a minute, so
            # the exported tail keeps the useful history.
            key=(status,'' if status=='connecting' else str(connection.get('message',''))[:200])
            now=time.monotonic()
            if key!=self.last_logged_connection and now-self.connection_log_times.get(key,-1e9)>=60:
                self.connection_log_times[key]=now
                if len(self.connection_log_times)>64:self.connection_log_times.clear()
                level=LOG.warning if status in ('error','retrying') else LOG.info
                level('Conexión: %s · %s',status,str(connection.get('message',''))[:200])
            self.last_logged_connection=key
        if 'game' in changes and changes['game']!=self.state.get('game'):
            LOG.info('Juego: %s',changes['game'])
        before=(self.state.get('progress') or {}).get('deaths') or {}
        after=(changes.get('progress') or {}).get('deaths') or {}
        for key in after.keys()-before.keys():
            record=after[key].get('pokemon') or {}
            LOG.info('Muerte registrada: %s (%s, origen %s)',record.get('species') or record.get('species_id'),
                     key,after[key].get('source','auto'))
        for key in before.keys()-after.keys():
            LOG.info('Muerte retirada (revivir): %s',key)
        failed=changes.get('last_command_error')
        if isinstance(failed,dict):
            LOG.warning('Comando %s rechazado: %s',failed.get('action'),failed.get('message'))
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
    def validate_process(self,metadata):
        if not isinstance(metadata,dict):
            if self.config.get('creation_id'):
                raise ValueError('No se pudo verificar la identidad del emulador. Selecciona el proceso de nuevo.')
            return
        hint=metadata.get('game_hint')
        if hint and hint!=self.config['game']:
            raise ValueError('El proceso seleccionado corresponde a '+hint+'. Selecciona el juego o proceso correcto.')
        expected=self.config.get('creation_id')
        if expected and metadata.get('creation_id')!=expected:
            raise ValueError('El proceso del emulador cambió. Selecciona el proceso de nuevo.')

    def connect(self):
        self.close_reader()
        # Refuse a known incompatible title or reused PID before scanning RAM.
        if not self.factory and self.config['mode']=='memory':
            try:instances=list_emulator_instances()
            except OSError:instances=[]
            selected=[m for m in instances if m['pid']==self.config.get('pid')]
            if not self.config.get('pid') and len(instances)==1:selected=instances
            if selected:self.validate_process(selected[0])
            elif self.config.get('creation_id'):
                raise ValueError('El proceso guardado ya no está disponible. Selecciona el proceso de nuevo.')
        profile=PROFILES[self.config.get('game','Ultra Moon 1.0')]
        if profile.name!=self.profile.name:
            self.profile=profile
            suffix=self.progress_suffix(profile.name)
            self.open_progress(suffix)
            self.update(game=profile.name,party=[None]*6,boxes={},stale=True)
            self._refresh_game_data()
        self.profile=profile;self.sun_box_base=None;self.gen7_probe=None
        self.scan_next=None;self.scan_verified=set();self.gen6_pending_boxes={};self.gen6_box_failed=False;self.gen6_probe=None;self.gen6_research_done=False
        self.update(connection={'status':'connecting','message':'Localizando RAM…'},stale=True,scan={'active':False,'completed':0})
        mode=self.config['mode']
        if self.factory:self.reader=self.factory(self.config)
        elif mode=='memory':
            generation=self.config.get('_connection_generation',self.connection_generation)
            # Both USUM games can relocate their party wrappers in Lime3DS.
            # Discover RAM independently of the selected game's display name;
            # selecting Ultra Sun must never be required to read Ultra Moon.
            self.reader=LimeProcessMemory(self.config.get('pid'),lambda msg:self.update(connection={'status':'connecting','message':msg}),dynamic=True,
                cancel=lambda:generation!=self.connection_generation or self.stop.is_set(),
                generation=self.profile.generation)
            self.profile=replace(self.profile,party_address=self.reader.party_address)
            self.diagnostic={'game':self.profile.name,
                             'party_address':hex(self.profile.party_address),
                             'discovery_mode':getattr(self.reader,'discovery_mode','unknown'),
                             'discovery':getattr(self.reader.process,'discovery_report',{})}
        else:
            self.reader=LimeGDB(self.config.get('port',24689));self.reader.identify();self.reader.resume()
        metadata=getattr(getattr(self.reader,'process',None),'metadata',None)
        try:self.validate_process(metadata)
        except ValueError:
            self.close_reader()
            raise
        if isinstance(metadata,dict):
            if type(metadata.get('pid')) is int:self.config['pid']=metadata['pid']
            if metadata.get('creation_id'):self.config['creation_id']=metadata['creation_id']
        # Gen6 box addresses are sourced from a third-party plugin, and must
        # pass complete, repeated encrypted PK6 validation before publication.
        # Validate a decoded team before reporting any Gen6 game as connected.
        if self.profile.generation==6:
            party=decode_party(capture_party(self.reader,self.profile),max_species=721)
            if not any(party):
                raise ValueError('No se detectó equipo PK6 válido. Abre una partida con al menos un Pokémon y guarda diagnóstico.')
            # Start reading PC only after the party was independently
            # verified. Subsequent full scans refresh every 180 seconds.
            self.scan_next=1
            self.next_box_refresh_at=time.monotonic()+180.0
        else:
            self.scan_next=1
            self.next_box_refresh_at=time.monotonic()+180.0
        self.update(connection={'status':'connected','message':('Gen6 · equipo conectado · 31 cajas con actualización automática' if self.profile.generation==6 else
            'Conectado · '+('Windows sin GDB' if mode=='memory' else 'GDB'))},
            box_verified=False,box_status='pending',
            scan={'active':True,'completed':0})
        # A locked session file must not tear down a healthy connection.
        try:
            self.save_session();self.session_save_error=None
        except OSError as exc:
            self.session_save_error=str(exc)[:200]
        if self.refresh_persist_warning():
            with self.condition:self.state['revision']+=1;self.condition.notify_all()
    # ------------------------------------------------------------------
    # Memory polling. poll() runs once per worker tick: read the party,
    # merge battle HP, advance at most one PC box and publish one update().
    # Every access goes through self.reader.read(); nothing is ever written.
    # ------------------------------------------------------------------
    def poll(self) -> None:
        party=self._read_party()
        if self.profile.generation==6:
            self._poll_gen6(party)
        else:
            self._poll_gen7(party)

    def _cancel_predicate(self,generation:int)->Callable[[],bool]:
        """Cancel PC work when the connection changes or the worker stops."""
        return lambda:generation!=self.connection_generation or self.stop.is_set()

    def _read_party(self)->Party|None:
        """Decode and enrich the overworld team.

        Gen6 overworld party may be temporarily unavailable or stale while
        the game is in battle (the battle roster is verified separately), so
        an invalid Gen6 snapshot yields None. Gen7 errors propagate.
        """
        try:
            return [self.enrich(p) for p in decode_party(capture_party(self.reader,self.profile),
                    max_species=721 if self.profile.generation==6 else 807)]
        except ValueError:
            if self.profile.generation!=6:raise
            return None

    # -- Gen6 X/Y/ORAS -------------------------------------------------
    def _poll_gen6(self,party:Party|None)->None:
        saved=self.snapshot_fields('party','stale','box_verified')
        party,gen6_battle=self._gen6_battle_party(party,saved)
        # Keep memory snapshots isolated and reject apparently valid but
        # inconsistent RAM instead of guessing a PC base from empty bytes.
        changes:dict[str,Any]={'party':party,'stale':False,'battle_hp':gen6_battle}
        if self.scan_next is not None:
            changes.update(self._gen6_scan_step(saved))
        else:
            changes['connection']=self._gen6_idle_connection(saved)
        self.update(**changes)
        if self.diagnostic is not None:
            self.diagnostic.update(box_status=('verified' if self.snapshot_fields('box_verified').get('box_verified') else 'unverified_gen6'),
                box_address=hex(self.profile.box_address),validated_team_slots=sum(p is not None for p in party),
                battle_hp=gen6_battle)

    def _gen6_battle_party(self,party:Party|None,saved:dict[str,Any])->tuple[Party,bool]:
        """Merge verified Gen6 battle HP; raise ValueError if no team is usable."""
        if not party or not any(party):
            previous=saved.get('party',[]) if not saved.get('stale',True) else []
            if not previous or not any(previous):
                raise ValueError('Equipo PK6 temporalmente no disponible.')
            party,gen6_battle=apply_gen6_battle_hp(
                self.reader,previous,self.profile.name,self.profile.party_address,self.diagnostic)
            if not gen6_battle:
                raise ValueError('Equipo PK6 temporalmente no disponible; esperando regreso.')
            return party,gen6_battle
        party,gen6_battle=apply_gen6_battle_hp(
            self.reader,party,self.profile.name,self.profile.party_address,self.diagnostic)
        # If the overworld mirror changes during combat, compare
        # against last verified team. Never trust a stored party alone:
        # the complete runtime battle roster/HP must validate as well.
        if not gen6_battle and not saved.get('stale',True) and any(saved.get('party',[])):
            previous,in_battle=apply_gen6_battle_hp(
                self.reader,saved['party'],self.profile.name,self.profile.party_address)
            if in_battle:party,gen6_battle=previous,True
        return party,gen6_battle

    def _gen6_scan_step(self,saved:dict[str,Any])->dict[str,Any]:
        """Read the next of the 31 Gen6 boxes; finish the scan after box 31."""
        number=self.scan_next
        if self.gen6_probe is None:
            original=PROFILES[self.profile.name].party_address
            shift=self.profile.party_address-original
            generation=(self.config or {}).get('_connection_generation',self.connection_generation)
            self.gen6_probe=Gen6BoxProbe(self.profile.box_address,shift,
                cancel=self._cancel_predicate(generation))
            if self.diagnostic is not None:
                self.diagnostic['gen6_party_shift']=shift
        self.gen6_probe.read(self.reader,number)
        done=number==31
        self.scan_next=None if done else number+1
        changes:dict[str,Any]={'scan':{'active':not done,'completed':number}}
        if done:
            changes.update(self._gen6_finish_scan(saved))
        return changes

    def _gen6_finish_scan(self,saved:dict[str,Any])->dict[str,Any]:
        """Publish the 31 boxes only for a unique validated PC base."""
        chosen,verified_boxes=self.gen6_probe.finish()
        if self.diagnostic is not None:
            self.diagnostic['gen6_box_candidates']=self.gen6_probe.diagnostic()
        if chosen is None and not self.gen6_research_done:
            self.gen6_research_done=True
            found,discovered=self._gen6_search_pc()
            if found is not None:
                chosen,verified_boxes=found,discovered
        changes:dict[str,Any]={}
        if chosen is not None:
            changes['boxes']={k:[self.enrich(p) for p in box]
                for k,box in verified_boxes.items()}
            changes['box_verified']=True
            self.scan_verified=set(range(1,32))
            self.profile=replace(self.profile,box_address=chosen)
        else:
            self.scan_verified=set()
            changes['box_verified']=bool(saved.get('box_verified',False))
        changes['connection']={'status':'connected','message':(
            'Gen6 experimental · equipo y 31 cajas PK6 verificadas · PS combate experimental'
            if chosen is not None else
            'Gen6 experimental · equipo válido; cajas no verificadas (prueba con Pokémon depositado)')}
        self.gen6_probe=None
        self.next_box_refresh_at=time.monotonic()+180.0
        return changes

    def _gen6_search_pc(self)->tuple[int|None,dict[str,list[dict[str,Any]|None]]|None]:
        """Bounded read-only PC search; cancellation propagates, other errors are reported."""
        try:
            generation=(self.config or {}).get('_connection_generation',self.connection_generation)
            found,discovered,search_report=search_pc_memory(
                self.reader,PROFILES[self.profile.name].box_address,
                cancel=self._cancel_predicate(generation))
            if self.diagnostic is not None:
                self.diagnostic['gen6_box_search']=search_report
            return found,discovered
        except DiscoveryCancelled:raise
        except (ValueError,ConnectionError,OSError) as exc:
            if self.diagnostic is not None:
                self.diagnostic['gen6_box_search']={
                    'error':str(exc)[:120]}
            return None,None

    @staticmethod
    def _gen6_idle_connection(saved:dict[str,Any])->dict[str,str]:
        return {'status':'connected','message':(
            'Gen6 experimental · equipo y cajas PK6 · PS combate experimental'
            if saved.get('box_verified') else
            'Gen6 experimental · equipo válido, cajas no verificadas')}

    # -- Gen7 USUM -----------------------------------------------------
    def _poll_gen7(self,party:Party)->None:
        party,in_battle=apply_battle_hp(self.reader,party,self.profile.name)
        saved=self.snapshot_fields('box_verified','selected_box','box_status')
        changes:dict[str,Any]={'party':party,'stale':False,'battle_hp':in_battle}
        if self.scan_next is not None:
            changes.update(self._gen7_scan_step())
        elif saved.get('box_verified') and self.sun_box_base is not None:
            changes.update(self._gen7_refresh_selected_box(saved))
        status=changes.get('box_status',saved.get('box_status','pending'))
        changes['connection']=self._gen7_connection(status)
        if self.diagnostic is not None:
            self.diagnostic.update(box_address=hex(self.profile.box_address),box_status=status,
                box_verified=changes.get('box_verified',saved.get('box_verified',False)),battle_hp=in_battle)
        self.update(**changes)

    @staticmethod
    def gen7_box_candidates(profile:GameProfile)->tuple[int,...]:
        """USUM PC bases to probe: profile base, Moon base and Moon base shifted like the party."""
        delta=profile.party_address-ULTRA_MOON_10.party_address
        return tuple(a for a in (profile.box_address,ULTRA_MOON_10.box_address,
                     ULTRA_MOON_10.box_address+delta) if 0x30000000<=a<=0x40000000-32*6960)

    def _gen7_scan_step(self)->dict[str,Any]:
        """Read the next of the 32 USUM boxes; finish the scan after box 32."""
        number=self.scan_next
        if self.gen7_probe is None:
            self.gen7_probe=Gen7BoxProbe(self.gen7_box_candidates(self.profile),
                cancel=self._cancel_predicate(self.connection_generation))
        self.gen7_probe.read(self.reader,number)
        done=number==32
        self.scan_next=None if done else number+1
        changes:dict[str,Any]={'box_verified':False,'box_status':'pending',
                               'scan':{'active':not done,'completed':number}}
        if done:
            changes.update(self._gen7_finish_scan())
        return changes

    def _gen7_finish_scan(self)->dict[str,Any]:
        """Publish the 32 boxes only for a unique populated PC candidate."""
        chosen,boxes=self.gen7_probe.finish()
        changes:dict[str,Any]={'box_status':self.gen7_probe.status}
        if self.diagnostic is not None:
            self.diagnostic['gen7_box_candidates']=self.gen7_probe.diagnostic()
        if chosen is not None:
            changes['boxes']={k:[self.enrich(p) for p in box] for k,box in boxes.items()}
            changes['box_verified']=True
            self.scan_verified=set(range(1,33))
            self.sun_box_base=chosen
            self.profile=replace(self.profile,box_address=chosen)
        else:self.scan_verified=set()
        self.gen7_probe=None
        self.next_box_refresh_at=time.monotonic()+180.0
        return changes

    def _gen7_refresh_selected_box(self,saved:dict[str,Any])->dict[str,Any]:
        """Re-read only the selected box once the whole PC layout was verified."""
        number=saved['selected_box']
        try:
            raw=read_box(self.reader,number,self.sun_box_base)
            if raw!=read_box(self.reader,number,self.sun_box_base):
                raise ValueError('La caja cambió entre lecturas')
            members=decode_box(raw)
            # Shallow copy: only this box gets a fresh list; the other
            # box lists are never mutated in place.
            with self.condition:boxes=dict(self.state.get('boxes') or {})
            boxes[str(number)]=[self.enrich(p) for p in members]
            return {'boxes':boxes}
        except DiscoveryCancelled:raise
        except (ValueError,ConnectionError,OSError):
            self.scan_next=1;self.gen7_probe=None
            return {'box_verified':False,'box_status':'invalid',
                    'scan':{'active':True,'completed':0}}

    _GEN7_MESSAGES:dict[str,str]={
        'verified':'equipo y 32 cajas verificadas',
        'pending':'equipo conectado; verificando cajas',
        'pending_empty':'equipo conectado; cajas pendientes (deposita un Pokémon)',
        'ambiguous':'equipo conectado; varias copias de PC, cajas pendientes',
        'invalid':'equipo conectado; cajas pendientes de una lectura válida'}

    @classmethod
    def _gen7_connection(cls,status:str)->dict[str,str]:
        return {'status':'connected','message':'Conectado · '+cls._GEN7_MESSAGES.get(status,cls._GEN7_MESSAGES['pending'])}

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
        elif action=='route_trade':
            self.set_route_trade(cmd)
        elif action=='set_origin':
            self.set_origin(cmd)
        elif action=='mark_route':
            self.mark_route(cmd)
        elif action=='clear_route_mark':
            self.clear_route_mark(cmd)
        elif action in LEVEL_CAP_ACTIONS:
            self.apply_level_caps(cmd)
        elif action=='connect':self.config=cmd;self.retry_at=0;self.scan_next=None;self.connect()
        elif action=='disconnect':
            self.gen7_probe=None
            self.config=None;self.scan_next=None;self.gen6_pending_boxes={};self.gen6_probe=None;self.close_reader();self.update(connection={'status':'disconnected','message':'Desconectado'},stale=True,scan={'active':False,'completed':0})
        elif action=='box':self.update(selected_box=cmd['number'])
        elif action=='scan':
            if not self.reader:raise ValueError('Conecta el tracker antes de leer las cajas.')
            self.scan_verified=set();self.gen6_pending_boxes={};self.gen6_box_failed=False;self.gen6_probe=None;self.gen6_research_done=False
            self.gen7_probe=None
            self.scan_next=1;self.update(box_verified=False,box_status='pending',scan={'active':True,'completed':0})
        elif action=='cancel':self.scan_next=None;self.gen6_probe=None;self.gen7_probe=None;self.update(scan={'active':False,'completed':self.snapshot_fields('scan')['scan']['completed']})
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
    def validate_route_mark(self,cmd,undo=False):
        from .progress import pokemon_key, ORIGIN_KEY_PATTERN
        key=cmd.get('key')
        if not isinstance(key,str) or ORIGIN_KEY_PATTERN.fullmatch(key) is None:
            raise ValueError('Clave del Pokémon inválida')
        if undo:
            if key not in self.progress.data['route_marks']:
                raise ValueError('No existe una marca para quitar')
            return key, None
        kind=cmd.get('kind')
        if kind not in ('trade','fossil'):
            raise ValueError('Selecciona Fósil o Intercambiado')
        state=self.snapshot()
        roster=[*state.get('party',[]),
                *(p for box in state.get('boxes',{}).values() for p in box)]
        match=next((p for p in roster if isinstance(p,dict) and
                    p.get('checksum_valid') is True and pokemon_key(p)==key),None)
        if match is None:
            # The Pokémon may have left via trade AFTER the last valid scan.
            saved=self.progress.data['encounters'].get(key)
            if saved is None:
                raise ValueError('No hay ningún encuentro registrado con esa clave')
            match={**saved,'checksum_valid':True}
        return key, match

    def mark_route(self,cmd):
        key, pokemon=self.validate_route_mark(cmd)
        kind=cmd['kind']
        changed=self.progress.mark_route(pokemon,kind)
        if kind=='fossil':
            changed=self.progress.set_origin(pokemon,'fossil') or changed
        if changed:
            self.update()

    def clear_route_mark(self,cmd):
        key,_=self.validate_route_mark(cmd,undo=True)
        kind=self.progress.data['route_marks'][key]['kind']
        changed=self.progress.clear_route_mark(key)
        if kind=='fossil' and self.progress.data['origins'].get(key)=='fossil':
            member={**self.progress.data['encounters'].get(key,{})}
            if member and self.progress.set_origin(member,'auto'):
                changed=True
        if changed:
            self.update()

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
        from .progress import pokemon_key
        key=pokemon_key(target)
        changed=self.progress.set_origin(target,cmd['category'])
        if cmd['category']!='fossil' and self.progress.data['route_marks'].get(key,{}).get('kind')=='fossil':
            changed=self.progress.clear_route_mark(key) or changed
        if changed:
            self.update()

    def validate_route_trade(self,cmd):
        ids={str(r['id']) for r in self.reference.routes(self.state['game'])['routes']}
        if cmd.get('route') not in ids or type(cmd.get('traded')) is not bool:
            raise ValueError('Ruta o estado Intercambiado inválido')

    def set_route_trade(self,cmd):
        self.validate_route_trade(cmd)
        if self.progress.set_traded_route(cmd['route'],cmd['traded']):
            self.update()

    def validate_level_caps(self,cmd):
        """Check a level-caps command against the current run without changing anything."""
        action=cmd.get('action')
        if action=='level_caps_set':
            self.progress.check_level_caps(cmd.get('stages'),cmd['current'] if 'current' in cmd else KEEP_CURRENT)
        elif action=='level_caps_current':
            if 'stage' not in cmd:raise ValueError('Falta la etapa vigente.')
            self.progress.check_current_stage(cmd['stage'])
        elif action=='level_caps_show':
            if type(cmd.get('show')) is not bool:raise ValueError('Opción de mostrar los límites inválida.')
            self.progress.check_level_caps_editable()
        elif action=='level_caps_accept_proposal':
            self.level_caps_proposal_stages(cmd)
        elif action=='level_caps_dismiss_proposal':
            if type(cmd.get('dismissed')) is not bool:raise ValueError('Indica si la propuesta se descarta o se recupera.')
            self.level_caps_proposal(cmd)
            self.level_caps_source.check_writable()
        else:
            raise ValueError('Acción de límites de nivel inválida')
    def level_caps_proposal(self,cmd):
        """The Randomizer proposal the command refers to; ValueError when it is not the one loaded now.

        The command names the game, the imported data and the patch table it was reviewed against, so a
        confirmation given for another run, game or file can never be applied to this one.
        """
        game=self.state['game']
        manager=getattr(self,'game_data',None)
        proposal=manager.level_caps(game) if manager is not None else None
        if not proposal or proposal['state']!='proposal':
            raise ValueError('No hay una propuesta de límites de Definitive Randomizer para esta partida y juego.')
        if (cmd.get('game')!=game or cmd.get('dataFingerprint')!=manager.status(game)['fingerprint']
                or cmd.get('capsFingerprint')!=proposal['fingerprint'] or cmd.get('tableSha256')!=proposal['tableSha256']):
            raise ValueError('La propuesta que revisaste ya no es la vigente: cambió la partida, el juego o los datos importados. Vuelve a revisarla.')
        return proposal
    def level_caps_proposal_stages(self,cmd):
        """Stages an accepted proposal would save, checked against the list that was reviewed. Changes nothing."""
        proposal=self.level_caps_proposal(cmd)
        if type(cmd.get('finalStage')) is not bool:raise ValueError('Indica si se añade la etapa final de nivel 100.')
        self.progress.check_level_caps_editable()
        view=level_caps_view(self.progress.data)
        if cmd.get('listRevision')!=view['revision']:
            raise ValueError('Las etapas de la partida cambiaron mientras revisabas la propuesta. Vuelve a revisarla.')
        if view['stages'] and cmd.get('replace') is not True:
            raise ValueError('Confirma que quieres reemplazar las etapas actuales de la partida.')
        stages=[dict(stage) for stage in proposal['stages']]
        if cmd['finalStage']:
            # Derived from the ceiling of the patch, never one of its checkpoints; only on request.
            stages.append({'name':FINAL_STAGE_NAME,'cap':proposal['ceiling']})
        if len(stages)>MAX_STAGES:
            raise ValueError(f'La propuesta con la etapa final tendría {len(stages)} etapas; el máximo es {MAX_STAGES}. No se recorta.')
        self.progress.check_level_caps(stages)
        self.level_caps_source.check_writable()
        return proposal,stages
    def accept_level_caps_proposal(self,cmd):
        proposal,stages=self.level_caps_proposal_stages(cmd)
        status=self.game_data.status(self.state['game'])
        # No current stage is chosen: every stage is new, so the previous current one (if any) is only reported.
        self.progress.set_level_caps(stages)
        view=level_caps_view(self.progress.data)
        try:
            self.level_caps_source.record_accept({'source':'definitive-game-data','blockVersion':1,
                'producer':{'id':status['producer']['id'],'version':status['producer']['version']},
                'game':self.state['game'],'dataFingerprint':status['fingerprint'],'capsFingerprint':proposal['fingerprint'],
                'tableSha256':proposal['tableSha256'],'checkpoints':proposal['count'],'finalStage':cmd['finalStage'],
                'listRevision':view['revision']})
        except OSError as exc:
            self.update()
            raise ValueError('Las etapas se reemplazaron, pero no se pudo guardar su procedencia: '+str(exc)[:160]) from exc
        return True
    def apply_level_caps(self,cmd):
        # Validated again here: the run may have changed since the HTTP check.
        self.validate_level_caps(cmd)
        action=cmd['action']
        if action=='level_caps_accept_proposal':
            changed=self.accept_level_caps_proposal(cmd)
        elif action=='level_caps_dismiss_proposal':
            proposal=self.level_caps_proposal(cmd)
            changed=self.level_caps_source.record_dismiss(proposal['fingerprint'],proposal['tableSha256'] if cmd['dismissed'] else None)
        elif action=='level_caps_set':
            changed=self.progress.set_level_caps(cmd['stages'],cmd['current'] if 'current' in cmd else KEEP_CURRENT)
        elif action=='level_caps_current':
            changed=self.progress.set_current_stage(cmd['stage'])
        else:
            changed=self.progress.set_level_caps_shown(cmd['show'])
        if changed:
            self.update()
    def validate_route_miss(self,cmd):
        ids={str(r['id']) for r in self.reference.routes(self.state['game'])['routes']}
        if cmd.get('route') not in ids or type(cmd.get('missed')) is not bool:
            raise ValueError('Ruta o estado Miss inválido')
    def set_route_miss(self,cmd):
        self.validate_route_miss(cmd)
        self.progress.set_miss(cmd['route'],cmd['missed'])
        self.update()
    def handle_command(self,cmd):
        """User commands report their own errors; they are not connection errors."""
        if isinstance(cmd,dict) and cmd.get('action')=='connect':
            # Connection failures keep the connection status/retry handling.
            self.handle(cmd);return
        try:self.handle(cmd)
        except (ValueError,KeyError,TypeError,OSError) as exc:
            message=str(exc) if isinstance(exc,(ValueError,OSError)) and str(exc) else 'Comando inválido'
            self.update(last_command_error={'message':message,'at':time.time(),
                                            'action':cmd.get('action') if isinstance(cmd,dict) else None})
    def guarded(self,handler,*args):
        """Run an error handler without letting it escape the worker loop."""
        try:handler(*args)
        except Exception as exc:
            self.last_internal_error=repr(exc)[:200]
            LOG.exception('Fallo interno en %s',getattr(handler,'__name__','manejador'))
    def on_cancelled(self):
        self.close_reader();self.scan_next=None;self.retry_at=0
    def on_value_error(self,exc):
        # Without a reader this is a failed connection attempt: wait before
        # enumerating processes again instead of retrying every second.
        if not self.reader:self.retry_at=time.monotonic()+3
        # A torn RAM snapshot must not tear down a healthy transport.
        self.update(connection={'status':'connected' if self.reader else 'error','message':str(exc)},stale=True)
    def on_failure(self,exc):
        LOG.warning('Lectura interrumpida (%s): %s',type(exc).__name__,str(exc)[:200])
        details=getattr(exc,'diagnostic',None) or {}
        self.diagnostic={'game':self.profile.name,'mode':(self.config or {}).get('mode'),
                         'error':str(exc),**details}
        self.close_reader();self.scan_next=None;self.retry_at=time.monotonic()+3
        self.update(connection={'status':'retrying' if self.config else 'error','message':str(exc)},stale=True,scan={'active':False,'completed':0})
    def run(self):
        while not self.stop.is_set():
            try:
                try:cmd=self.commands.get(timeout=.15)
                except queue.Empty:cmd=None
                if cmd is not None:self.handle_command(cmd)
                if self.config and not self.reader and time.monotonic()>=self.retry_at:self.connect()
                if self.reader:
                    if self.scan_next is None and time.monotonic()>=self.next_box_refresh_at:
                        self.scan_next=1
                        self.next_box_refresh_at=time.monotonic()+180.0
                        self.update(scan={'active':True,'completed':0})
                    self.poll()
            except DiscoveryCancelled:
                self.guarded(self.on_cancelled)
            except ValueError as exc:
                self.guarded(self.on_value_error,exc)
            except Exception as exc:
                self.guarded(self.on_failure,exc)
            self.guarded(self.retry_persistence)
            self.guarded(self.flush_state)
            self.stop.wait(.35 if self.scan_next else .85)
        self.close_reader()
        self.guarded(self.flush_state,True)
