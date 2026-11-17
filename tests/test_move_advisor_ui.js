'use strict';
// Team assistant · move advisor: attack types, redundancy, thin coverage and type suggestions with their evidence level.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const A=require('../web/analysis.js'),I=require('../web/insights.js');
const {loadShared,slice,read}=require('./ui_shared.js');
const data=JSON.parse(fs.readFileSync(path.join(__dirname,'../data/Analysis_USUM.json'),'utf8'));
const {chart,types}=data;
let checks=0;const ok=(value,message)=>{assert.ok(value,message);checks++};const eq=(a,b,message)=>{assert.deepEqual(a,b,message);checks++};
let ec=3000;
const move=(name,type,category='Físico',id=0)=>({id,name,type,category});
const mon=(nickname,monTypes,moves=[],extra={})=>({species_id:1,species:nickname,nickname,types:monTypes,ability:'—',ability_id:0,
  analysis_moves:[...moves,...Array(Math.max(0,4-moves.length)).fill(null)],move_names:moves.map(m=>m.name),encryption_constant:ec++,origin_version:33,...extra});
const skarm=mon('Skarm',['Acero','Volador'],[move('Ala de Acero','Acero',undefined,211),move('Cabeza de Hierro','Acero',undefined,442),move('Pico Taladro','Volador',undefined,65),move('Respiro','Volador','Estado',355)]);
const magne=mon('Magne',['Eléctrico','Acero'],[move('Foco Resplandor','Acero','Especial',430),move('Rayo','Eléctrico','Especial',85)]);
const luca=mon('Luca',['Lucha','Acero'],[move('Puño Bala','Acero',undefined,418),move('A Bocajarro','Lucha',undefined,370)]);
const steel=[skarm,magne,luca];
const ev=I.evaluateTeam(chart,types,steel,true);
const advice=I.moveAdvice(chart,types,ev,true);

// --- Pure advice.
eq(advice.attackTypes[0].type,'Acero');eq(advice.attackTypes[0].count,4);
eq(advice.stacked.map(s=>s.type),['Acero'],'Muchos ataques de tipo Acero');
eq(advice.uncovered,ev.uncovered);
ok(advice.uncovered.includes('Eléctrico'));
const ground=advice.suggestions.find(s=>s.type==='Tierra');
ok(ground&&ground.covers.includes('Eléctrico'),'Tierra mejora la cobertura frente a Eléctrico');
eq(advice.suggestions[0].type,'Tierra','El tipo que más cobertura nueva aporta va primero');
eq(advice.lines,['Tienes 4 ataques de tipo Acero. Te vendría bien un movimiento de tipo Tierra para mejorar la cobertura frente a Veneno, Fuego, Eléctrico.']);
for(const s of advice.suggestions){
  ok(!ev.attackTypes.some(a=>a.type===s.type),'No se sugiere un tipo que el equipo ya tiene');
  for(const target of s.covers){ok(ev.uncovered.includes(target));eq(A.basic(chart,s.type,[target])>1,true,'Cobertura calculada con TypeAnalysis')}
  ok(s.covers.length+s.reinforces.length>0);
}
ok(advice.suggestions.length<=6);
ok(advice.thin.every(t=>ev.offense.find(row=>row.type===t.type).hitters.length===1),'Poca cobertura: un solo ataque supereficaz');
const skarmRoom=advice.room.find(r=>r.pokemon==='Skarm');
eq(skarmRoom,{pokemon:'Skarm',free:0,repeated:[{type:'Acero',moves:['Ala de Acero','Cabeza de Hierro']}]});
eq(advice.room.find(r=>r.pokemon==='Magne').free,2);
eq([advice.hasLearnsets,advice.learnable],[false,[]],'Sin datos de aprendizaje no se nombra ningún movimiento');
ok(!JSON.stringify(advice.suggestions).includes('Terremoto'),'Nunca un movimiento concreto sin evidencia');
// Evidence present: only moves the snapshot lists as learnable, of a suggested type, not already known, not status.
const taught=mon('Magne',['Eléctrico','Acero'],[move('Rayo','Eléctrico','Especial',85)],{learnable_moves:[
  {...move('Terratemblor','Tierra',undefined,523),source:'MT de Definitive Game Data'},move('Rayo','Eléctrico','Especial',85),
  move('Bofetón Lodo','Tierra','Estado',189),move('Viento Hielo','Hielo','Especial',196),null,'Terremoto']});
const withData=I.moveAdvice(chart,types,I.evaluateTeam(chart,types,[skarm,taught,luca],true),true);
eq(withData.hasLearnsets,true);
ok(withData.learnable.some(l=>l.move==='Terratemblor'&&l.pokemon==='Magne'&&l.type==='Tierra'&&l.source==='MT de Definitive Game Data'));
ok(!withData.learnable.some(l=>l.move==='Rayo'||l.move==='Bofetón Lodo'),'Ni conocidos ni de estado');
ok(!withData.learnable.some(l=>l.pokemon!=='Magne'),'Solo quien tiene evidencia');
// Abilities change the attack type (Pixilate turns Normal moves into Fairy).
const pixie=mon('Sylv',['Hada'],[move('Vozarrón','Normal','Especial',304)],{ability_id:182});
eq(I.moveAdvice(chart,types,I.evaluateTeam(chart,types,[pixie],true),true).attackTypes[0].type,'Hada');
eq(I.moveAdvice(chart,types,I.evaluateTeam(chart,types,[pixie],false),false).attackTypes[0].type,'Normal');
// Nothing known: no suggestions, no invented coverage.
const mute=I.moveAdvice(chart,types,I.evaluateTeam(chart,types,[mon('Mudo',['Planta'])],true),true);
eq([mute.attackTypes,mute.suggestions,mute.uncovered,mute.lines],[[],[],[],[]]);
eq(mute.room,[{pokemon:'Mudo',free:4,repeated:[]}]);
const none=I.moveAdvice(chart,types,I.evaluateTeam(chart,types,[],true),true);
eq([none.suggestions,none.room],[[],[]]);

// --- View.
class El{
  constructor(id){Object.assign(this,{id,options:[],innerHTML:'',textContent:'',value:'',hidden:false,checked:false,disabled:false,listeners:{},dataset:{},attributes:{}})}
  replaceChildren(){this.options=[]}
  add(o){this.options.push(o)}
  addEventListener(type,fn){this.listeners[type]=fn}
  setAttribute(k,v){this.attributes[k]=String(v)}
  focus(){}
}
const nodes={};const $=id=>nodes[id]??=new El(id);
const commands=[];
const live={game:'Ultra Moon 1.0',party:[skarm,magne,luca,null,null,null],boxes:{},box_verified:true,stale:false,connection:{status:'connected'},progress:{},scan:{active:false}};
const ctx={$,TypeAnalysis:A,TeamInsights:I,state:live,analysisData:{types,chart},companionView:false,analysisSignature:'',analysisTeamSignature:'',console,
  Option:function(text,value){this.text=text;this.value=String(value)},setText:(node,text)=>{node.textContent=text},
  getJSON:async()=>({teams:[]}),command:c=>commands.push(c),document:{activeElement:null,querySelectorAll:()=>[]}};
vm.createContext(ctx);loadShared(ctx);
vm.runInContext(slice('app/analysis-view.js','function multiplier(',"\nfor(const id of ['analysis-defense'"),ctx);
vm.runInContext(read('app/team-builder.js'),ctx);
$('builder-abilities').checked=true;
$('analysis-section-builder').onclick();
ok(!$('builder-report').innerHTML.includes('Asesor de movimientos'),'Sin equipo no hay asesor');
$('builder-use-party').onclick();
let report=$('builder-report').innerHTML;
ok(report.includes('Asesor de movimientos'));
ok(report.includes('Tienes 4 ataques de tipo Acero. Te vendría bien un movimiento de tipo Tierra para mejorar la cobertura frente a Veneno, Fuego, Eléctrico.'));
ok(/<b>Acero<\/b> ×4: Ala de Acero \(Skarm\), Cabeza de Hierro \(Skarm\), Foco Resplandor \(Magne\), Puño Bala \(Luca\)/.test(report),'Movimientos ofensivos por tipo');
ok(!/×\d+: [^<]*Respiro/.test(report),'Los movimientos de estado no cuentan como ataques');
ok(report.includes('El equipo tiene 4 ataques de tipo <b>Acero</b>.')&&report.includes('Skarm conoce 2 ataques de tipo <b>Acero</b>: Ala de Acero, Cabeza de Hierro.'));
ok(/Sin ataque supereficaz: [^<]*Eléctrico/.test(report));
ok(report.includes('Sugerencia genérica de tipo</span> Un movimiento de tipo <b>Tierra</b> añadiría cobertura frente a Veneno, Fuego, Eléctrico'));
ok(report.includes('Movimiento conocido')&&report.includes('Información no disponible'),'Niveles de evidencia visibles');
ok(!report.includes('Disponible en datos verificables'),'Sin datos de aprendizaje no se muestra esa categoría');
ok(report.includes('solo se sugieren tipos de movimiento, no movimientos concretos')&&report.includes('la ROM puede estar randomizada'));
ok(report.includes('Magne tiene 2 espacios libres de movimiento.'));
ok(report.includes('El asesor no cambia movimientos en el juego.'));
// With verifiable learnset data the concrete move is named and labelled.
ctx.state={...live,party:[skarm,{...taught,encryption_constant:magne.encryption_constant},luca,null,null,null]};ctx.renderTeamBuilder();
report=$('builder-report').innerHTML;
ok(report.includes('Disponible en datos verificables</span> Magne puede aprender <b>Terratemblor</b> (Tierra) según MT de Definitive Game Data.'));
ok(report.includes('Los movimientos concretos proceden de los datos importados de esta partida.'));
// Hostile move names stay inert.
const hostile='<img src=x onerror=alert(1)>';
ctx.state={...live,party:[mon(hostile,['Agua'],[move(hostile,hostile),move(hostile,hostile),move(hostile,hostile)],{learnable_moves:[{...move(hostile,'Tierra'),source:hostile}]})]};
ctx.renderTeamBuilder();$('builder-use-party').onclick();
ok($('builder-report').innerHTML.includes('Asesor de movimientos')&&!$('builder-report').innerHTML.includes('<img src=x'));
eq(commands.length,0,'El asesor no envía órdenes');
ok(read('style.css').includes('.move-evidence{'));
console.log(checks+' comprobaciones del asesor de movimientos: OK');
