'use strict';
const assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const I=require('../web/insights.js');
const {loadShared}=require('./ui_shared.js');
const nodes={};const $=id=>nodes[id]??={innerHTML:'',textContent:'',value:'',checked:true};
const ctx={$,TeamInsights:I,state:{game:'Pokémon X 1.0'},companionView:false,document:{addEventListener(){}},renderBoxes(){},renderAnalysis(){}};
vm.createContext(ctx);loadShared(ctx);
vm.runInContext(fs.readFileSync('web/app/analysis-pokemon.js','utf8'),ctx);
const p={species_id:6,species:'Charizard',nickname:'Brasa',form:0,item_id:660,encryption_constant:123,origin_version:24,
  types:['Fuego','Volador'],ability_id:66,ability:'Mar Llamas',stats:{ATQ:120},max_hp:150,level:50,
  mega_preview:{form:1,label:'Mega X',item_id:660,types:['Fuego','Dragón'],ability_id:181,ability:'Garra Dura',base_stats:{HP:78,ATK:130,DEF:111,SPA:130,SPD:85,SPE:100},base_stats_source:'Referencia XY',reference_only:true}};
function mega_is_explicit_and_never_mutates_snapshot(){
  assert.equal(ctx.analysisPokemon(p),p);
  assert.match(ctx.analysisMegaControl(p),/Aplicar mega/);
  ctx.analysisToggleMega(I.pokemonId(p),[p]);
  const preview=ctx.analysisPokemon(p);
  assert.deepEqual(Array.from(preview.types),['Fuego','Dragón']);
  assert.equal(preview.ability_id,181);assert.equal(preview.base_stats.ATK,130);
  assert.equal(preview.analysis_mega,true);assert.equal(preview.stats,null);assert.equal(preview.max_hp,null);
  assert.equal(p.form,0);assert.equal(p.stats.ATQ,120);assert.equal(p.types[1],'Volador');
  assert.match(ctx.analysisMegaControl(p),/Quitar mega/);
  ctx.analysisToggleMega(I.pokemonId(p),[p]);assert.equal(ctx.analysisPokemon(p),p);
}
function mega_selection_does_not_cross_game_or_stone(){
  ctx.analysisToggleMega(I.pokemonId(p),[p]);
  assert.equal(ctx.analysisPokemon({...p,item_id:661,mega_preview:{...p.mega_preview,item_id:661,form:2}}).analysis_mega,undefined);
  ctx.state={game:'Ultra Moon 1.0'};assert.equal(ctx.analysisPokemon(p),p);
  ctx.state={game:'Pokémon X 1.0'};assert.equal(ctx.analysisPokemon(p),p);
  assert.equal(ctx.analysisMegaControl({...p,mega_preview:null}),'');
}
for(const test of [mega_is_explicit_and_never_mutates_snapshot,mega_selection_does_not_cross_game_or_stone]){test();console.log(test.name+': OK')}
