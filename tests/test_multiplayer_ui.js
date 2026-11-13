'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const roomSource=fs.readFileSync('web/room.js','utf8'),source=fs.readFileSync('web/companion.js','utf8');
class Node {
  constructor(tag='div'){this.tagName=tag;this.children=[];this.value='';this.textContent='';this.hidden=false;this.disabled=false;this.checked=false;}
  append(...nodes){this.children.push(...nodes);}
  replaceChildren(...nodes){this.children=[...nodes];}
  setAttribute(name,value){this[name]=value;}
  removeAttribute(name){delete this[name];}
  closest(){return this.wrapper??={hidden:false};}
  showModal(){this.open=true;}
  close(){this.open=false;}
  querySelectorAll(){return this.children.flatMap(n=>[...(['button','select'].includes(n.tagName)?[n]:[]),...n.querySelectorAll()]);}
  set innerHTML(value){throw Error('Untrusted room data must use textContent');}
}
const els={},el=id=>els[id]??=new Node();
const pokemon=(id,name,route=8,extra={})=>({species_id:25,species:'Pikachu',nickname:name,origin_version:33,
 encryption_constant:id,met_location_id:route,level:20,hp:50,max_hp:50,checksum_valid:true,...extra});
const own=pokemon(1234,'Local'),other=pokemon(5678,'Remoto');
const state=(p)=>({schema_version:1,game:'Ultra Sun 1.0',party:[p,null,null,null,null,null],boxes:{'1':[p]},
 progress:{deaths:{},route_marks:{},origins:{},missed_routes:[]}});
const catalog=[{id:8,ids:[8,9],name:'Ruta 1',story_order:1}];
const members=Array.from({length:4},(_,i)=>({player_id:'p'+i,run_id:'r'+i,name:'Jugador '+i,game:'Ultra Sun 1.0',
 online:true,source_live:true,left:false,state:state(i===0?own:{...other,encryption_constant:5678+i}),links:{'alola:8':i===0?'33:1234':'33:'+(5678+i)}}));
let info={protocol:2,configured:true,transport:'direct',direct_role:'host',player_id:'p0',invite_link:'',
 room:{session_id:'session',epoch:'epoch',capacity:4,host_id:'p0',revision:1,members,events:[]}};
let poll,hold=false,release;const posts=[],views=[];
const ctx={console,document:{getElementById:el,createElement:tag=>new Node(tag),querySelectorAll:()=>[]},
 window:{setCompanionView:(...args)=>views.push(args)},localState:{...state(own),stale:false,connection:{status:'connected'}},
 localStorage:{getItem:()=> 'true',setItem(){}},routeCatalog:catalog,routeCatalogFor:()=>catalog,
 token:'local-test',confirm:()=>true,navigator:{},setInterval:fn=>{poll=fn;},
 fetch:async(url,opts)=>{if(opts?.method==='POST'){posts.push({url,...JSON.parse(opts.body)});if(hold)await new Promise(resolve=>{release=resolve;});}return {ok:true,json:async()=>info};}};
el('companion-transport').value='direct';el('companion-game').value='Ultra Sun 1.0';
el('room-panel').append(el('room-roster'),el('room-groups'));
const settle=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{
 vm.createContext(ctx);require('./ui_shared.js').loadShared(ctx);vm.runInContext(roomSource,ctx);ctx.window.PokeJuzRoom=ctx.window.PokeJuzRoom;
 const groups=ctx.window.PokeJuzRoom.groups(info.room,()=>catalog);
 assert.equal(groups.length,1);assert.equal(groups[0].members.length,4);
 assert.equal(groups[0].members[0].row.candidates.size,1,'party and box duplicates merge');
 const mixed=structuredClone(info.room);mixed.members[1].game='Pokémon X 1.0';mixed.members[1].state.party[0].origin_version=24;
 assert.equal(ctx.window.PokeJuzRoom.groups(mixed,()=>catalog)[0].members[1].compatible,false,'regions are not silently linked');
 vm.runInContext(source,ctx);await settle();
 assert.equal(el('room-roster').children.length,4);
 assert.equal(el('room-panel').hidden,false);
 assert.equal(posts.length,0,'a snapshot cannot write a command');
 hold=true;el('companion-refresh').onclick();await settle();
 assert.equal(el('room-groups').querySelectorAll().find(n=>n.tagName==='select').disabled,true,'pending action blocks capture selection');
 await poll();await settle();
 assert.equal(el('room-groups').querySelectorAll().find(n=>n.tagName==='select').disabled,true,'poll cannot re-enable selection during an action');
 hold=false;release();await settle();
 assert.equal(el('room-groups').querySelectorAll().find(n=>n.tagName==='select').disabled,false);
 const card=el('room-roster').children[1];card.children.find(n=>n.tagName==='button').onclick();
 assert.equal(views.at(-1)[0],true);assert.equal(views.at(-1)[1].stale,true,'remote view is read-only');
 members[1].state.progress.deaths['33:5679']={pokemon:{...other,encryption_constant:5679},recorded_at:'today'};
 await poll();await settle();
 assert.equal(el('soullink-notification').hidden,false);
 assert.equal(posts.filter(p=>p.url==='/api/command').length,0,'death requires a click');
 await el('soullink-kill').onclick();await settle();
 assert.equal(posts.at(-1).action,'mark_dead');assert.equal(posts.at(-1).key,'33:1234');
 assert.equal(posts.at(-1).source,'soullink-response');
 members[2].state.progress.deaths['33:5680']={pokemon:{...other,encryption_constant:5680},recorded_at:'today',source:'soullink-response'};
 await poll();await settle();assert.equal(el('soullink-notification').hidden,true,'response does not bounce');
 members[3].state.progress.deaths['33:5681']={pokemon:{...other,encryption_constant:5681},recorded_at:'today'};
 await poll();await settle();assert.equal(el('soullink-notification').hidden,false);
 delete members[3].state.progress.deaths['33:5681'];await poll();await settle();
 const count=posts.length;await el('soullink-kill').onclick();await settle();
 assert.equal(posts.length,count,'revived remote death is revalidated before command');
 info={...info,configured:false};await poll();await settle();assert.equal(el('soullink-notification').hidden,true);
 assert.equal(el('companion-setup').hidden,false,'cached room can be inspected without reconnecting');
 console.log('Room UI: four players, isolated maps, explicit confirmation, no bounce and revival revalidation OK');
})().catch(e=>{console.error(e);process.exitCode=1;});
