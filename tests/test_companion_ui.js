'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const code = fs.readFileSync(require('node:path').join(__dirname, '../web/companion.js'), 'utf8');
const app = fs.readFileSync(require('node:path').join(__dirname, '../web/app.js'), 'utf8');
assert.match(app, /if\(companionView\)throw Error\('La sesión del compañero es de solo lectura/);
assert.match(app, /function setCompanionView\(/);
const controls = {};
const get = id => controls[id] ??= { id, hidden: false, value:'', textContent:'', disabled:false,
  showModal(){this.open=true},close(){this.open=false} };
const events = [];
const own = {schema_version:1,game:'Ultra Moon 1.0',party:[null,null,null,null,null,null],boxes:{},progress:{deaths:{},missed_routes:[]}};
const status = {configured:true,invite_code:'',partner:{name:'Amigo',game:'Ultra Moon 1.0',updated_at:12345,state:own}};
const context={
  console, token:'local',
  document:{getElementById:get,querySelectorAll:()=>[]},
  window:{setCompanionView:(...args)=>events.push(args)},
  fetch:async()=>({ok:true,json:async()=>status}),
  setInterval:()=>1,
  confirm:()=>true,
  navigator:{clipboard:{writeText:async()=>{}}},
};
vm.createContext(context);
vm.runInContext(code,context);
setImmediate(()=>{
  try {
    assert.equal(get('companion-toggle').hidden,false);
    assert.match(code, /setInterval\(getStatus, 5000\)/);
    assert.match(code, /invite_link \|\| info\.invite_code/);
    assert.equal(get('companion-toggle').textContent,'Compañero');
    get('companion-toggle').onclick();
    assert.equal(events.length,1);
    assert.equal(events[0][0],true);
    assert.equal(events[0][1].game,'Ultra Moon 1.0');
    get('companion-toggle').onclick();
    assert.equal(events[1][0],false);
    assert.equal(get('companion-toggle').textContent,'Compañero');
    console.log('Compañero: vista remota y retorno a mi partida OK');
  } catch(error) {console.error(error);process.exitCode=1}
});
