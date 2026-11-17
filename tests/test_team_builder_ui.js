'use strict';
// Team assistant: candidates, manual selection, evaluation and the report markup.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const A=require('../web/analysis.js'),I=require('../web/insights.js');
const {loadShared,slice,read}=require('./ui_shared.js');
const data=JSON.parse(fs.readFileSync(path.join(__dirname,'../data/Analysis_USUM.json'),'utf8'));
const {chart,types}=data;
let checks=0;const ok=(value,message)=>{assert.ok(value,message);checks++};const eq=(a,b,message)=>{assert.deepEqual(a,b,message);checks++};
let ec=500;
const move=(name,type,category='Físico',id=0)=>({id,name,type,category});
const mon=(nickname,species_id,monTypes,moves=[],extra={})=>({species_id,species:'Sp'+species_id,nickname,types:monTypes,ability:'—',ability_id:0,
  analysis_moves:moves,move_names:moves.map(m=>m.name),encryption_constant:ec++,origin_version:33,...extra});
const skarm=mon('Skarm',227,['Acero','Volador'],[move('Ala de Acero','Acero'),move('Cabeza de Hierro','Acero'),move('Pico Taladro','Volador')]);
const magne=mon('Magne',462,['Eléctrico','Acero'],[move('Foco Resplandor','Acero','Especial'),move('Rayo','Eléctrico','Especial'),move('Onda Trueno','Eléctrico','Estado')]);
const luca=mon('Luca',448,['Lucha','Acero'],[move('Puño Bala','Acero'),move('A Bocajarro','Lucha')]);
const gyara=mon('Gyara',130,['Agua','Volador'],[move('Cascada','Agua')]);
const chomp=mon('Chomp',445,['Dragón','Tierra'],[move('Terremoto','Tierra'),move('Garra Dragón','Dragón')]);
const ghost=mon('Gengar',94,['Fantasma','Veneno'],[move('Bola Sombra','Fantasma','Especial')],{ability_id:26});
const dead=mon('Caído',143,['Normal'],[move('Golpe Cuerpo','Normal')]);
const egg=mon('Huevo',175,['Hada'],[],{egg:true});
const boxes={'1':Array(30).fill(null),'2':Array(30).fill(null)};
boxes['1'][0]=gyara;boxes['1'][1]=chomp;boxes['1'][2]=dead;boxes['2'][5]=ghost;boxes['2'][6]=egg;
// The same specimen read twice (stale box copy of a party member) counts once.
boxes['2'][7]={...skarm};
const live={game:'Ultra Moon 1.0',party:[skarm,magne,luca,null,null,null],boxes,box_verified:true,stale:false,connection:{status:'connected'},
  progress:{deaths:{[I.pokemonId(dead)]:{pokemon:dead}}},scan:{active:false}};

// --- Candidates.
const candidates=I.candidateEntries(live);
eq(candidates.map(e=>e.pokemon.nickname),['Skarm','Magne','Luca','Gyara','Chomp','Caído','Gengar','Huevo'],'Equipo primero y sin ejemplares repetidos');
ok(candidates.every(e=>e.historical===false),'Lectura en vivo y verificada');
ok(I.candidateEntries({...live,stale:true}).every(e=>e.historical),'Sin conexión todo es lectura guardada');
eq(I.candidateEntries({...live,box_verified:false}).map(e=>e.historical),[false,false,false,true,true,true,true,true],'Cajas sin verificar: históricas; equipo en vivo');
eq(I.candidateEntries({...live,party:[{species:'x'}]}).some(e=>e.id===null),false,'Sin identificador estable no hay candidato');
eq(I.filterEntries(candidates,{hideDead:true,hideEggs:true}).map(e=>e.pokemon.nickname),['Skarm','Magne','Luca','Gyara','Chomp','Gengar'],'Por defecto sin muertos ni huevos');
eq(I.filterEntries(candidates,{kind:'box',hideEggs:true}).length,4);

// --- Resolution of saved members.
const members=[I.memberOf(candidates[0]),{id:'33:999999',species_id:1,species:'Bulbasaur',nickname:'Perdido'},{...I.memberOf(candidates[4]),species_id:444,species:'Gabite'}];
eq(members[0],{id:I.pokemonId(skarm),species_id:227,species:'Sp227',nickname:'Skarm'});
const resolved=I.resolveTeam(members,candidates);
eq(resolved.map(r=>r.status),['located','missing','changed']);
eq(resolved[1].entry,null,'Un ausente no se sustituye por otro Pokémon');
eq(resolved[2].entry.pokemon.nickname,'Chomp','Mismo ejemplar tras evolucionar');
eq(I.resolveTeam(Array(9).fill(members[0]),candidates).length,6,'Máximo seis');

// --- Evaluation built on TypeAnalysis.
const steel=[skarm,magne,luca];
const ev=I.evaluateTeam(chart,types,steel,true);
eq(ev.size,3);eq(ev.knownMoves,7,'Los movimientos de estado no cuentan');
const fire=ev.sharedWeaknesses.find(w=>w.type==='Fuego');
eq(fire.weak,3);eq(fire.answers,[],'Tres débiles a Fuego y nadie lo resiste');
const ground=ev.sharedWeaknesses.find(w=>w.type==='Tierra');
eq(ground.members.sort(),['Luca','Magne']);eq(ground.answers,['Skarm'],'Skarm es inmune a Tierra');
eq(ev.sharedWeaknesses[0].type,'Fuego','La debilidad más repetida va primero');
ok(ev.unresisted.includes('Fuego')&&!ev.unresisted.includes('Tierra'));
ok(ev.immunities.some(i=>i.type==='Veneno'&&i.members.length===3),'Acero es inmune a Veneno');
ok(ev.resistances.some(r=>r.type==='Planta'));
ok(ev.uncovered.includes('Tierra')&&ev.uncovered.includes('Eléctrico'),'Sin ataque supereficaz contra Tierra ni Eléctrico');
ok(!ev.uncovered.includes('Hada')&&!ev.uncovered.includes('Agua'));
eq(ev.sharedTypes[0],{type:'Acero',members:['Skarm','Magne','Luca']});
eq(ev.attackTypes[0].type,'Acero');eq(ev.attackTypes[0].count,4);
for(const row of ev.offense)for(const hit of row.hitters)eq(hit.value,A.offensive(chart,hit.move,hit.pokemon,[row.type],true),'Sin reglas duplicadas');
const withChomp=I.evaluateTeam(chart,types,[...steel,chomp],true);
ok(!withChomp.uncovered.includes('Eléctrico'),'Terremoto cubre Eléctrico');
ok(!withChomp.unresisted.includes('Fuego'),'Dragón resiste Fuego');
const empty=I.evaluateTeam(chart,types,[],true);
eq([empty.size,empty.unresisted,empty.uncovered,empty.sharedWeaknesses],[0,[],[],[]],'Un equipo vacío no afirma nada');
const noMoves=I.evaluateTeam(chart,types,[mon('Mudo',1,['Planta'])],true);
eq([noMoves.knownMoves,noMoves.uncovered,noMoves.walled],[0,[],[]],'Sin movimientos conocidos no se inventa cobertura');
eq(I.evaluateTeam(chart,types,[ghost],true).immunities.map(i=>i.type).sort(),['Lucha','Normal','Tierra'],'Levitación cuenta con habilidades');
eq(I.evaluateTeam(chart,types,[ghost],false).immunities.map(i=>i.type).sort(),['Lucha','Normal']);

// --- View in a fake DOM.
class El{
  constructor(id){Object.assign(this,{id,children:[],options:[],innerHTML:'',textContent:'',value:'',hidden:false,checked:false,disabled:false,listeners:{},dataset:{},attributes:{}})}
  replaceChildren(){this.children=[];this.options=[]}
  add(o){this.options.push(o)}
  addEventListener(type,fn){this.listeners[type]=fn}
  setAttribute(k,v){this.attributes[k]=String(v)}
  focus(){focusedNode=this}
}
let focusedNode=null;
const nodes={};const $=id=>nodes[id]??=new El(id);
const commands=[];
const ctx={$,TypeAnalysis:A,TeamInsights:I,state:live,analysisData:{types,chart},companionView:false,analysisSignature:'',analysisTeamSignature:'',console,
  Option:function(text,value){this.text=text;this.value=String(value)},setText:(node,text)=>{node.textContent=text},
  command:c=>commands.push(c),document:{activeElement:null,querySelectorAll:()=>[]}};
vm.createContext(ctx);loadShared(ctx);
vm.runInContext(slice('app/analysis-view.js','function multiplier(',"\nfor(const id of ['analysis-defense'"),ctx);
vm.runInContext(read('app/team-builder.js'),ctx);
$('builder-abilities').checked=true;
const click=dataset=>$('team-builder').listeners.click({target:{closest:()=>({dataset,disabled:false})}});
const slots=()=>[...$('builder-team').innerHTML.matchAll(/<li class="builder-slot[^"]*">(?:<img[^>]*>)?<div><strong>([^<]+)</g)].map(m=>m[1]);
const shownCandidates=()=>[...$('builder-candidates').innerHTML.matchAll(/data-builder-toggle="[^"]+"[^>]*aria-pressed="(true|false)"[^>]*>(?:<img[^>]*>)<strong>([^<]+)</g)].map(m=>[m[2],m[1]==='true']);
// Opening the assistant.
eq(ctx.teamBuilderActive(),false);
$('analysis-section-builder').onclick();
eq(ctx.teamBuilderActive(),true);
eq([$('analysis-current').hidden,$('team-builder').hidden],[true,false]);
eq($('analysis-section-builder').attributes['aria-pressed'],'true');
eq($('builder-count').textContent,'0 / 6');
eq(shownCandidates().map(c=>c[0]),['Skarm','Magne','Luca','Gyara','Chomp','Gengar'],'Muertos y huevos excluidos por defecto');
ok($('builder-report').innerHTML.includes('Elige tu primer integrante'));
eq(($('builder-team').innerHTML.match(/builder-slot-empty/g)||[]).length,6);
ok($('builder-candidates').innerHTML.includes('Caja 1 · 2')&&$('builder-candidates').innerHTML.includes('Equipo · 1'));
// Manual selection: add, coverage changes, remove, reorder.
$('builder-use-party').onclick();
eq(slots(),['Skarm','Magne','Luca']);eq($('builder-count').textContent,'3 / 6');
let report=$('builder-report').innerHTML;
ok(/<b>Fuego<\/b>: 3 débiles \(Skarm, Magne, Luca\) · nadie lo resiste/.test(report),'Debilidad compartida explicada');
ok(/<b>Tierra<\/b>: 2 débiles \(Magne, Luca\) · lo resisten o son inmunes: Skarm/.test(report));
ok(/Sin ataque supereficaz<\/h3><ul><li>[^<]*Tierra/.test(report));
ok(report.includes('3 integrantes de tipo <b>Acero</b>')&&report.includes('4 ataques de tipo <b>Acero</b>'),'Redundancias defensiva y ofensiva');
ok(report.includes('class="fx-chart"')&&report.includes('coverage-grid'),'Reutiliza el gráfico y la cobertura del análisis');
click({builderToggle:I.pokemonId(chomp)});
eq(slots(),['Skarm','Magne','Luca','Chomp']);
report=$('builder-report').innerHTML;
ok(!/Sin ataque supereficaz<\/h3><ul><li>[^<]*Eléctrico/.test(report),'La cobertura cambia al añadir a Chomp');
ok(/lo resisten o son inmunes: Chomp/.test(report),'Chomp resiste Fuego');
eq(shownCandidates().find(c=>c[0]==='Chomp')[1],true,'Candidato marcado como seleccionado');
click({builderMove:'3:-1'});
eq(slots(),['Skarm','Magne','Chomp','Luca'],'Orden de integrantes');
click({builderMove:'0:-1'});eq(slots(),['Skarm','Magne','Chomp','Luca'],'No se sale del equipo');
click({builderRemove:'1'});
eq(slots(),['Skarm','Chomp','Luca']);
click({builderToggle:I.pokemonId(chomp)});
eq(slots(),['Skarm','Luca'],'Pulsar un seleccionado lo quita');
// Six at most.
for(const p of [magne,gyara,chomp,ghost])click({builderToggle:I.pokemonId(p)});
eq($('builder-count').textContent,'6 / 6');
$('builder-dead').checked=true;$('builder-dead').onchange();
ok(/data-builder-toggle="[^"]+" data-focus="[^"]+" aria-pressed="false" title="Equipo completo[^"]*" disabled>(?:<img[^>]*>)<strong>Caído/.test($('builder-candidates').innerHTML),'Con seis no se puede añadir otro');
ok($('builder-candidates').innerHTML.includes('Muerto'));
click({builderToggle:I.pokemonId(dead)});
eq($('builder-count').textContent,'6 / 6','El séptimo se ignora');
// Filters and sorting of candidates.
$('builder-dead').checked=false;$('builder-type').value='Volador';$('builder-type').onchange();
eq(shownCandidates().map(c=>c[0]),['Skarm','Gyara']);
$('builder-type').value='';$('builder-source').value='box';$('builder-search').value='ch';$('builder-search').oninput();
eq(shownCandidates().map(c=>c[0]),['Chomp']);
$('builder-source').value='';$('builder-search').value='';$('builder-sort').value='name';$('builder-sort').onchange();
eq(shownCandidates().map(c=>c[0]),['Chomp','Gengar','Gyara','Luca','Magne','Skarm']);
eq($('builder-candidate-count').textContent,'6 de 8');
// A member that disappears is flagged, never replaced.
$('builder-clear').onclick();eq(slots(),[]);
click({builderToggle:I.pokemonId(ghost)});click({builderToggle:I.pokemonId(skarm)});
const withoutGhost={...live,boxes:{'1':boxes['1'],'2':Array(30).fill(null)}};
ctx.state=withoutGhost;ctx.renderTeamBuilder();
eq(slots(),['Gengar','Skarm']);
ok($('builder-team').innerHTML.includes('builder-slot-missing')&&$('builder-team').innerHTML.includes('No localizado en el equipo ni en las cajas leídas'));
ok($('builder-status').textContent.startsWith('1 integrante no localizado'));
ok(!$('builder-report').innerHTML.includes('Gengar'),'El ausente no cuenta en la cobertura');
// Saved readings are labelled.
ctx.state={...live,stale:true,connection:{status:'disconnected'}};ctx.renderTeamBuilder();
ok($('builder-candidates').innerHTML.includes('Lectura guardada')&&$('builder-team').innerHTML.includes('lectura guardada'));
// Another game or the partner view starts a new draft.
ctx.state={...live,game:'Ultra Sun 1.0'};ctx.renderTeamBuilder();
eq(slots(),[],'Los equipos virtuales no se mezclan entre juegos');
ctx.state=live;ctx.renderTeamBuilder();click({builderToggle:I.pokemonId(skarm)});eq(slots(),['Skarm']);
ctx.companionView=true;ctx.renderTeamBuilder();eq(slots(),[],'Ni con la vista del compañero');
ctx.companionView=false;
// Same frame: nothing is rebuilt. Hostile names stay inert. No command is sent.
ctx.renderTeamBuilder();$('builder-report').innerHTML='sentinel';ctx.renderTeamBuilder();
eq($('builder-report').innerHTML,'sentinel');
const hostile='<img src=x onerror=alert(1)>';
ctx.state={...live,party:[mon(hostile,1,[hostile],[move(hostile,hostile)],{species:hostile})],boxes:{}};
ctx.renderTeamBuilder();$('builder-use-party').onclick();
for(const id of ['builder-team','builder-candidates','builder-report'])ok(!$(id).innerHTML.includes('<img src=x'),id+' escapa nombres');
eq(commands.length,0,'El asistente no envía órdenes al juego');
function copyingPartyRespectsDeadFilter(){
  ctx.state={...live,party:[dead,skarm,null,null,null,null]};ctx.renderTeamBuilder();
  $('builder-dead').checked=false;$('builder-use-party').onclick();
  eq(slots(),['Skarm'],'Usar el equipo actual excluye muertos por defecto');
  $('builder-dead').checked=true;$('builder-use-party').onclick();
  eq(slots(),['Caído','Skarm'],'La inclusión de muertos necesita activar el control');
}
copyingPartyRespectsDeadFilter();
function virtualTeamComparisonTracksCurrentParty(){
  ctx.state=live;ctx.renderTeamBuilder();$('builder-clear').onclick();
  for(const p of [skarm,magne,luca,chomp])click({builderToggle:I.pokemonId(p)});
  let report=$('builder-report').innerHTML;
  ok(report.includes('Comparación con el equipo actual'),'El borrador tiene una comparación visible');
  ok(/data-metric="members"[^]*?data-side="current">3<[^]*?data-side="virtual">4</.test(report),'Compara el equipo real de tres con el virtual de cuatro');
  ok(report.includes('añade cobertura supereficaz frente a')&&report.includes('Eléctrico'),'Explica la cobertura ganada frente al equipo actual');
  $('builder-clear').onclick();click({builderToggle:I.pokemonId(skarm)});
  ok(/data-metric="members"[^]*?data-side="current">3<[^]*?data-side="virtual">1</.test($('builder-report').innerHTML),'Compara equipos incompletos de un integrante');
  $('builder-clear').onclick();
  for(const p of [ghost,skarm,magne,luca,gyara,chomp])click({builderToggle:I.pokemonId(p)});
  ctx.state=withoutGhost;ctx.renderTeamBuilder();
  report=$('builder-report').innerHTML;
  ok(/data-metric="members"[^]*?data-side="current">3<[^]*?data-side="virtual">5</.test(report),'Con seis guardados y uno ausente solo compara cinco localizados');
  ok(!report.includes('Incorporaciones posibles'),'Un ausente conserva el sexto hueco: no hay botones de añadir inertes');
  ok($('builder-team').innerHTML.includes('No localizado'),'La comparación no sustituye al ausente');
  ctx.state={...withoutGhost,stale:true};ctx.renderTeamBuilder();
  ok($('builder-report').innerHTML.includes('Comparación basada en lecturas guardadas'),'No presenta datos históricos como equipo en vivo');
  ctx.state={...live,party:[null,null,null,null,null,null]};ctx.renderTeamBuilder();
  ok($('builder-report').innerHTML.includes('No hay un equipo actual leído para comparar'),'Equipo actual vacío: sin conclusiones inventadas');
}
virtualTeamComparisonTracksCurrentParty();
$('analysis-section-current').onclick();
eq([ctx.teamBuilderActive(),$('analysis-current').hidden,$('team-builder').hidden],[false,false,true]);

// --- Wiring.
const page=read('index.html'),css=read('style.css'),source=read('app/team-builder.js');
for(const id of ['analysis-section-current','analysis-section-builder','analysis-current','team-builder','builder-team','builder-candidates','builder-report','builder-search','builder-type','builder-source','builder-sort','builder-dead','builder-abilities','builder-use-party','builder-clear','builder-count','builder-status'])
  ok(page.includes(`id="${id}"`),id);
ok(page.indexOf('src="/app/analysis-view.js"')<page.indexOf('src="/app/team-builder.js"'));
ok(!/command\(|fetch\(/.test(source.split('// --- Saved teams')[0]),'La selección manual no llama al servicio');
ok(read('app/analysis-view.js').includes("typeof teamBuilderActive==='function'&&teamBuilderActive()"));
ok(css.includes('.builder-team{')&&css.includes('.builder-candidate[aria-pressed="true"]'));
console.log(checks+' comprobaciones del asistente de equipos: OK');
