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
 'hp_mid','upload','save','reset','hp_fill_upload','hp_frame_upload',
 'hp_custom_fill','hp_custom_frame','share-ip','share-enable','share-disable',
 'link-target','share-status'])
 assert.match(editor,new RegExp('id="'+id+'"'),id);
assert.match(edit,/navigator\.clipboard\.writeText/);
assert.match(edit,/\/api\/overlay\/font/);
assert.match(edit,/\/api\/overlay\/settings/);
assert.match(edit,/setTimeout\(save,350\)/);
assert.match(edit,/new Option/);
assert.doesNotMatch(editor,/id="preview"|Vista previa en tiempo real/);
assert.match(edit,/\/api\/overlay\/hp-image/);
assert.match(edit,/\/api\/overlay\/share/);
assert.match(client,/hp_custom_fill/);
assert.match(client,/hp_custom_frame/);
assert.match(css,/\.hp-fill\.custom-fill/);
assert.match(css,/\.hp-outline\.custom-frame::after/);
const editorCss=read('overlay-editor.css'),appCss=read('style.css');
for(const token of ['--page:#101010','--surface:#191919','--text:#f5f5f5',
  '--muted:#aaa','--accent:#f05b65','--border:#ffffff20',
  '--page:#fff','--accent:#be1d28']){
  assert.ok(editorCss.includes(token), 'Paleta OBS: '+token);
  assert.ok(appCss.includes(token), 'Paleta principal: '+token);
}
assert.match(editorCss,/\[data-theme="light"\]/);
assert.match(editorCss,/\[data-theme="dark"\]/);
assert.doesNotMatch(editorCss,/#101318|#1a1f29|#111721|#303949/i);
assert.match(editor,/progressive-theme/);
assert.match(editor,/addEventListener\('storage'/);
assert.match(edit,/status\.dataset\.error=String\(problem\)/);
console.log('OBS overlay: capas separadas, personalización y sintaxis JavaScript OK');
