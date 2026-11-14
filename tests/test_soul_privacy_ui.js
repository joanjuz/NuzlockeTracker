'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
class Element{
 constructor(tag='div'){this.tagName=tag;this.children=[];this.value='';this.textContent='';this.hidden=false;this.disabled=false;this.checked=false;this.style={setProperty:(k,v)=>{this[k]=v;}};}
 append(...nodes){this.children.push(...nodes);}
 replaceChildren(...nodes){this.children=[...nodes];}
 setAttribute(name,value){this[name]=value;}
 closest(){return this.wrapper??={hidden:false};}
 querySelectorAll(){return this.children.flatMap(n=>[...(['button','select','input'].includes(n.tagName)?[n]:[]),...n.querySelectorAll()]);}
 set innerHTML(value){throw Error('Room values must use textContent');}
}
const elements={},el=id=>elements[id]??=new Element();
const text=node=>[node.textContent,...node.children.map(text)].join(' ');
const catalog=[{id:8,ids:[8,9],name:'Ruta 1',story_order:1}];
const mon=(ec,nickname)=>({species_id:25,species:'Pikachu',nickname,origin_version:33,encryption_constant:ec,met_location_id:8,level:20,hp:50,max_hp:50,checksum_valid:true});
const snapshot=(ec,name)=>({schema_version:1,game:'Ultra Sun 1.0',party:[mon(ec,name),null,null,null,null,null],boxes:{},progress:{deaths:{},route_marks:{},origins:{},missed_routes:[]}});
const minimal=(ec,status='alive',at='',response=false)=>({key:'33:'+ec,pokemon:{species_id:25,origin_version:33,encryption_constant:ec,met_location_id:8},status,death_at:at,response});
const member=(i)=>({player_id:'p'+i,run_id:'r'+i,name:'Jugador '+i,game:'Ultra Sun 1.0',sequence:1,online:true,source_live:true,left:false,sharing:false,state:null,view_ttl_ms:0,links:{'alola:8':'33:'+(100+i)},soul:{captures:{'alola:8':minimal(100+i)},missed_routes:[]}});
const makeInfo=(count=2)=>({configured:true,protocol:3,transport:'direct',direct_role:'host',player_id:'p0',own_sharing:false,invite_link:'nuzlocke://127.0.0.1:9000/soul#same-link',error:'',room:{protocol:3,session_id:'s',epoch:'e',host_id:'p0',capacity:4,revision:1,members:Array.from({length:count},(_,i)=>member(i)),events:[]}});
const actions=[],shown=[],notices=[],timers=[];let cleared=0,resets=0,clock=0;
const ownState={...snapshot(100,'MY_LOCAL_CAPTURE'),stale:false,connection:{status:'connected'}};
const ctx={window:{},document:{createElement:tag=>new Element(tag)},confirm:()=>true,setInterval:fn=>timers.push(fn)};
vm.createContext(ctx);vm.runInContext(fs.readFileSync('web/room.js','utf8'),ctx);vm.runInContext(fs.readFileSync('web/soul.js','utf8'),ctx);
el('room-panel').append(el('room-roster'),el('room-groups'),el('soul-sharing'),el('soul-regenerate'),el('soul-revoke'));
const ui=ctx.window.PokeJuzSoul.create({el,action:(name,data)=>actions.push({name,data}),showMember:(m,open)=>shown.push({m,open}),backToLocal:()=>{cleared++;},catalog:()=>catalog,local:()=>ownState,propose:n=>notices.push(n),resetNotices:()=>{resets++;},enabled:()=>true,now:()=>clock});
let info=makeInfo();ui.update(info);
assert.equal(el('soul-sharing').checked,false,'sharing defaults off');
assert.match(el('soul-sharing-state').textContent,/privada/);
assert.equal(el('room-roster').children.length,2);
assert.match(text(el('room-roster').children[1]),/Partida privada/);
assert.ok(!text(el('room-roster').children[1]).includes('MY_LOCAL_CAPTURE'));
assert.equal(el('room-roster').children[1].children.filter(n=>n.tagName==='button').length,0,'host gets no private view button');
assert.equal(ctx.window.PokeJuzSoul.groups(info.room,'p0',ownState,()=>catalog)[0].members[0].row.candidates.size,1,'own capture can be selected without full sharing');
el('soul-sharing').checked=true;el('soul-sharing').onchange();
assert.deepEqual(JSON.parse(JSON.stringify(actions.pop())),{name:'soul_share',data:{sharing:true}});
for(const count of [1,2,3,4]){info=makeInfo(count);info.room.revision=count+1;ui.update(info);assert.equal(el('room-roster').children.length,count);assert.match(el('room-summary').textContent,new RegExp('^'+count+'/4'));assert.equal(el('room-roster')['--room-count'],String(count));assert.equal(el('companion-share').value,'nuzlocke://127.0.0.1:9000/soul#same-link');}
assert.equal(actions.length,0,'joins never generate additional links');
el('soul-regenerate').onclick();el('soul-revoke').onclick();
assert.deepEqual(actions.map(a=>a.name),['soul_invite','soul_revoke']);actions.length=0;
// A private participant still produces only a manually proposed linked death.
info=makeInfo();info.room.revision=10;ui.update(info);
info=structuredClone(info);info.room.revision++;info.room.members[1].sequence++;
info.room.members[1].soul.captures['alola:8']=minimal(101,'dead','t1');ui.update(info);
assert.equal(notices.length,1);assert.equal(actions.length,0,'remote events never issue a local action');
assert.equal(ui.valid(notices[0]),true);
assert.equal(ui.commandContext(notices[0]).soullink_room.protocol,3);
assert.equal(ui.commandContext(notices[0]).soullink_room.local_run_id,'r0');
ui.update(structuredClone(info));assert.equal(notices.length,1,'duplicate death does not propose again');
info=structuredClone(info);info.room.revision++;info.room.members[1].soul.captures['alola:8']=minimal(101,'alive');ui.update(info);
assert.equal(ui.valid(notices[0]),false,'revival invalidates pending confirmation');
info=structuredClone(info);info.room.revision++;info.room.members[1].soul.captures['alola:8']=minimal(101,'dead','t2',true);ui.update(info);
assert.equal(notices.length,1,'Soul Link response does not bounce');
// Full view is explicitly shared and time limited.
info=structuredClone(info);info.room.revision++;Object.assign(info.room.members[1],{sharing:true,state:snapshot(101,'REVOKE_ME_FULL_SECRET'),view_ttl_ms:1000,sequence:5});ui.update(info);
let viewButton=el('room-roster').children[1].children.find(n=>n.tagName==='button');assert.ok(viewButton);
viewButton.onclick();assert.equal(shown.at(-1).open,true);assert.match(text(el('room-roster').children[1]),/REVOKE_ME_FULL_SECRET/);
const replay=structuredClone(info);clock=400;const repeated=structuredClone(replay);ui.update(repeated);clock=1100;const before=cleared;ui.tick();
assert.ok(cleared>before);assert.equal(repeated.room.members[1].state,null);
assert.ok(!text(el('room-roster').children[1]).includes('REVOKE_ME_FULL_SECRET'));
ui.update(structuredClone(replay));
assert.equal(el('room-roster').children[1].children.filter(n=>n.tagName==='button').length,0,'expired same-sequence replay cannot recreate a view');
assert.ok(!text(el('room-roster').children[1]).includes('REVOKE_ME_FULL_SECRET'));
// A newer authorized sequence works, but failed polling clears it and prevents replay.
info=structuredClone(replay);info.room.revision++;info.room.members[1].sequence=6;ui.update(info);
assert.match(text(el('room-roster').children[1]),/REVOKE_ME_FULL_SECRET/);
const failureReplay=structuredClone(info);ui.failed();assert.equal(info.room.members[1].state,null);
ui.update(failureReplay);assert.equal(failureReplay.room.members[1].state,null,'failed polling expires the current sequence');
// Revocation fails closed even if an unexpected full snapshot arrives alongside false permission.
info=structuredClone(replay);info.room.revision=30;info.room.members[1].sequence=7;info.room.members[1].sharing=false;ui.update(info);
assert.equal(info.room.members[1].state,null);assert.match(text(el('room-roster').children[1]),/Partida privada/);
assert.ok(!text(el('room-roster').children[1]).includes('REVOKE_ME_FULL_SECRET'));
info=structuredClone(info);info.room.members[1].online=false;ui.update(info);assert.match(text(el('room-roster').children[1]),/plaza reservada/);
const cached=structuredClone(replay);cached.room.revision=40;cached.configured=false;ui.update(cached);assert.equal(cached.room.members[1].state,null,'offline cache never exposes a full view');
assert.equal(el('soul-own-sharing').hidden,true);
ui.idle({protocol:3,configured:false,room:null,can_resume:true,error:''});
assert.equal(el('companion-setup').hidden,false);
assert.equal(el('companion-linked').hidden,false,'saved individual proof has an explicit forget action');
assert.equal(el('companion-leave').textContent,'Olvidar conexión guardada');
assert.equal(el('companion-refresh').hidden,true);
ui.idle({protocol:3,configured:false,room:null,can_forget:true,error:'No se pudo guardar'});
assert.equal(el('companion-linked').hidden,false,'failed admission can be forgotten');
ui.clear();assert.equal(el('companion-refresh').hidden,false,'legacy controls restore after leaving the new flow');
ui.idle({protocol:3,configured:false,room:null,can_resume:false,error:''});
assert.equal(el('companion-refresh').hidden,true);
ui.clear();assert.equal(el('companion-refresh').hidden,false,'leaving plain idle restores legacy refresh without a saved room');
assert.ok(resets>0);
console.log('Soul Link UI: private membership, shared invitation, dynamic cards, minimal death proposals, revocation and replay-safe leases OK');
