'use strict';
// Team assistant · recommendations: notes, separate measures, additions, substitutions and "complete with suggestions".
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const A=require('../web/analysis.js'),I=require('../web/insights.js');
const {loadShared,slice,read}=require('./ui_shared.js');
const data=JSON.parse(fs.readFileSync(path.join(__dirname,'../data/Analysis_USUM.json'),'utf8'));
const {chart,types}=data;
let checks=0;const ok=(value,message)=>{assert.ok(value,message);checks++};const eq=(a,b,message)=>{assert.deepEqual(a,b,message);checks++};
let ec=2000;
const move=(name,type,category='Físico',id=0)=>({id,name,type,category});
const mon=(nickname,species_id,monTypes,moves=[],extra={})=>({species_id,species:'Sp'+species_id,nickname,types:monTypes,ability:'—',ability_id:0,
  analysis_moves:moves,move_names:moves.map(m=>m.name),encryption_constant:ec++,origin_version:33,...extra});
const skarm=mon('Skarm',227,['Acero','Volador'],[move('Ala de Acero','Acero'),move('Cabeza de Hierro','Acero'),move('Pico Taladro','Volador')]);
const magne=mon('Magne',462,['Eléctrico','Acero'],[move('Foco Resplandor','Acero','Especial'),move('Rayo','Eléctrico','Especial')]);
const luca=mon('Luca',448,['Lucha','Acero'],[move('Puño Bala','Acero'),move('A Bocajarro','Lucha')]);
const gyara=mon('Gyara',130,['Agua','Volador'],[move('Cascada','Agua')]);
const chomp=mon('Chomp',445,['Dragón','Tierra'],[move('Terremoto','Tierra'),move('Garra Dragón','Dragón')]);
const ghost=mon('Gengar',94,['Fantasma','Veneno'],[move('Bola Sombra','Fantasma','Especial')],{ability_id:26});
const dead=mon('Caído',6,['Fuego','Volador'],[move('Lanzallamas','Fuego','Especial')]);
const egg=mon('Huevo',175,['Hada'],[],{egg:true});
const boxes={'1':Array(30).fill(null)};
[gyara,chomp,ghost,dead,egg].forEach((p,i)=>{boxes['1'][i]=p});
const live={game:'Ultra Moon 1.0',party:[skarm,magne,luca,null,null,null],boxes,box_verified:true,stale:false,connection:{status:'connected'},
  progress:{deaths:{[I.pokemonId(dead)]:{pokemon:dead}}},scan:{active:false}};
const steel=[skarm,magne,luca];
const pool=I.candidateEntries(live).filter(e=>e.kind==='box');
const ev=I.evaluateTeam(chart,types,steel,true);

// --- Notes: plain statements about the team.
const notes=I.teamNotes(ev);
eq(notes.defensive[0],'3 integrantes son débiles a Fuego y ninguno lo resiste ni es inmune.');
ok(notes.defensive.includes('2 integrantes son débiles a Tierra; Skarm es inmune.'),'Considera inmunidades, no solo cuenta debilidades');
ok(notes.defensive.includes('2 integrantes son débiles a Lucha y ninguno lo resiste ni es inmune.'));
ok(notes.offensive[0].startsWith('Ningún Pokémon del equipo dispone de un ataque supereficaz contra '));
ok(notes.offensive[0].includes('Tierra')&&notes.offensive[0].includes('Eléctrico'));
eq(I.teamNotes(I.evaluateTeam(chart,types,[mon('Mudo',1,['Planta'])],true)).offensive,['No se conocen movimientos ofensivos de este equipo: no se puede valorar su cobertura.']);
eq(I.teamNotes(I.evaluateTeam(chart,types,[],true)),{defensive:[],offensive:[]},'Un equipo vacío no recibe observaciones');

// --- Measures are separate.
const scores=I.teamScores(ev);
eq(Object.keys(scores).sort(),['coverage','covered','defense','diversity','exposed','redundancy','total']);
ok(scores.exposed.includes('Fuego')&&scores.exposed.includes('Lucha')&&!scores.exposed.includes('Tierra'));
eq(scores.covered,18-ev.uncovered.length);
eq(scores.diversity,4,'Acero, Volador, Eléctrico y Lucha');
eq(scores.redundancy,(3-1)+(4-2),'Tres de tipo Acero y cuatro ataques de Acero');
eq(I.teamScores(I.evaluateTeam(chart,types,[mon('Mudo',1,['Planta'])],true)).covered,0);

// --- compareTeams explains gains and losses.
const fireMon=mon('Brasa',5,['Fuego'],[move('Ascuas','Fuego','Especial')]);
const worse=I.compareTeams(ev,I.evaluateTeam(chart,types,[fireMon,magne,luca],true));
ok(worse.losses.includes('se pierde la inmunidad a Tierra'));
ok(worse.losses.includes('más integrantes débiles a Tierra (2 → 3)'));
ok(worse.gains.some(text=>text.startsWith('reduce las debilidades compartidas a Fuego (3 → 2)')));
const withChomp=I.compareTeams(ev,I.evaluateTeam(chart,types,[...steel,chomp],true));
ok(withChomp.gains.some(text=>text.startsWith('añade inmunidad a')&&text.includes('Eléctrico')),'Inmunidad nueva a Eléctrico');
ok(withChomp.gains.some(text=>text.startsWith('aporta resistencia a')&&text.includes('Fuego')));
ok(withChomp.gains.some(text=>text.startsWith('añade cobertura supereficaz frente a')&&text.includes('Eléctrico')));
ok(withChomp.delta>0&&withChomp.scores.coverage>0&&withChomp.scores.defense>0);
eq(I.compareTeams(ev,ev),{gains:[],losses:[],gained:{immunity:[],resist:[],coverage:[]},lost:{immunity:[],resist:[],coverage:[]},delta:0,
  scores:{defense:0,coverage:0,redundancy:0,diversity:0}},'Sin cambios no hay nada que explicar');

// --- suggestChanges: additions and single substitutions, deterministic and bounded.
const result=I.suggestChanges(chart,types,steel,pool,true);
const addNames=result.additions.map(a=>a.entry.pokemon.nickname);
ok(addNames.includes('Chomp')&&addNames.includes('Gyara'));
ok(!addNames.includes('Caído')&&!addNames.includes('Huevo'),'Ni muertos ni huevos');
ok(result.additions.every(a=>a.gains.length&&a.delta>0),'Cada sugerencia tiene un motivo');
for(let i=1;i<result.additions.length;i++)ok(result.additions[i-1].delta>=result.additions[i].delta);
ok(result.swaps.length>0);
for(const swap of result.swaps){
  ok(steel.includes(swap.out)&&steel[swap.index]===swap.out,'Indica a quién se sustituye');
  ok(swap.gains.length&&swap.delta>0&&Array.isArray(swap.losses));
}
eq(new Set(result.swaps.map(s=>s.entry.id)).size,result.swaps.length,'Cada candidato aparece una vez');
eq([result.considered,result.skipped],[3,0]);
eq(JSON.stringify(I.suggestChanges(chart,types,steel,pool,true)),JSON.stringify(result),'Determinista');
// BST plays no part: a high-BST Pokémon that repeats the team's typing is not preferred.
const titan=mon('Titán',376,['Acero'],[move('Puño Meteoro','Acero')],{base_stats:{HP:150,ATK:150,DEF:150,SPA:150,SPD:150,SPE:150}});
const titanEntry={pokemon:titan,id:I.pokemonId(titan),kind:'box',box:9,slot:0,key:'box:9:0',dead:false,egg:false,historical:false};
const withTitan=I.suggestChanges(chart,types,steel,[titanEntry,...pool],true);
ok(!withTitan.additions.some(a=>a.entry.pokemon===titan),'Un BST alto no basta para ser sugerido');
eq(withTitan.additions.map(a=>a.entry.id),result.additions.map(a=>a.entry.id));
// A full team only gets substitutions.
const six=[skarm,magne,luca,gyara,chomp,ghost];
eq(I.suggestChanges(chart,types,six,[titanEntry],true).additions,[]);
// Bounded pool.
const many=Array.from({length:400},(_,i)=>{const p=mon('N'+i,10,['Normal'],[move('Placaje','Normal')]);return {pokemon:p,id:I.pokemonId(p),kind:'box',box:1,slot:i,key:'k'+i,dead:false,egg:false}});
const bounded=I.suggestChanges(chart,types,steel,many,true);
eq([bounded.considered,bounded.skipped],[I.SUGGESTION_POOL,100],'Sin exploración ilimitada');
eq(I.suggestChanges(chart,types,[],[],true),{additions:[],swaps:[],considered:0,skipped:0});
// completeTeam fills free slots greedily and stops when nothing helps.
const filled=I.completeTeam(chart,types,steel,pool,true);
ok(filled.length>=1&&filled.length<=3);
eq(new Set(filled.map(f=>f.entry.id)).size,filled.length);
eq(I.completeTeam(chart,types,six,pool,true),[]);
eq(I.completeTeam(chart,types,steel,[titanEntry],true),[],'No rellena con Pokémon que no aportan');

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
const ctx={$,TypeAnalysis:A,TeamInsights:I,state:live,analysisData:{types,chart},companionView:false,analysisSignature:'',analysisTeamSignature:'',console,
  Option:function(text,value){this.text=text;this.value=String(value)},setText:(node,text)=>{node.textContent=text},
  getJSON:async()=>({teams:[]}),command:c=>commands.push(c),document:{activeElement:null,querySelectorAll:()=>[]}};
vm.createContext(ctx);loadShared(ctx);
vm.runInContext(slice('app/analysis-view.js','function multiplier(',"\nfor(const id of ['analysis-defense'"),ctx);
vm.runInContext(read('app/team-builder.js'),ctx);
$('builder-abilities').checked=true;
const click=dataset=>$('team-builder').listeners.click({target:{closest:()=>({dataset,disabled:false})}});
const slots=()=>[...$('builder-team').innerHTML.matchAll(/<li class="builder-slot[^"]*">(?:<img[^>]*>)?<div><strong>([^<]+)</g)].map(m=>m[1]);
$('analysis-section-builder').onclick();$('builder-use-party').onclick();
let report=$('builder-report').innerHTML;
ok(report.includes('<dt>Balance defensivo</dt>')&&report.includes('<dt>Tipos con ataque supereficaz</dt>')&&report.includes('<dt>Redundancias</dt>')&&report.includes('<dt>Tipos distintos</dt>'),'Medidas separadas');
ok(report.includes(`<dd>${scores.covered} / 18</dd>`));
ok(report.includes('3 integrantes son débiles a Fuego y ninguno lo resiste ni es inmune.'));
ok(report.includes('Incorporaciones posibles')&&report.includes('Sustituciones posibles'));
ok(/Sustituir a <b>[^<]+<\/b> por <b>[^<]+<\/b>/.test(report)&&report.includes('Motivo: '));
ok(report.includes('Añadir al borrador')&&report.includes('Aplicar al borrador'));
ok(report.includes('no «el mejor equipo»')&&report.includes('No tienen en cuenta niveles, estadísticas, objetos'),'Sin afirmaciones absolutas');
ok(report.includes('Se compararon 3 candidatos.'));
ok(!/data-builder-(toggle|swap)="[^"]*"[^>]*>[^<]*<\/button>[^]*Caído/.test(report.split('Cobertura ofensiva')[0])||!report.includes('Caído'),'Los muertos no se sugieren');
// Applying a substitution edits only the draft.
const first=result.swaps[0];
click({builderSwap:`${first.index}:${first.entry.id}`});
const expected=steel.map(p=>p.nickname);expected[first.index]=first.entry.pokemon.nickname;
eq(slots(),expected,'La sustitución se aplica al borrador');
click({builderSwap:`0:${first.entry.id}`});eq(slots(),expected,'Un Pokémon no puede entrar dos veces');
click({builderSwap:'9:33:1'});eq(slots(),expected);
// Complete with suggestions, then keep editing.
$('builder-use-party').onclick();
$('builder-complete').onclick();
eq(slots().length,3+filled.length);
eq(slots().slice(3),filled.map(f=>f.entry.pokemon.nickname));
ok($('builder-saved-status').textContent.includes('Puedes cambiarlas antes de guardar'));
click({builderRemove:'3'});
eq(slots().length,2+filled.length,'El equipo sugerido se puede modificar');
// Full team: no additions block; nothing to add.
$('builder-clear').onclick();
for(const p of six)click({builderToggle:I.pokemonId(p)});
ok(!$('builder-report').innerHTML.includes('Incorporaciones posibles'));
$('builder-complete').onclick();
eq($('builder-saved-status').textContent,'El equipo virtual ya tiene seis integrantes.');
// Empty draft: no advice at all.
$('builder-clear').onclick();
ok(!$('builder-report').innerHTML.includes('builder-advice'));
// Hostile names stay inert in suggestions.
const hostile='<img src=x onerror=alert(1)>';
const evil=mon(hostile,1,['Agua'],[move(hostile,'Agua')],{species:hostile});
ctx.state={...live,boxes:{'1':[evil,...Array(29).fill(null)]}};ctx.renderTeamBuilder();$('builder-use-party').onclick();
ok(!$('builder-report').innerHTML.includes('<img src=x'));
eq(commands.length,0,'Las recomendaciones no envían órdenes');
ok(read('index.html').includes('id="builder-complete"'));
ok(!/Math\.random|Date\.now/.test(read('insights.js')),'Reglas deterministas');
console.log(checks+' comprobaciones de recomendaciones: OK');
