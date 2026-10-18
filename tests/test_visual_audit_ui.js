"use strict";
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../web/app.js'),'utf8');
const status=source.slice(source.indexOf('function gen7ScanStatus('),source.indexOf('function render(next)'));
const c={};vm.createContext(c);vm.runInContext(status,c);
const base={boxes:{1:[]},box_verified:false,scan:{active:false}};
for(const [state,pattern] of [['pending',/Verificando/],['pending_empty',/PC vacío.*deposita un Pokémon/],['ambiguous',/varias ubicaciones/],['invalid',/No se pudieron validar/]]){
 const text=c.gen7ScanStatus({...base,box_status:state});assert.match(text,pattern);assert.match(text,/Cajas guardadas: no verificadas/);
}
assert.doesNotMatch(c.gen7ScanStatus({...base,box_verified:true,box_status:'verified'}),/no verificadas|sin validar/);
assert.match(c.gen7ScanStatus({...base,scan:{active:true,completed:15}}),/Lectura global: 15 \/ 32/);
console.log('Gen7: estados de validación y cajas guardadas identificados OK');
const nodes={};const $=id=>nodes[id]??={hidden:true,disabled:false};const scripts=[];
const loader={window:{},$,document:{createElement:()=>({}),body:{append:s=>scripts.push(s)}}};
vm.createContext(loader);vm.runInContext(source.slice(source.indexOf('// Optional Companion dependency')),loader);
loader.window.companionScriptFailed();assert.equal($('companion-load-error').hidden,false);
$('companion-load-retry').onclick();$('companion-load-retry').onclick();assert.equal(scripts.length,1);
assert.equal($('companion-load-retry').disabled,true);scripts[0].onerror();
assert.equal($('companion-load-retry').disabled,false);$('companion-load-retry').onclick();assert.equal(scripts.length,2);
scripts[1].onload();assert.equal($('companion-load-error').hidden,true);
console.log('Companion: error visible, reintento exclusivo y recuperación OK');
