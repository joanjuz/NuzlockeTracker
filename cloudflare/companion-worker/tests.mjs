import test from 'node:test';
import assert from 'node:assert/strict';
import { DatabaseSync } from 'node:sqlite';
import { readFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import worker from './src/index.mjs';

class Stmt {
  constructor(stmt, db){this.stmt=stmt;this.db=db;this.args=[]}
  bind(...args){this.args=args;return this}
  first(){return this.stmt.get(...this.args)??null}
  run(){return this.stmt.run(...this.args)}
}
class D1Mock {
  constructor(){this.db=new DatabaseSync(':memory:');this.db.exec('PRAGMA foreign_keys=ON;');this.db.exec(readFileSync(new URL('./migrations/0001_schema.sql', import.meta.url),'utf8'))}
  prepare(query){return new Stmt(this.db.prepare(query),this)}
  async batch(stmts){this.batches=(this.batches||[]);this.batches.push(stmts.length);this.db.exec('BEGIN');try{const values=stmts.map(s=>s.run());this.db.exec('COMMIT');return values}catch(e){this.db.exec('ROLLBACK');throw e}}
}
const env={DB:new D1Mock(),CREATE_KEY:'setup-secret-for-tests-12345'};
function call(path,method='GET',body,headers={}){
  return worker.fetch(new Request('https://localhost'+path,{method,headers:{...headers,...(body!==undefined?{'Content-Type':'application/json'}:{})},body:body===undefined?undefined:JSON.stringify(body)}),env);
}
const bearer=t=>({'Authorization':'Bearer '+t});

test('pair, join same game, save and retrieve last session, revoke',async()=>{
  let res=await call('/v1/pairs','POST',{name:'Sol',game:'Ultra Sun 1.0'},{'X-Setup-Key':env.CREATE_KEY});
  assert.equal(res.status,201);const owner=await res.json();
  assert.equal((await call('/v1/partner','GET',undefined,bearer(owner.token))).status,200);
  // Two Ultra Sun players are now allowed, just like Sun/Moon or Moon/Moon.
  res=await call('/v1/pairs/join','POST',{name:'Luna',game:'Ultra Sun 1.0',invite_code:owner.invite_code});
  assert.equal(res.status,201);const guest=await res.json();
  const obj={schema_version:1,game:'Ultra Sun 1.0',party:[{species_id:448,nickname:'Lucario'} ,null,null,null,null,null],
    boxes:{},progress:{deaths:{},missed_routes:[]},battle_hp:false};
  res=await call('/v1/state','PUT',{state:obj},bearer(guest.token));assert.equal(res.status,200);
  res=await call('/v1/partner','GET',undefined,bearer(owner.token));assert.equal(res.status,200);
  let partner=(await res.json()).partner;
  assert.equal(partner.name,'Luna');assert.equal(partner.state.party[0].species_id,448);
  res=await call('/v1/state','PUT',{state:{...obj,game:'Ultra Moon 1.0'}},bearer(guest.token));assert.equal(res.status,400);
  res=await call('/v1/state','PUT',{state:obj},bearer('badtoken'));assert.equal(res.status,401);
  res=await call('/v1/pairs/join','POST',{name:'Luna2',game:'Ultra Sun 1.0',invite_code:owner.invite_code});assert.equal(res.status,409);
  res=await call('/v1/leave','POST',{},bearer(owner.token));assert.equal(res.status,200);
  res=await call('/v1/partner','GET',undefined,bearer(guest.token));assert.equal(res.status,401);
});

test('health, rejects unauthorized pair creation and malformed state',async()=>{
  let r=await call('/health');assert.equal(r.status,200);
  r=await call('/v1/pairs','POST',{name:'Other',game:'Ultra Sun 1.0'},{'X-Setup-Key':'wrong'});
  assert.equal(r.status,403);
  r=await call('/v1/pairs','POST',{name:'Other',game:'Ultra Sun 1.0'},{'X-Setup-Key':env.CREATE_KEY});
  assert.equal(r.status,201);
  const owner=await r.json();
  r=await call('/v1/state','PUT',{state:{party:[null]}},bearer(owner.token));
  assert.equal(r.status,400);
});


test('all six games pair and retain generation bounds and member game binding', async()=>{
  const games=['Pokémon X 1.0','Pokémon Y 1.0','Omega Ruby 1.0','Alpha Sapphire 1.0','Ultra Sun 1.0','Ultra Moon 1.0'];
  for (const [index, game] of games.entries()) {
    const gen6=index<4, maxBoxes=gen6?31:32, maxSpecies=gen6?721:807;
    let res=await call('/v1/pairs','POST',{name:'Host',game},{'X-Setup-Key':env.CREATE_KEY});
    assert.equal(res.status,201,game); const owner=await res.json();
    const peerGame=games[(index+1)%games.length];
    res=await call('/v1/pairs/join','POST',{name:'Peer',game:peerGame,invite_code:owner.invite_code});
    assert.equal(res.status,201,peerGame); const guest=await res.json();
    const obj={schema_version:1,game,party:[{species_id:maxSpecies,nickname:'Ultimo'},null,null,null,null,null],
      boxes:Object.fromEntries(Array.from({length:maxBoxes},(_,n)=>[String(n+1),Array(30).fill(null)])),
      progress:{deaths:{},missed_routes:[]},battle_hp:false};
    res=await call('/v1/state','PUT',{state:obj},bearer(owner.token)); assert.equal(res.status,200,game);
    res=await call('/v1/partner','GET',undefined,bearer(guest.token));
    const received=(await res.json()).partner;
    assert.equal(received.game,game); assert.equal(received.state.party[0].species_id,maxSpecies);
    assert.equal(Object.keys(received.state.boxes).length,maxBoxes);
    res=await call('/v1/state','PUT',{state:obj},bearer(guest.token)); assert.equal(res.status,400,'member binding');
    obj.boxes[String(maxBoxes+1)]=Array(30).fill(null);
    res=await call('/v1/state','PUT',{state:obj},bearer(owner.token)); assert.equal(res.status,400,'extra box');
    delete obj.boxes[String(maxBoxes+1)]; obj.party[0].species_id=maxSpecies+1;
    res=await call('/v1/state','PUT',{state:obj},bearer(owner.token)); assert.equal(res.status,400,'future species');
    res=await call('/v1/leave','POST',{},bearer(owner.token)); assert.equal(res.status,200);
  }
  const invalid=await call('/v1/pairs','POST',{name:'Unknown',game:'unsupported'},{'X-Setup-Key':env.CREATE_KEY});
  assert.equal(invalid.status,400);
});

const HOSTILE='<img src=x onerror=alert(1)>';
// Full record with the shape tracker/service.py enrich() produces.
const fullMon=()=>({species_id:637,species:'Volcarona',nickname:'Botella',slot:1,level:100,hp:304,max_hp:304,
  stats:{ATQ:211,DEF:153,VEL:249,ATE:317,DEE:224},ability:'Cuerpo Llama',item:'Restos',
  move_names:['Escaldar','Aerochorro','Danza Llama','—'],moves:[503,177,552,0],nature:'Firme',
  iv:[31,30,25,31,28,26],ev:[4,252,0,252,0,0],met_location:'Ruta 1',met_location_id:8,met_level:5,
  met_date:'2026-10-08',egg_location:'Sin lugar registrado',egg_location_id:0,origin_version:33,
  encryption_constant:4294967295,egg:false,form:0,type_source:'Referencia USUM',types:['Bicho','Fuego'],
  ability_id:49,item_id:234,move_pp:[15,5,10,0],move_pp_ups:[0,0,0,0],
  base_stats:{HP:85,ATK:60,DEF:65,SPA:135,SPD:105,SPE:100},
  evolutions:[{target:637,method:'Subir de nivel al nivel 59',raw_method:'4',form:-1,source:'pk3DS Progressive',
    item:'Piedra Fuego',target_form:0,target_name:'Volcarona',sprite_id:637}]});
const fullState=game=>({schema_version:1,game,party:[fullMon(),null,null,null,null,null],
  boxes:{'1':[{...fullMon(),level:null,hp:null,max_hp:null,stats:null,met_date:null},...Array(29).fill(null)]},
  progress:{deaths:{'33:1':{pokemon:fullMon(),recorded_at:'2026-10-09T10:00:00',source:'soullink-response'}},
    missed_routes:['10'],death_count:1,origins:{'33:1':'fossil'},
    route_marks:{'33:2':{kind:'trade',pokemon:{species_id:25,species:'Pikachu',nickname:'Pika',origin_version:33,
      encryption_constant:7,met_location_id:8,met_location:'Ruta 1'}}},traded_routes:['8']},battle_hp:true});
async function freshPair(game='Ultra Sun 1.0'){
  const r=await call('/v1/pairs','POST',{name:'Host',game},{'X-Setup-Key':env.CREATE_KEY});
  assert.equal(r.status,201);return r.json();
}

test('full tracker record (party, boxes with null stats, deaths, route marks) is accepted',async()=>{
  const owner=await freshPair();
  const res=await call('/v1/state','PUT',{state:fullState('Ultra Sun 1.0')},bearer(owner.token));
  assert.equal(res.status,200);
  await call('/v1/leave','POST',{},bearer(owner.token));
});

test('snapshot produced by the Python companion is accepted by the Worker',async(t)=>{
  const root=fileURLToPath(new URL('../../',import.meta.url));
  const script=['import json,sys,tempfile','from pathlib import Path','from tracker.demo import DemoService',
    'from companion.snapshot import snapshot','with tempfile.TemporaryDirectory() as d:',
    "    s=DemoService(Path(d)/'s.json');st=s.snapshot();st['boxes']={'1':s.box_data(1),'2':s.box_data(2)}",
    '    sys.stdout.write(json.dumps(snapshot(st)))'].join('\n');
  let raw=null;
  for(const exe of ['python','python3']){
    try{raw=execFileSync(exe,['-c',script],{cwd:root,encoding:'utf8',stdio:['ignore','pipe','ignore'],timeout:60000});break}catch(_){}
  }
  if(raw===null){t.skip('Python no disponible');return}
  const state=JSON.parse(raw);
  assert.ok(state.boxes['1'].some(p=>p&&p.hp===null),'la caja incluye registros sin PS');
  const owner=await freshPair(state.game);
  const res=await call('/v1/state','PUT',{state},bearer(owner.token));
  assert.equal(res.status,200,await res.text());
  await call('/v1/leave','POST',{},bearer(owner.token));
});

test('hostile pokemon fields and progress entries are rejected',async()=>{
  const owner=await freshPair();
  const mutations=[
    s=>{s.party[0].hp=HOSTILE}, s=>{s.party[0].max_hp=1000}, s=>{s.party[0].hp=-1},
    s=>{s.party[0].stats={ATQ:'x'}}, s=>{s.party[0].stats=[1,2]}, s=>{s.party[0].stats={[HOSTILE]:1}},
    s=>{s.party[0].iv=[32,0,0,0,0,0]}, s=>{s.party[0].iv=[31,31]}, s=>{s.party[0].ev=['0',0,0,0,0,0]},
    s=>{s.party[0].move_names='abc'}, s=>{s.party[0].move_names=[HOSTILE]}, s=>{s.party[0].move_names=['a','b','c','d','e']},
    s=>{s.party[0].moves=[1,2,3,HOSTILE]}, s=>{s.party[0].nickname=HOSTILE}, s=>{s.party[0].types=[HOSTILE]},
    s=>{s.party[0].met_date=HOSTILE}, s=>{s.party[0].egg='yes'}, s=>{s.party[0].level=101},
    s=>{s.party[0].base_stats={HP:HOSTILE}}, s=>{s.party[0].evolutions=[{target:1,method:HOSTILE}]},
    s=>{s.party[0].evolutions=[{target:1,extra:{nested:HOSTILE}}]}, s=>{s.party[0].unknown_field=1},
    s=>{s.boxes['1'][0].hp=HOSTILE}, s=>{s.progress.deaths['33:1'].pokemon.ability=HOSTILE},
    s=>{s.progress.deaths['33:1'].recorded_at=HOSTILE}, s=>{s.progress.deaths['33:1'].source='forged'},
    s=>{s.progress.deaths[HOSTILE]=s.progress.deaths['33:1']}, s=>{s.progress.missed_routes=[HOSTILE]},
    s=>{s.progress.route_marks['33:2'].pokemon.nickname=HOSTILE}, s=>{s.progress.origins={'33:1':HOSTILE}},
    s=>{s.progress.traded_routes=['../x']}, s=>{s.progress.death_count=-1},
  ];
  for(const [i,mutate] of mutations.entries()){
    const state=fullState('Ultra Sun 1.0');mutate(state);
    const res=await call('/v1/state','PUT',{state},bearer(owner.token));
    assert.equal(res.status,400,'mutation '+i);
  }
  await call('/v1/leave','POST',{},bearer(owner.token));
});

test('leave revokes both members in a single D1 batch',async()=>{
  const owner=await freshPair();
  const join=await call('/v1/pairs/join','POST',{name:'Peer',game:'Ultra Moon 1.0',invite_code:owner.invite_code});
  const guest=await join.json();
  env.DB.batches=[];
  assert.equal((await call('/v1/leave','POST',{},bearer(guest.token))).status,200);
  assert.deepEqual(env.DB.batches,[2]);
  assert.equal(env.DB.db.prepare('SELECT COUNT(*) n FROM members WHERE pair_id=?').get(owner.pair_id).n,0);
  assert.equal(env.DB.db.prepare('SELECT COUNT(*) n FROM pairs WHERE id=?').get(owner.pair_id).n,0);
  assert.equal((await call('/v1/partner','GET',undefined,bearer(owner.token))).status,401);
});

test('creating a pair removes abandoned unjoined pairs older than a week, and only those',async()=>{
  const db=env.DB.db, now=Date.now(), old=now-8*86400000;
  const add=(id,created,expires,slots)=>{
    db.prepare('INSERT INTO pairs (id,invite_hash,invite_expires,created_at) VALUES (?,?,?,?)').run(id,'h-'+id,expires,created);
    for(const slot of slots)db.prepare('INSERT INTO members (id,pair_id,slot,token_hash,name,game) VALUES (?,?,?,?,?,?)')
      .run(id+'-'+slot,id,slot,'t-'+id+'-'+slot,'N','Ultra Sun 1.0');
  };
  add('abandoned',old,old+86400000,[1]);
  add('joined-old',old,old+86400000,[1,2]);
  add('recent-expired',now-2*86400000,now-86400000,[1]);
  add('pending',now,now+86400000,[1]);
  await freshPair();
  const exists=id=>db.prepare('SELECT COUNT(*) n FROM pairs WHERE id=?').get(id).n===1;
  assert.equal(exists('abandoned'),false);
  assert.equal(db.prepare("SELECT COUNT(*) n FROM members WHERE pair_id='abandoned'").get().n,0);
  for(const id of ['joined-old','recent-expired','pending'])assert.equal(exists(id),true,id);
});

test('setup key comparison rejects wrong, missing, prefix and longer keys',async()=>{
  const k=env.CREATE_KEY;
  for(const headers of [{},{'X-Setup-Key':''},{'X-Setup-Key':k.slice(0,-1)},{'X-Setup-Key':k+'x'},
                        {'X-Setup-Key':k.toUpperCase()}]){
    const r=await call('/v1/pairs','POST',{name:'Other',game:'Ultra Sun 1.0'},headers);
    assert.equal(r.status,403);
  }
  assert.equal((await call('/v1/pairs','POST',{name:'Other',game:'Ultra Sun 1.0'},{'X-Setup-Key':k})).status,201);
});

test('whitespace-only player names are rejected like the client does',async()=>{
  const res=await call('/v1/pairs','POST',{name:'   ',game:'Ultra Sun 1.0'},{'X-Setup-Key':env.CREATE_KEY});
  assert.equal(res.status,400);
});
