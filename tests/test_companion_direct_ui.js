'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../web/companion.js'), 'utf8');
const html = fs.readFileSync(path.join(__dirname, '../web/index.html'), 'utf8');
for (const id of ['companion-transport','companion-direct-fields','companion-host','companion-port','companion-direct-host'])
  assert.ok(html.includes(`id="${id}"`), `Direct setup includes ${id}`);
const elements = {};
const get = id => elements[id] ??= {
  value:'',hidden:false,disabled:false,textContent:'',
  showModal(){},close(){},closest(){return this.wrapper ??= {hidden:false}},
};
get('companion-transport').value = 'direct';
get('companion-host').value = '26.10.20.30';
get('companion-port').value = '8770';
get('companion-name').value = 'Sol';
get('companion-game').value = 'Ultra Sun 1.0';
const calls = [];
let info = {configured:false,transport:'cloud',partner:null};
const context = {
  document:{getElementById:get,querySelectorAll:()=>[]},
  localStorage:{getItem:()=>null,setItem(){}},
  window:{setCompanionView(){}},navigator:{clipboard:{writeText:async()=>{}}},
  localState:{party:[],boxes:{},progress:{deaths:{}}},routeCatalog:[],token:'local-secret',
  setInterval(){},confirm:()=>true,
  fetch:async(url,options)=>{
    if(options?.method === 'POST') calls.push(JSON.parse(options.body));
    return {ok:true,json:async()=>info};
  },
};
const settle = () => new Promise(resolve=>setImmediate(resolve));
(async()=>{
  vm.createContext(context);vm.runInContext(source,context);await settle();
  assert.equal(get('companion-create').hidden,true);
  assert.equal(get('companion-setup-key').closest().hidden,true);
  assert.equal(get('companion-url').closest().hidden,true);
  assert.equal(get('companion-direct-fields').hidden,false);
  await get('companion-direct-host').onclick();await settle();
  assert.equal(calls[0].action,'direct_host');
  assert.equal(calls[0].host,'26.10.20.30');
  assert.equal(calls[0].port,8770);
  assert.equal(calls[0].name,'Sol');
  get('companion-invite').value = 'nuzlocke://26.10.20.30:8770/join#'+'A'.repeat(43);
  await get('companion-join').onclick();await settle();
  assert.equal(calls[1].action,'direct_join');
  assert.equal(calls[1].invite_code,get('companion-invite').value);
  get('companion-transport').value='cloud';get('companion-transport').onchange();
  assert.equal(get('companion-create').hidden,false);
  assert.equal(get('companion-setup-key').closest().hidden,false);
  assert.equal(get('companion-url').closest().hidden,false);
  assert.equal(get('companion-direct-fields').hidden,true);
  await get('companion-join').onclick();await settle();
  assert.equal(calls[2].action,'join');
  console.log('Soul Link directo: host, invitación y alternativa Cloudflare OK');
})().catch(error=>{console.error(error);process.exitCode=1});
