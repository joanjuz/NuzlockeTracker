'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../web/companion.js'),'utf8');
const html=fs.readFileSync(path.join(__dirname,'../web/index.html'),'utf8');
const els={},get=id=>els[id]??={id,hidden:false,value:'',textContent:'',checked:false,disabled:false,
  showModal(){this.open=true},close(){this.open=false}};
assert.match(html,/id="soullink-enabled"/);
assert.match(html,/id="soullink-pokemon-icon"/);
let interval,body,requests=[];
const mon={species_id:25,nickname:'Chispa',species:'Pikachu',encryption_constant:101,
  origin_version:33,met_location_id:8};
const own={game:'Ultra Sun 1.0',party:[mon,null,null,null,null,null],boxes:{},progress:{deaths:{}},
  connection:{status:'connected'},stale:false};
const remoteMon={species_id:1,nickname:'Brote',species:'Bulbasaur',encryption_constant:202,
  origin_version:33,met_location_id:8};
const remote={schema_version:1,game:'Ultra Sun 1.0',party:[remoteMon,null,null,null,null,null],boxes:{},
  progress:{deaths:{},missed_routes:[]}};
body={configured:true,my_name:'Mi partida',partner:{name:'Amigo',game:'Ultra Sun 1.0',updated_at:100,
  state:remote}};
const storage={};
const ctx={document:{getElementById:get,querySelectorAll:()=>[]},
  localStorage:{getItem:k=>storage[k]??null,setItem:(k,v)=>storage[k]=v},
  localState:own,routeCatalog:[{id:8,ids:[8]}],token:'test-local-token',
  fetch:async(url,opts)=>{requests.push({url,opts});return{ok:true,json:async()=>url==='/api/companion'?body:{ok:true}}},
  window:{setCompanionView:()=>{}},setInterval:(cb)=>{interval=cb},
  navigator:{clipboard:{writeText:async()=>{}}},confirm:()=>true,
};
vm.createContext(ctx);vm.runInContext(source,ctx);
async function settle(){for(let i=0;i<3;i++)await new Promise(r=>setImmediate(r))}
(async()=>{
 await settle();
 get('soullink-enabled').checked=true;
 get('soullink-enabled').onchange();
 // First remote snapshot is history, not a new alert.
 await interval();await settle();
 assert.equal(get('soullink-notification').hidden,true);
 remote.progress.deaths['33:202']={pokemon:remoteMon,recorded_at:'2026-10-09T10:00:00Z'};
 body.partner.updated_at=101;
 await interval();await settle();
 assert.equal(get('soullink-notification').hidden,false);
 assert.match(get('soullink-description').textContent,/Chispa/);
 assert.match(get('soullink-description').textContent,/Brote/);
 assert.equal(get('soullink-pokemon-icon').src,'/sprites/25.png');
 assert.equal(requests.filter(x=>x.url==='/api/command').length,0,
   'No automatic deaths');
 get('soullink-dismiss').onclick();
 assert.equal(get('soullink-notification').hidden,true);
 await interval();await settle();
 assert.equal(get('soullink-notification').hidden,true,'Dismiss stays dismissed');
 delete remote.progress.deaths['33:202'];
 remote.progress.deaths['33:303']={pokemon:remoteMon,recorded_at:'2026-10-09T10:01:00Z'};
 await interval();await settle();
 assert.equal(get('soullink-notification').hidden,false);
 await get('soullink-kill').onclick();
 const commands=requests.filter(x=>x.url==='/api/command');
 assert.equal(commands.length,1);
 assert.deepEqual(JSON.parse(commands[0].opts.body),{action:'mark_dead',key:'33:101'});
 get('soullink-enabled').checked=false;
 get('soullink-enabled').onchange();
 remote.progress.deaths['33:404']={pokemon:remoteMon,recorded_at:'2026-10-09T10:02:00Z'};
 await interval();await settle();
 assert.equal(get('soullink-notification').hidden,true);
 assert.equal(requests.filter(x=>x.url==='/api/command').length,1);
 console.log('Soul Link: muerte de la misma ruta, Ignorar/Marcar, sin muerte automática OK');
})().catch(e=>{console.error(e);process.exitCode=1});
