'use strict';
// Automatic stage advance UI (web/app/progress.js): the opt-in switch and the notice with undo.
const assert=require('node:assert/strict'),vm=require('node:vm');
const {loadShared,scripts,read}=require('./ui_shared.js');
let checks=0;const ok=(value,message)=>{assert.ok(value,message);checks++};const eq=(a,b,message)=>{assert.deepEqual(a,b,message);checks++};
class El{
  constructor(id){Object.assign(this,{id,innerHTML:'',textContent:'',hidden:false,disabled:false,open:false,dataset:{},attributes:{},listeners:{},value:'',checked:false})}
  setAttribute(k,v){this.attributes[k]=String(v)}
  getAttribute(k){return this.attributes[k]??null}
  addEventListener(type,fn){(this.listeners[type]??=[]).push(fn)}
  querySelector(){return null}
  showModal(){this.open=true}
  close(){this.open=false}
}
function load({companion=false,stored=null}={}){
  const nodes={},commands=[],storage={...(stored?{'progressive-cap-auto-dismissed':stored}:{})};
  const $=id=>nodes[id]??=new El(id);
  const ctx={$,companionView:companion,state:null,token:'t',console,
    setText:(node,text)=>{if(node.textContent!==text)node.textContent=text},
    command:async cmd=>commands.push(cmd),switchTab:()=>{},setTimeout:()=>{},
    localStorage:{getItem:key=>storage[key]??null,setItem:(key,value)=>{storage[key]=String(value)}},
    window:{addEventListener:()=>{}}};
  vm.createContext(ctx);loadShared(ctx,['esc','num','list']);
  vm.runInContext(scripts['app/progress.js'],ctx,{filename:'web/app/progress.js'});
  return {ctx,$,commands,storage,run:code=>vm.runInContext(code,ctx)};
}
const stage=(id,name,cap)=>({id,name,cap});
const stages=[stage('a','Gimnasio 1',14),stage('b','Gimnasio 2',20),stage('c','Liga',50)];
const caps=current=>{const index=stages.findIndex(s=>s.id===current);
  return {status:'ok',configured:true,show:true,stages,current,current_index:index,current_cap:stages[index].cap,current_name:stages[index].name,total:3,decreasing:[],removed_current:null,rejected_kept:false}};
const advance={id:'e1',kind:'advance',at:'2026-11-16T10:00:00+00:00',pokemon:'Chispa',from_level:14,to_level:15,from_stage:stages[0],to_stage:stages[1]};
const snapshot=(auto,current='b')=>({level_caps:caps(current),level_caps_auto:auto,party:[{species:'Pikachu',nickname:'Chispa',level:15},null,null,null,null,null]});
const plain=value=>JSON.parse(JSON.stringify(value));

// --- The switch: off by default, sends its own command, explains itself.
{
  const {ctx,$,commands,run}=load();
  ctx.state=snapshot({enabled:false,read_only:false,event:null});
  run('renderProgress()');
  let html=$('caps-current').innerHTML;
  ok(/<input type="checkbox" id="caps-auto" aria-describedby="caps-auto-note"> Avanzar automáticamente a la siguiente etapa<\/label>/.test(html),'Desactivada de forma predeterminada');
  ok(html.includes('Desactivado de forma predeterminada')&&html.includes('Avanza una sola etapa cada vez')&&html.includes('No modifica el juego'));
  ok(html.includes('id="caps-show" checked')&&html.includes('id="caps-select"'),'La selección manual sigue disponible');
  ctx.capsChange({target:{id:'caps-auto',checked:true}});
  ctx.capsChange({target:{id:'caps-auto',checked:false}});
  eq(plain(commands),[{action:'level_caps_auto',enabled:true},{action:'level_caps_auto',enabled:false}]);
  ctx.state=snapshot({enabled:true,read_only:false,event:null});run('renderProgress()');
  ok($('caps-current').innerHTML.includes('id="caps-auto" aria-describedby="caps-auto-note" checked>'),'Refleja la opción guardada');
  ctx.state=snapshot({enabled:false,read_only:true,event:null});run('renderProgress()');
  ok($('caps-current').innerHTML.includes('id="caps-auto" aria-describedby="caps-auto-note" disabled>')&&$('caps-current').innerHTML.includes('versión más nueva'));
  // A snapshot from an older service (no level_caps_auto) still renders.
  ctx.state={level_caps:caps('b'),party:[]};run('renderProgress()');
  ok($('caps-current').innerHTML.includes('id="caps-auto"'));
}
// --- Notice after an automatic advance, with undo.
{
  const {ctx,$,commands,storage,run}=load();
  ctx.state=snapshot({enabled:true,read_only:false,event:null});
  run('renderLevelCapIndicators(state)');
  eq($('level-cap-auto-notice').hidden,true);
  ctx.state=snapshot({enabled:true,read_only:false,event:advance});
  run('renderLevelCapIndicators(state)');
  eq($('level-cap-auto-notice').hidden,false);
  eq($('level-cap-auto-text').textContent,'Etapa avanzada automáticamente a «Gimnasio 2» (Nv. 20). Chispa subió del nivel 14 al 15 y superó el límite de «Gimnasio 1» (Nv. 14).');
  eq($('level-cap-auto-action').textContent,'Deshacer');
  $('level-cap-auto-action').onclick();
  eq(plain(commands),[{action:'level_caps_current',stage:'a'}],'Deshacer es una elección manual de la etapa anterior');
  eq($('level-cap-auto-notice').hidden,true);
  eq(storage['progressive-cap-auto-dismissed'],'e1');
  run('renderLevelCapIndicators(state)');
  eq($('level-cap-auto-notice').hidden,true,'El mismo aviso no reaparece');
  ctx.state=snapshot({enabled:true,read_only:false,event:{...advance,id:'e2'}});
  run('renderLevelCapIndicators(state)');
  eq($('level-cap-auto-notice').hidden,false,'Un avance posterior sí avisa');
  $('level-cap-auto-dismiss').onclick();
  eq($('level-cap-auto-notice').hidden,true);
  eq(commands.length,1,'Ocultar no cambia la etapa');
}
// --- Suggestion when the next stage lowers the cap.
{
  const {ctx,$,commands,run}=load();
  const suggest={id:'s1',kind:'suggest',pokemon:'Chispa',from_level:30,to_level:31,from_stage:stage('x','Alto',30),to_stage:stage('y','Bajo',12)};
  ctx.state=snapshot({enabled:true,read_only:false,event:suggest});
  run('renderLevelCapIndicators(state)');
  eq($('level-cap-auto-text').textContent,'Chispa subió del nivel 30 al 31 y superó el límite de «Alto» (Nv. 30). La siguiente etapa, «Bajo» (Nv. 12), tiene un límite menor: no se avanzó automáticamente.');
  eq($('level-cap-auto-action').textContent,'Pasar a esa etapa');
  $('level-cap-auto-action').onclick();
  eq(plain(commands),[{action:'level_caps_current',stage:'y'}]);
}
// --- Dismissed before a reload; partner view; malformed or hostile events.
{
  const {ctx,$,run}=load({stored:'e1'});
  ctx.state=snapshot({enabled:true,read_only:false,event:advance});
  run('renderLevelCapIndicators(state)');
  eq($('level-cap-auto-notice').hidden,true,'Aviso ya ocultado antes de recargar');
}
{
  const {ctx,$,run}=load({companion:true});
  ctx.state=snapshot({enabled:true,read_only:false,event:advance});
  run('renderLevelCapIndicators(state)');
  eq($('level-cap-auto-notice').hidden,true,'En la vista del compañero no hay aviso');
}
{
  const {ctx,$,run}=load();
  for(const event of [{id:5},{id:'z',kind:'other',from_stage:stages[0],to_stage:stages[1]},{id:'z',kind:'advance'},'x',[]]){
    ctx.state=snapshot({enabled:true,read_only:false,event});
    run('renderLevelCapIndicators(state)');
    eq($('level-cap-auto-notice').hidden,true);
  }
  const hostile='<img src=x onerror=alert(1)>';
  ctx.state=snapshot({enabled:true,read_only:false,event:{...advance,id:'h',pokemon:hostile,to_stage:stage('b',hostile,20)}});
  run('renderLevelCapIndicators(state)');
  eq($('level-cap-auto-notice').hidden,false);
  ok($('level-cap-auto-text').textContent.includes(hostile)&&$('level-cap-auto-text').innerHTML==='','Se escribe como texto, no como HTML');
}
// --- Wiring.
const page=read('index.html');
for(const id of ['level-cap-auto-notice','level-cap-auto-text','level-cap-auto-action','level-cap-auto-dismiss'])ok(page.includes(`id="${id}"`),id);
ok(/id="level-cap-auto-notice"[^>]*role="status"[^>]*hidden/.test(page));
console.log(checks+' comprobaciones del avance automático de etapas (interfaz): OK');
