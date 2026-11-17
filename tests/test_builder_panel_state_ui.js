'use strict';
const assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const handlers={};
const panel={open:true,closest:selector=>selector==='#team-builder'?{}:null,contains:()=>false};
const menu={open:true,closest:()=>null,contains:()=>false};
const source=fs.readFileSync('web/app/shell.js','utf8');
vm.runInNewContext(source.slice(source.indexOf("document.addEventListener('pointerdown'")),{
  document:{addEventListener:(type,fn)=>handlers[type]=fn,querySelectorAll:()=>[panel,menu]}
});
handlers.pointerdown({target:{}});
assert.equal(panel.open,true,'An outside builder action keeps the available panel open');
assert.equal(menu.open,false,'Transient menus still dismiss outside');
menu.open=true;handlers.keydown({key:'Escape'});
assert.equal(panel.open,true,'Escape does not collapse persistent builder panels');
assert.equal(menu.open,false,'Escape still dismisses transient menus');
console.log('Builder persistent disclosure: 4 checks passed');
