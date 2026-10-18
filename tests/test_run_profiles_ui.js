'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../web/app.js'),'utf8');
const end=source.indexOf('// End named run controls.');
assert.ok(end>0);
class Node{
  constructor(){this.value='';this.dataset={};this.hidden=true;this.disabled=false;this.textContent='';this.children=[];this.open=false;}
  replaceChildren(...items){this.children=items;}
  showModal(){this.open=true;}
  close(){this.open=false;}
  focus(){this.focused=true;}
}
function harness(){
  const nodes={},requests=[];let reloaded=0;
  const $=id=>nodes[id]??=new Node();
  const replies=[];
  const context={$,token:'local-secret',Option:function(name,id){this.text=name;this.value=id;},
    window:{location:{reload:()=>reloaded++}},
    fetch:async(url,options)=>{
      requests.push({url,options});
      if(!replies.length)throw Error('Missing test response');
      const reply=replies.shift();return {ok:reply.ok!==false,json:async()=>reply.data};
    }};
  vm.createContext(context);vm.runInContext(source.slice(0,end),context);
  return {context,$,requests,replies,reloaded:()=>reloaded};
}
const status={active:'principal',profiles:[{id:'principal',name:'Principal'},{id:'run-123',name:'<script>literal</script>'}]};
async function test_picker_population_and_explicit_switch(){
  const h=harness();h.replies.push({data:status});await h.context.loadRunProfiles();
  assert.equal(h.$('run-profile-controls').hidden,false);
  assert.equal(h.$('run-profile').value,'principal');
  assert.equal(h.$('run-profile').children[1].text,'<script>literal</script>');
  h.replies.push({data:{...status,active:'run-123'}});
  await h.context.selectRunProfile('run-123');
  assert.equal(h.requests[1].url,'/api/profiles');
  assert.equal(h.requests[1].options.headers['X-Tracker-Token'],'local-secret');
  assert.deepEqual(JSON.parse(h.requests[1].options.body),{action:'select',id:'run-123'});
  assert.equal(h.reloaded(),1);
}
async function test_failed_switch_restores_picker_and_shows_error(){
  const h=harness();h.replies.push({data:status});await h.context.loadRunProfiles();
  h.$('run-profile').value='run-123';
  h.replies.push({ok:false,data:{error:'Esta partida ya está abierta en otra ventana.'}});
  await assert.rejects(h.context.selectRunProfile('run-123'),/otra ventana/);
  assert.equal(h.$('run-profile').value,'principal');
  assert.equal(h.$('run-profile').disabled,false);
  assert.equal(h.$('new-run-profile').disabled,false);
  assert.match(h.$('status').textContent,/otra ventana/);
  assert.equal(h.reloaded(),0);
}
async function test_create_run_then_selects_returned_id_and_reloads(){
  const h=harness();h.replies.push({data:status});await h.context.loadRunProfiles();
  h.$('new-run-profile').onclick();
  assert.equal(h.$('run-profile-dialog').open,true);
  assert.equal(h.$('run-profile-name').focused,true);
  h.$('run-profile-name').value='  Ultra Luna  ';
  h.replies.push({data:{...status,created:'run-new'}},{data:status},{data:{active:'run-new'}});
  await h.$('run-profile-form').onsubmit({preventDefault(){}});
  assert.deepEqual(JSON.parse(h.requests[1].options.body),{action:'create',name:'Ultra Luna'});
  assert.deepEqual(JSON.parse(h.requests[3].options.body),{action:'select',id:'run-new'});
  assert.equal(h.reloaded(),1);
  assert.equal(h.$('run-profile-create').disabled,false);
}
async function test_empty_name_and_creation_error_keep_dialog_usable(){
  const h=harness();h.replies.push({data:status});await h.context.loadRunProfiles();
  h.$('new-run-profile').onclick();h.$('run-profile-name').value=' ';
  await h.$('run-profile-form').onsubmit({preventDefault(){}});
  assert.match(h.$('run-profile-feedback').textContent,/Escribe un nombre/);
  assert.equal(h.requests.length,1);
  h.$('run-profile-name').value='Duplicada';
  h.replies.push({ok:false,data:{error:'Ya existe una partida con ese nombre.'}});
  await h.$('run-profile-form').onsubmit({preventDefault(){}});
  assert.match(h.$('run-profile-feedback').textContent,/Ya existe/);
  assert.equal(h.$('run-profile-dialog').open,true);
  assert.equal(h.$('run-profile-create').disabled,false);
  assert.equal(h.$('run-profile-close').disabled,false);
  assert.equal(h.reloaded(),0);
}
async function test_unavailable_profile_api_does_not_break_startup(){
  const h=harness();h.replies.push({ok:false,data:{}});
  await h.context.loadRunProfiles();assert.equal(h.$('run-profile-controls').hidden,true);
}
async function test_delete_inactive_profile_with_single_click(){
  const h=harness();h.replies.push({data:status});await h.context.loadRunProfiles();
  h.$('delete-run-profile').onclick();
  assert.equal(h.$('delete-run-profile-dialog').open,true);
  assert.equal(h.$('delete-run-profile-select').children[0].disabled,true);
  assert.equal(h.$('delete-run-profile-confirm').disabled,false);
  await h.context.deleteRunProfile('principal',status);
  await h.context.deleteRunProfile('run-123',{...status,active:'run-123'});
  assert.equal(h.requests.length,1);
  h.replies.push({data:{active:'principal',profiles:[status.profiles[0]]}});
  await h.$('delete-run-profile-confirm').onclick();
  assert.deepEqual(JSON.parse(h.requests[1].options.body),{action:'delete',id:'run-123'});
  assert.equal(h.$('run-profile').value,'principal');
  assert.equal(h.$('delete-run-profile-dialog').open,false);
  assert.equal(h.reloaded(),0);
}
async function test_delete_locked_error_retains_dialog_and_selection(){
  const h=harness();h.replies.push({data:status});await h.context.loadRunProfiles();
  h.$('delete-run-profile').onclick();
  h.replies.push({ok:false,data:{error:'La partida está abierta en otra ventana.'}});
  await h.context.deleteRunProfile('run-123',status);
  assert.match(h.$('delete-run-profile-feedback').textContent,/otra ventana/);
  assert.equal(h.$('delete-run-profile-dialog').open,true);
  assert.equal(h.$('delete-run-profile-close').disabled,false);
  assert.equal(h.$('run-profile').value,'principal');
}
(async()=>{
  for(const test of [test_picker_population_and_explicit_switch,test_failed_switch_restores_picker_and_shows_error,
    test_create_run_then_selects_returned_id_and_reloads,test_empty_name_and_creation_error_keep_dialog_usable,
    test_unavailable_profile_api_does_not_break_startup,test_delete_inactive_profile_with_single_click,test_delete_locked_error_retains_dialog_and_selection]){
    await test();console.log(test.name+' OK');
  }
})().catch(error=>{console.error(error);process.exitCode=1;});
