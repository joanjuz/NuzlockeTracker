'use strict';
// Team assistant · saved teams: save, open, rename, duplicate, delete, and members that can no longer be found.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const A=require('../web/analysis.js'),I=require('../web/insights.js');
const {loadShared,slice,read}=require('./ui_shared.js');
const data=JSON.parse(fs.readFileSync(path.join(__dirname,'../data/Analysis_USUM.json'),'utf8'));
let checks=0;const ok=(value,message)=>{assert.ok(value,message);checks++};const eq=(a,b,message)=>{assert.deepEqual(a,b,message);checks++};
let ec=900;
const mon=(nickname,species_id,types)=>({species_id,species:'Sp'+species_id,nickname,types,ability:'—',ability_id:0,analysis_moves:[],move_names:[],
  encryption_constant:ec++,origin_version:33});
const a=mon('Uno',1,['Planta']),b=mon('Dos',4,['Fuego']),c=mon('Tres',7,['Agua']);
const box=Array(30).fill(null);box[0]=c;
const live={game:'Ultra Moon 1.0',party:[a,b,null,null,null,null],boxes:{'1':box},box_verified:true,stale:false,connection:{status:'connected'},progress:{},scan:{active:false}};

// Minimal stand-in for /api/teams with the same contract as tracker/virtual_teams.py.
const server={teams:[],next:1,posts:[],fail:null,readOnly:false,notice:null};
const view=team=>({schema_version:1,game:'Ultra Moon 1.0',teams:JSON.parse(JSON.stringify(server.teams)),limit:50,team,
  ...(server.readOnly?{read_only:true}:{}),...(server.notice?{notice:server.notice}:{})});
function post(body){
  server.posts.push(body);
  if(server.fail)return {ok:false,json:async()=>({error:server.fail})};
  let team=null;
  if(body.action==='save'&&!body.id){team={id:'t'+server.next++,name:body.name,members:body.members,game:'Ultra Moon 1.0',modified:'2026-11-16T10:00:00+00:00'};server.teams.push(team)}
  else if(body.action==='save'){team=server.teams.find(t=>t.id===body.id);Object.assign(team,{name:body.name,members:body.members})}
  else if(body.action==='rename'){team=server.teams.find(t=>t.id===body.id);team.name=body.name}
  else if(body.action==='duplicate'){const source=server.teams.find(t=>t.id===body.id);team={...source,id:'t'+server.next++,name:source.name+' (copia)'};server.teams.push(team)}
  else if(body.action==='delete'){assert.equal(body.confirm,true);server.teams=server.teams.filter(t=>t.id!==body.id)}
  return {ok:true,json:async()=>view(team?team.id:null)};
}
class El{
  constructor(id){Object.assign(this,{id,options:[],innerHTML:'',textContent:'',value:'',hidden:false,checked:false,disabled:false,listeners:{},dataset:{},attributes:{}})}
  replaceChildren(){this.options=[]}
  add(o){this.options.push(o)}
  addEventListener(type,fn){this.listeners[type]=fn}
  setAttribute(k,v){this.attributes[k]=String(v)}
  focus(){focused=this.id}
}
let focused=null,confirmAnswer=true;const confirms=[];
const nodes={};const $=id=>nodes[id]??=new El(id);
const ctx={$,TypeAnalysis:A,TeamInsights:I,state:live,analysisData:{types:data.types,chart:data.chart},companionView:false,analysisSignature:'',analysisTeamSignature:'',
  token:'tok',console,Option:function(text,value){this.text=text;this.value=String(value)},setText:(node,text)=>{node.textContent=text},
  getJSON:async url=>{assert.equal(url,'/api/teams');return view(null)},
  fetch:async(url,options)=>{assert.equal(url,'/api/teams');assert.equal(options.method,'POST');assert.equal(options.headers['X-Tracker-Token'],'tok');return post(JSON.parse(options.body))},
  confirm:text=>{confirms.push(text);return confirmAnswer},
  document:{activeElement:null,querySelectorAll:()=>[]}};
vm.createContext(ctx);loadShared(ctx);
vm.runInContext(slice('app/analysis-view.js','function multiplier(',"\nfor(const id of ['analysis-defense'"),ctx);
vm.runInContext(read('app/team-builder.js'),ctx);
const tick=()=>new Promise(resolve=>setImmediate(resolve));
const click=dataset=>$('team-builder').listeners.click({target:{closest:()=>({dataset,disabled:false})}});
const slots=()=>[...$('builder-team').innerHTML.matchAll(/<li class="builder-slot[^"]*">(?:<img[^>]*>)?<div><strong>([^<]+)</g)].map(m=>m[1]);
const options=()=>$('builder-saved').options.map(o=>o.text);

(async()=>{
  $('analysis-section-builder').onclick();await tick();
  eq(options(),['Borrador sin guardar']);
  eq($('builder-saved-info').textContent,'0 equipos guardados en esta partida y juego.');
  eq([$('builder-save').disabled,$('builder-rename').disabled,$('builder-duplicate').disabled,$('builder-delete').disabled],[true,true,true,true],'Nada que guardar todavía');
  // Save needs a name and at least one member.
  $('builder-use-party').onclick();
  eq($('builder-save').disabled,false);
  ok($('builder-saved-info').textContent.startsWith('Borrador sin guardar.'));
  $('builder-save').onclick();
  eq(server.posts.length,0);eq($('builder-saved-status').textContent,'Escribe un nombre para el equipo.');eq(focused,'builder-name');
  $('builder-name').value='  Liga  ';
  await $('builder-save').onclick();
  eq(server.posts[0],{action:'save',name:'Liga',members:[I.memberOf(I.candidateEntries(live)[0]),I.memberOf(I.candidateEntries(live)[1])]},'Solo identificador, especie y apodo, en orden');
  eq(Object.keys(server.posts[0].members[0]).sort(),['id','nickname','species','species_id']);
  eq(options(),['Borrador sin guardar','Liga (2)']);eq($('builder-saved').value,'t1');
  eq($('builder-saved-status').textContent,'Equipo guardado.');
  eq($('builder-save').textContent,'Guardar cambios');
  eq($('builder-saved-info').textContent,'Liga · Ultra Moon 1.0 · modificado 2026-11-16');
  // Editing the open team marks it and saving updates the same record.
  click({builderToggle:I.pokemonId(c)});
  ok($('builder-saved-info').textContent.endsWith('cambios sin guardar'));
  await $('builder-save').onclick();
  eq(server.posts[1].id,'t1');eq(server.teams.length,1);eq(server.teams[0].members.length,3);
  ok(!$('builder-saved-info').textContent.includes('sin guardar'));
  // Rename and duplicate.
  $('builder-name').value='Final';await $('builder-rename').onclick();
  eq(server.posts[2],{action:'rename',id:'t1',name:'Final'});eq(options()[1],'Final (3)');
  await $('builder-duplicate').onclick();
  eq(options(),['Borrador sin guardar','Final (3)','Final (copia) (3)']);
  eq($('builder-saved').value,'t2','Se edita la copia');eq($('builder-name').value,'Final (copia)');
  // Open: the draft is replaced by the saved order; unsaved changes ask first.
  click({builderRemove:'0'});eq(slots(),['Dos','Tres']);
  confirmAnswer=false;$('builder-saved').value='t1';$('builder-saved').onchange();
  eq(confirms.length,1);eq($('builder-saved').value,'t2','Cancelar conserva el equipo abierto');eq(slots(),['Dos','Tres']);
  confirmAnswer=true;$('builder-saved').value='t1';$('builder-saved').onchange();
  eq(slots(),['Uno','Dos','Tres']);eq($('builder-name').value,'Final');
  // A saved member that no longer exists is shown as not located, never replaced.
  ctx.state={...live,boxes:{'1':Array(30).fill(null)}};ctx.renderTeamBuilder();
  eq(slots(),['Uno','Dos','Tres'],'El ausente conserva su nombre guardado');
  ok($('builder-team').innerHTML.includes('No localizado'));
  ok($('builder-status').textContent.startsWith('1 integrante no localizado'));
  ok(!$('builder-saved-info').textContent.includes('sin guardar'),'Un ausente no modifica el equipo guardado');
  ctx.state=live;ctx.renderTeamBuilder();
  ok(!$('builder-team').innerHTML.includes('No localizado'),'Al volver a leerse se localiza de nuevo');
  // Delete asks for confirmation and keeps the draft.
  confirmAnswer=false;$('builder-delete').onclick();
  eq(server.teams.length,2,'Sin confirmar no se elimina');ok(confirms.at(-1).includes('«Final»'));
  confirmAnswer=true;await $('builder-delete').onclick();
  eq(server.posts.at(-1),{action:'delete',id:'t1',confirm:true});
  eq(options(),['Borrador sin guardar','Final (copia) (3)']);eq($('builder-saved').value,'');eq(slots(),['Uno','Dos','Tres']);
  // Server errors are shown and nothing changes locally.
  server.fail='Ya hay un equipo guardado con ese nombre';$('builder-name').value='Final (copia)';
  await $('builder-save').onclick();
  eq($('builder-saved-status').textContent,'Ya hay un equipo guardado con ese nombre');eq(options().length,2);
  server.fail=null;
  // A list written by a newer version is read-only.
  server.readOnly=true;server.notice='Estos equipos se guardaron con una versión más nueva.';
  $('analysis-section-current').onclick();$('analysis-section-builder').onclick();await tick();
  eq($('builder-save').disabled,true);eq($('builder-name').disabled,true);
  eq($('builder-saved-status').textContent,'Estos equipos se guardaron con una versión más nueva.');
  server.readOnly=false;server.notice=null;
  // The partner view never loads or saves local teams.
  const before=server.posts.length;
  ctx.companionView=true;ctx.renderTeamBuilder();await tick();
  eq(options(),['Borrador sin guardar']);eq($('builder-saved').disabled,true);eq($('builder-save').disabled,true);
  eq($('builder-saved-info').textContent,'Los equipos se guardan solo en tu propia partida.');
  await ctx.builderTeamRequest({action:'save',name:'x',members:[]},'no');
  eq(server.posts.length,before);
  ctx.companionView=false;ctx.renderTeamBuilder();await tick();
  eq(options(),['Borrador sin guardar','Final (copia) (3)'],'Al volver a la partida propia se recargan');
  // Another game: its own list (the scope reloads).
  ctx.state={...live,game:'Ultra Sun 1.0'};server.teams=[];ctx.renderTeamBuilder();await tick();
  eq(options(),['Borrador sin guardar']);eq(slots(),[]);
  // Hostile team names stay text.
  server.teams=[{id:'h1',name:'<img src=x onerror=alert(1)>',members:[{id:'33:1',species_id:1,species:'<b>x</b>',nickname:'<i>y</i>'}],game:'<u>g</u>',modified:'<s>'}];
  $('analysis-section-current').onclick();$('analysis-section-builder').onclick();await tick();
  $('builder-saved').value='h1';$('builder-saved').onchange();
  ok(!$('builder-team').innerHTML.includes('<b>x</b>')&&!$('builder-team').innerHTML.includes('<i>y</i>'));
  eq($('builder-saved-info').innerHTML,'','El resumen se escribe como texto, no como HTML');

  // --- Wiring.
  const page=read('index.html'),source=read('app/team-builder.js');
  for(const id of ['builder-saved','builder-name','builder-save','builder-rename','builder-duplicate','builder-delete','builder-saved-info','builder-saved-status'])ok(page.includes(`id="${id}"`),id);
  ok(source.includes("fetch('/api/teams'")&&!/fetch\('https?:/.test(source),'Solo el servidor local');
  ok(!/command\(/.test(source),'Guardar equipos no envía órdenes al juego');
  ok(!/soul|companion\./i.test(source.replace(/companionView/g,'')),'Sin relación con Soul Link');
  console.log(checks+' comprobaciones de equipos guardados: OK');
})().catch(error=>{console.error(error);process.exit(1)});
