import test from 'node:test';
import assert from 'node:assert/strict';
import { DatabaseSync } from 'node:sqlite';
import { readFileSync } from 'node:fs';
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
  async batch(stmts){this.db.exec('BEGIN');try{const values=stmts.map(s=>s.run());this.db.exec('COMMIT');return values}catch(e){this.db.exec('ROLLBACK');throw e}}
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
