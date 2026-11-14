'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const elements={},get=id=>elements[id]??={value:'',hidden:false,disabled:false,textContent:'',
 closest(){return this.wrapper??={hidden:false};},showModal(){},close(){}};
get('companion-transport').value='soul';get('companion-name').value='Sol';
get('companion-game').value='Ultra Sun 1.0';get('companion-port').value='0';
let status={configured:false,partner:null},updates=0;
const posts=[];
const ctx={document:{getElementById:get,querySelectorAll:()=>[]},localStorage:{getItem:()=>null,setItem(){}},
 window:{setCompanionView(){},PokeJuzRoom:{create:()=>({update(){updates++;},clear(){},setBusy(){}})}},
 navigator:{},localState:{party:[],boxes:{},progress:{deaths:{}}},routeCatalog:[],token:'test-local',
 setInterval(){},confirm:()=>true,fetch:async(url,opts)=>{if(opts?.method==='POST')posts.push(JSON.parse(opts.body));return {ok:true,json:async()=>status};}};
const settle=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{
 vm.createContext(ctx);require('./ui_shared.js').loadShared(ctx);vm.runInContext(fs.readFileSync('web/companion.js','utf8'),ctx);await settle();
 for(const invite of ['nuzlocke://127.0.0.1:9000/room#abc','nuzlocke://127.0.0.1:9000/join#abc','https://pair.workers.dev/join#abc']){
  get('companion-invite').value=invite;await get('companion-join').onclick();await settle();
  assert.equal(posts.length,0,'primary private flow never silently chooses a full-sharing legacy protocol');
  assert.match(get('companion-status').textContent,/conexión anterior/);
 }
 get('companion-invite').value='nuzlocke://127.0.0.1:9000/soul#abc';
 await get('companion-join').onclick();await settle();assert.equal(posts.at(-1).action,'soul_join');
 get('companion-transport').value='room';get('companion-transport').onchange();
 get('companion-invite').value='nuzlocke://127.0.0.1:9000/room#abc';
 status={configured:true,protocol:2,room:{},partner:null};
 await get('companion-join').onclick();await settle();
 assert.equal(posts.at(-1).action,'room_join');assert.equal(updates,1);
 assert.equal(get('companion-title').textContent,'Conexión anterior');
 assert.match(get('companion-disclaimer').textContent,/comparte la partida completa/);
 console.log('Soul Link transition: no silent privacy downgrade; explicit legacy mode retains honest full-sharing notice');
})().catch(error=>{console.error(error);process.exitCode=1;});
