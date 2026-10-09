'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs'), path=require('node:path'), vm=require('node:vm');
const read=f=>fs.readFileSync(path.join(__dirname,'../web',f),'utf8');
const markup=read('overlay.html'),editor=read('overlay-editor.html');
const client=read('overlay.js'),edit=read('overlay-editor.js'),css=read('overlay.css');
new vm.Script(client,{filename:'overlay.js'});
new vm.Script(edit,{filename:'overlay-editor.js'});
assert.match(markup,/id="overlay"/);
assert.match(css,/background:transparent/);
assert.match(client,/\/api\/overlay\/public/);
assert.match(client,/\/api\/overlay\/settings/);
assert.match(client,/\/overlay\/media\/pokemon_/);
assert.match(client,/layer==='all'/);
assert.match(client,/layer===.all.|layer === .all./);
assert.match(client,/args\.get\('slot'\)/);
assert.match(client,/\.textContent=p\.present\?p\.nickname/);
assert.match(client,/p\.percent/);
assert.match(client,/settings\.hp_reverse/);
assert.match(client,/settings\.hp_style/);
assert.match(client,/settings\.hp_glow/);
assert.match(client,/settings\.font_file/);
assert.match(client,/img\.dataset\.src!==src/);
assert.doesNotMatch(client,/\/api\/state/);
for(const id of ['links','slot','order','direction','gap','slot_width',
 'sprite_size','font','font_file','name_color','name_size','hp_height',
 'hp_style','hp_reverse','hp_glow','hp_label','hp_good','hp_low',
 'hp_mid','upload','save','reset','preview'])
 assert.match(editor,new RegExp('id="'+id+'"'),id);
assert.match(edit,/navigator\.clipboard\.writeText/);
assert.match(edit,/\/api\/overlay\/font/);
assert.match(edit,/\/api\/overlay\/settings/);
assert.match(edit,/setTimeout\(save,350\)/);
assert.match(edit,/new Option/);
console.log('OBS overlay: capas separadas, personalización y sintaxis JavaScript OK');
