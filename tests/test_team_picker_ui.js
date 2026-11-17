'use strict';
// The guided picker never adds a Pokémon until the owner explicitly chooses it.
const assert=require('node:assert/strict'),vm=require('node:vm');
const A=require('../web/analysis.js'),I=require('../web/insights.js');
const {loadShared,read}=require('./ui_shared.js');
const {chart,types}=require('../data/Analysis_USUM.json');
const mon=(id,name,type,level,bases)=>({species_id:id,species:name,nickname:name,types:[type],level,base_stats:{HP:bases,ATK:bases,DEF:bases,SPA:bases,SPD:bases,SPE:bases},
  encryption_constant:id,origin_version:33,ability_id:0,analysis_moves:[{name:'Ataque',type,category:'Físico'}]});
const a=mon(1,'Uno','Planta',10,50),b=mon(2,'Dos','Agua',50,70),c=mon(3,'Tres','Fuego',30,60);
class El{
  constructor(id){Object.assign(this,{id,innerHTML:'',textContent:'',value:'',checked:false,disabled:false,open:false,options:[],listeners:{},dataset:{},attributes:{}})}
  add(o){this.options.push(o)} replaceChildren(){this.options=[]}
  addEventListener(t,fn){this.listeners[t]=fn} setAttribute(k,v){this.attributes[k]=String(v)} focus(){}
  showModal(){this.open=true} close(){this.open=false;this.listeners.close?.()}
}
const nodes={};const $=id=>nodes[id]??=new El(id);
const snapshot={game:'Ultra Moon 1.0',party:[a],boxes:{1:[b,c]},progress:{},stale:false,box_verified:true,connection:{status:'connected'}};
const ctx={$,TypeAnalysis:A,TeamInsights:I,state:snapshot,analysisData:{types,chart},companionView:false,analysisSignature:'',console,
  Option:function(text,value){this.text=text;this.value=String(value)},setText:(n,t)=>{n.textContent=t},
  getJSON:async()=>({teams:[],scope:'test-scope'}),document:{activeElement:null,querySelectorAll:()=>[]},
  defenseChart:()=>'',coverageReport:()=>'',command:()=>{throw Error('No game command is allowed')},
  renderAnalysis:()=>ctx.renderTeamBuilder()};
vm.createContext(ctx);loadShared(ctx);vm.runInContext(read('app/team-builder.js'),ctx);
const members=()=>JSON.parse(vm.runInContext('JSON.stringify(builderMembers.map(m=>m.id))',ctx));
const click=dataset=>$('team-builder').listeners.click({target:{closest:()=>({dataset,disabled:false})}});
const pick=id=>$('builder-picker-options').listeners.click({target:{closest:()=>({dataset:{builderPick:id},disabled:false})}});
const offered=()=>[...$('builder-picker-options').innerHTML.matchAll(/data-builder-pick="([^"]+)"/g)].map(m=>m[1]);
const ordered=()=>[...$('builder-candidates').innerHTML.matchAll(/data-builder-toggle="([^"]+)"/g)].map(m=>m[1]);
$('builder-abilities').checked=true;$('builder-sort').value='storage';$('analysis-section-builder').onclick();
function emptySlotStartsExplicitChoice(){
  assert.match($('builder-team').innerHTML,/data-builder-slot="0"/);
  click({builderSlot:'0'});
  assert.equal($('builder-picker').open,true);
  assert.equal(members().length,0);
  assert.ok(offered().length>0&&offered().length<=6);
  $('builder-picker-close').onclick();assert.equal($('builder-picker').open,false);
}
function completeGuidesOneChoiceAtATime(){
  $('builder-use-party').onclick();const before=members();
  $('builder-complete').onclick();assert.deepEqual(members(),before,'Opening guidance cannot autocomplete');
  assert.equal($('builder-picker').open,true);
  const offeredId=offered()[0];pick(offeredId);
  assert.deepEqual(members(),[I.pokemonId(a),offeredId],'Only the chosen Pokémon enters');
  assert.equal($('builder-picker').open,true,'Next empty slot is proposed without adding it');
  assert.match($('builder-picker-title').textContent,/3/);
  pick(offeredId);assert.equal(members().length,2,'The same specimen cannot enter twice');
  $('builder-picker-close').onclick();assert.equal(members().length,2);
}
function candidateSortingTracksFreshValues(){
  $('builder-sort').value='level';$('builder-sort').onchange();
  assert.deepEqual(ordered(),[I.pokemonId(b),I.pokemonId(c),I.pokemonId(a)]);
  ctx.state={...snapshot,party:[{...a,level:90}]};ctx.renderTeamBuilder();
  assert.deepEqual(ordered(),[I.pokemonId(a),I.pokemonId(b),I.pokemonId(c)],'Fresh levels must actually reorder candidates');
  $('builder-sort').value='bst';$('builder-sort').onchange();
  assert.deepEqual(ordered(),[I.pokemonId(b),I.pokemonId(c),I.pokemonId(a)]);
}
function switchingGameDismissesPendingChoice(){
  $('builder-complete').onclick();assert.equal($('builder-picker').open,true);
  ctx.state={...snapshot,game:'Pokémon X 1.0'};ctx.renderTeamBuilder();
  assert.equal($('builder-picker').open,false);assert.deepEqual(members(),[]);
}
function supplementalChoicesDiscloseSharedWeaknesses(){
  const duplicate={...a,encryption_constant:99,nickname:'Otra planta',analysis_moves:[]};
  ctx.state={...snapshot,party:[{...a,analysis_moves:[]}],boxes:{1:[duplicate]}};ctx.renderTeamBuilder();$('builder-use-party').onclick();
  $('builder-complete').onclick();
  const html=$('builder-picker-options').innerHTML;
  assert.match(html,/Volador/);assert.match(html,/Fuego/);
  assert.ok(!html.includes('Sin nuevas debilidades compartidas ni pérdida de cobertura'));
  $('builder-picker-close').onclick();ctx.state=snapshot;ctx.renderTeamBuilder();
}
for(const test of [emptySlotStartsExplicitChoice,completeGuidesOneChoiceAtATime,candidateSortingTracksFreshValues,supplementalChoicesDiscloseSharedWeaknesses,switchingGameDismissesPendingChoice]){
  test();console.log(test.name+': OK');
}
