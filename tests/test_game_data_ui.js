'use strict';
const assert=require('node:assert/strict');
const vm=require('node:vm');
const {read,slice,loadShared}=require('./ui_shared.js');
const html=read('index.html');
for(const id of ['game-data-file','preview-game-data','apply-game-data','cancel-game-data','remove-game-data','game-data-preview','game-data-ack','game-data-status'])
  assert.match(html,new RegExp('id="'+id+'"'));

async function run(){
  const elements={};
  const el=id=>elements[id]??=( {hidden:false,disabled:false,value:'',checked:false,textContent:'',files:[]} );
  el('game').value='Ultra Moon 1.0';
  el('game-data-file').files=[{size:10,text:async()=>'{"fixture":true}'}];
  const calls=[];let answer={};let status=200;
  const context=vm.createContext({$:el,companionView:false,token:'csrf',JSON,Error,
    fetch:async(url,options)=>{calls.push({url,options});return {ok:status===200,json:async()=>answer};}});
  vm.runInContext(slice('app/connection.js','// DGD is a two-step','if($(\'preview-game-data\'))'),context);
  const preview={previewToken:'one',game:'Ultra Moon 1.0',counts:{species:2,moves:1,evolutions:2},
    differences:[{record:'Pokémon 1',field:'HP',before:45,after:123}],requiresRevisionAcknowledgement:true,
    warning:'No se verifica la ROM.',replacesExisting:false};
  answer=preview;
  await context.previewGameData();
  assert.equal(calls.length,1);assert.equal(calls[0].url,'/api/game-data/preview');
  assert.equal(JSON.parse(calls[0].options.body).game,'Ultra Moon 1.0');
  assert.equal(el('game-data-preview').hidden,false);
  assert.match(el('game-data-differences').textContent,/Actual: 45\nImportado: 123/);
  assert.equal(el('game-data-ack-label').hidden,false);
  await context.applyGameData();
  assert.equal(calls.length,1,'Sin confirmación no se escribe');
  assert.match(el('game-data-status').textContent,/Confirma/);
  el('game-data-ack').checked=true;
  answer={loaded:true,active:true,game:'Ultra Moon 1.0',counts:{species:2,moves:1},revision:null,warning:'Identidad no comprobada'};
  await context.applyGameData();
  assert.equal(calls.at(-1).url,'/api/game-data/apply');
  assert.deepEqual(JSON.parse(calls.at(-1).options.body),{previewToken:'one',game:'Ultra Moon 1.0',acknowledgeUnknownRevision:true});
  assert.equal(el('game-data-preview').hidden,true);
  assert.equal(el('remove-game-data').hidden,false);
  assert.match(el('game-data-status').textContent,/DGD activo/);

  answer=preview;await context.previewGameData();context.cancelGameDataPreview();
  const beforeCancel=calls.length;await context.applyGameData();
  assert.equal(calls.length,beforeCancel,'Cancelar no importa');
  assert.equal(el('game-data-preview').hidden,true);

  answer=preview;await context.previewGameData();el('game').value='Ultra Sun 1.0';
  const beforeGameChange=calls.length;await context.applyGameData();
  assert.equal(calls.length,beforeGameChange,'Cambiar juego invalida la vista previa');
  assert.equal(el('game-data-preview').hidden,true);

  status=400;answer={error:'Esquema incompatible'};await context.previewGameData();
  assert.match(el('game-data-status').textContent,/Error: Esquema incompatible/);
  assert.equal(el('game-data-preview').hidden,true);

  el('game-data-file').files=[{size:5000001,text:async()=>{throw Error('No debe leerse');}}];
  const beforeLarge=calls.length;await context.previewGameData();
  assert.equal(calls.length,beforeLarge);assert.match(el('game-data-status').textContent,/5 MB/);

  context.renderGameDataStatus({loaded:false,active:false});
  assert.equal(el('remove-game-data').hidden,true);
  assert.match(el('game-data-status').textContent,/referencias y los CSV/);

  loadShared(context,['esc','list']);
  vm.runInContext(slice('app/detail.js','function detailBaseStats','function evolutionOption'),context);
  const card=context.detailBaseStats({base_stats:{HP:123},base_stats_source:'Definitive Game Data',species_abilities:[{name:'<unsafe>'}]});
  assert.match(card,/Estadísticas base · Definitive Game Data/);
  assert.match(card,/123/);assert.match(card,/&lt;unsafe&gt;/);assert.doesNotMatch(card,/<unsafe>/);
  console.log('DGD UI: preview values, confirm/ack, cancel, game change, errors, limits, removal fallback and escaped displayed stats passed');
}
run().catch(error=>{console.error(error);process.exitCode=1;});
