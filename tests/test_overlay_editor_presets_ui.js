'use strict';
// Ejecuta overlay-editor.js real con un DOM simulado: perfiles de estilo,
// enlaces fijados a un perfil, nuevas fuentes, vista previa y copia de seguridad.
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const read=file=>fs.readFileSync(path.join(__dirname,'../web',file),'utf8');
const source=read('overlay-editor.js'),markup=read('overlay-editor.html'),editorCss=read('overlay-editor.css');

class FakeElement {
  constructor(tag,id=''){
    this.tag=tag;this.id=id;this.children=[];this.options=[];this.dataset={};this.attributes={};
    this.style={};this.value='';this.checked=false;this.disabled=false;this.textContent='';
    this.type=tag==='input'?'text':'';this.clientWidth=600;
  }
  append(...items){this.children.push(...items);}
  add(option){this.options.push(option);if(this.options.length===1)this.value=option.value;}
  replaceChildren(...items){this.children=items;this.options=[];}
  remove(){}
  click(){this.onclick?.();}
  focus(){}
  setAttribute(name,value){this.attributes[name]=String(value);}
  getAttribute(name){return this.attributes[name]??null;}
  removeAttribute(name){delete this.attributes[name];}
  addEventListener(type,fn){(this.listeners??={})[type]=fn;}
  closest(){return null;}
  matches(){return false;}
  insertAdjacentElement(){}
  getContext(){return {font:'',measureText:text=>({width:String(text).length*8})};}
}
// Ids that the editor reads: taken from the real markup, so a renamed id fails here.
const ids=[...markup.matchAll(/id="([^"]+)"/g)].map(m=>m[1]);
const checkboxes=new Set([...markup.matchAll(/<input id="([^"]+)" type="checkbox"/g)].map(m=>m[1]));

function harness({fetchImpl,parentApi}={}){
  const elements=new Map();
  for(const id of ids){
    const tag=/<select\s$/.test(markup.split('id="'+id+'"')[0])?'select':'input';
    const el=new FakeElement(tag,id);
    if(checkboxes.has(id))el.type='checkbox';
    const first=markup.split('id="'+id+'"')[1].match(/^[^>]*>\s*<option(?: value="([^"]*)")?>([^<]*)/);
    if(tag==='select'&&first)el.value=first[1]??first[2];
    elements.set(id,el);
  }
  elements.get('link-target').value='local';
  const posts=[],timers=[];
  const body=new FakeElement('body');
  const window={addEventListener(){},parent:null};
  window.parent=parentApi?{pywebview:{api:parentApi}}:window;
  const context={window,location:{origin:'http://127.0.0.1:8765'},
    document:{getElementById:id=>elements.get(id)||null,createElement:tag=>new FakeElement(tag),
      querySelector:()=>null,querySelectorAll:()=>[],body},
    navigator:{clipboard:{writeText:async()=>{}}},localStorage:{getItem:()=>null,setItem(){}},
    Option:class{constructor(text,value){this.text=text;this.value=value;}},
    setTimeout(fn,ms){timers.push({fn,ms});return timers.length;},clearTimeout(){},
    requestAnimationFrame(fn){fn();},URL,Blob,btoa,
    fetch:async(url,options={})=>{
      if(options.method==='POST')posts.push({url,body:JSON.parse(options.body)});
      return fetchImpl?fetchImpl(url,options):{ok:false,json:async()=>({})};
    }};
  vm.createContext(context);
  vm.runInContext(source,context);
  const $=id=>elements.get(id);
  const links=()=>Object.fromEntries($('links').children.map(row=>[row.children[0].textContent,row.children[1].value]));
  return {$,posts,timers,links,context};
}
const flush=()=>new Promise(resolve=>setImmediate(resolve));
const ok=body=>({ok:true,status:200,json:async()=>body,text:async()=>JSON.stringify(body)});

function new_sources_and_dimensions_are_listed(){
  const h=harness();
  const links=h.links();
  assert.equal(links['Datos'],'http://127.0.0.1:8765/overlay?layer=info');
  assert.equal(links['Estadísticas'],'http://127.0.0.1:8765/overlay?layer=stats');
  h.$('slot').value='3';h.$('slot').onchange();
  assert.equal(h.links()['Datos'],'http://127.0.0.1:8765/overlay?layer=info&slot=3');
  assert.equal(h.links()['Estadísticas'],'http://127.0.0.1:8765/overlay?layer=stats','sin hueco');
  assert.equal(h.links()['Cementerio'],'http://127.0.0.1:8765/overlay?layer=graveyard');
  const sizes=$=>$('links').children.map(row=>row.children[3].dataset.sourceSize);
  assert.deepEqual(sizes(h.$),['all','sprites','names','hp','items','info','counter','graveyard','stats']);
}
function pinned_links_carry_the_preset_name(){
  const h=harness();
  h.$('preset-list').replaceChildren();
  h.$('preset-list').add({text:'Combate á',value:'Combate á'});
  h.$('preset-list').value='Combate á';
  h.$('preset-list').onchange();
  assert.equal(h.$('preset-pin').disabled,false);
  h.$('preset-pin').checked=true;h.$('preset-pin').onchange();
  assert.equal(h.links()['Vida'],'http://127.0.0.1:8765/overlay?layer=hp&preset=Combate%20%C3%A1');
  assert.equal(h.links()['Estadísticas'],'http://127.0.0.1:8765/overlay?layer=stats&preset=Combate%20%C3%A1');
  // La vista previa enseña la personalización en edición, no el perfil fijado.
  assert.ok(!String(h.$('preview-frame').src).includes('preset='));
  h.$('preset-pin').checked=false;h.$('preset-pin').onchange();
  assert.equal(h.links()['Vida'],'http://127.0.0.1:8765/overlay?layer=hp');
}
function preview_follows_layer_and_slot(){
  const h=harness();
  assert.equal(h.$('preview-frame').src,undefined,'sin ajustes cargados no se abre la vista previa');
  h.$('preview-layer').onchange();
  assert.equal(h.$('preview-frame').src,'/overlay?layer=all');
  h.$('preview-layer').value='info';h.$('slot').value='2';h.$('preview-layer').onchange();
  assert.equal(h.$('preview-frame').src,'/overlay?layer=info&slot=2');
  h.$('preview-layer').value='stats';h.$('preview-layer').onchange();
  assert.equal(h.$('preview-frame').src,'/overlay?layer=stats');
  assert.match(h.$('preview-frame').style.width,/^\d+px$/);
}
async function presets_save_apply_and_delete(){
  let presets=[];
  const settings={name_size:28,info_size:16,stats_direction:'column',order:['sprites','names','hp'],sprite_set:''};
  const h=harness({fetchImpl:async(url,options)=>{
    if(url==='/api/overlay/presets'&&options.method==='POST'){
      const {action,name}=JSON.parse(options.body);
      if(action==='save')presets=[...presets,{name}];
      if(action==='delete')presets=presets.filter(p=>p.name!==name);
      return ok({presets,settings});
    }
    if(url==='/api/overlay/sprite-sets')return ok({sets:[]});
    return {ok:false,json:async()=>({})};
  }});
  // Nombre inválido: no se envía nada.
  h.$('preset-name').value='<b>mal</b>';
  await h.$('preset-save').onclick();
  assert.equal(h.posts.length,0);
  assert.equal(h.$('preset-name').attributes['aria-invalid'],'true');
  h.$('preset-name').value='  Exploración ';
  await h.$('preset-save').onclick();
  assert.deepEqual(h.posts.at(-1),{url:'/api/overlay/presets',body:{action:'save',name:'Exploración'}});
  assert.equal(h.$('preset-list').value,'Exploración');
  assert.equal(h.$('preset-name').value,'');
  assert.match(h.$('preset-status').textContent,/Exploración/);
  await h.$('preset-apply').onclick();
  assert.deepEqual(h.posts.at(-1).body,{action:'apply',name:'Exploración'});
  assert.equal(h.$('name_size').value,28,'el editor muestra los ajustes aplicados');
  assert.equal(h.$('stats_direction').value,'column');
  // Eliminar pide confirmación con un segundo clic.
  const before=h.posts.length;
  await h.$('preset-delete').onclick();
  assert.equal(h.posts.length,before);
  assert.equal(h.$('preset-delete').textContent,'Confirmar eliminación');
  await h.$('preset-delete').onclick();
  assert.deepEqual(h.posts.at(-1).body,{action:'delete',name:'Exploración'});
  assert.equal(h.$('preset-list').value,'');
  assert.equal(h.$('preset-apply').disabled,true);
  assert.equal(h.$('preset-pin').checked,false);
}
async function export_prefers_native_dialog_of_the_parent_window(){
  const calls=[];
  const h=harness({parentApi:{save_export:async kind=>{calls.push(kind);return {saved:true,name:'obs.json'};}}});
  await h.$('overlay-export').onclick();
  assert.deepEqual(calls,['obs']);
  assert.match(h.$('backup-status').textContent,/obs\.json/);
  assert.equal(h.$('overlay-export').disabled,false);
}
async function import_posts_bundle_and_refreshes_editor(){
  const bundle={format:'progressive-tracker-obs',schema:1,settings:{}};
  const h=harness({fetchImpl:async url=>{
    if(url==='/api/overlay/import')return ok({settings:{name_size:40,order:['hp','names','sprites']},presets:[{name:'Importado'}]});
    if(url==='/api/overlay/fonts')return ok(['Pixel.ttf']);
    if(url==='/api/overlay/sprite-sets')return ok({sets:[]});
    return {ok:false,json:async()=>({})};
  }});
  h.$('overlay-import').files=[{name:'ajustes.json',size:100,text:async()=>JSON.stringify(bundle)}];
  await h.$('overlay-import').onchange();
  assert.deepEqual(h.posts.at(-1),{url:'/api/overlay/import',body:{bundle}});
  assert.equal(h.$('name_size').value,40);
  assert.equal(h.$('order').value,'hp,names,sprites');
  assert.equal(h.$('preset-list').value,'Importado');
  assert.match(h.$('backup-status').textContent,/ajustes\.json/);
  // JSON dañado: error en la sección, sin petición.
  const count=h.posts.length;
  h.$('overlay-import').files=[{name:'roto.json',size:5,text:async()=>'{no'}];
  await h.$('overlay-import').onchange();
  assert.equal(h.posts.length,count);
  assert.equal(h.$('backup-status').dataset.error,'true');
}
async function slot_frame_upload_uses_kind_slot(){
  const h=harness({fetchImpl:async url=>url==='/api/overlay/hp-image'?ok({width:96,height:96}):ok({})});
  const bytes=new Uint8Array([137,80,78,71]);
  h.$('slot_frame_upload').files=[{name:'marco.png',size:4,arrayBuffer:async()=>bytes.buffer}];
  await h.$('slot_frame_upload').onchange();
  await flush();
  assert.equal(h.posts[0].url,'/api/overlay/hp-image');
  assert.equal(h.posts[0].body.kind,'slot');
  assert.equal(h.$('slot_frame').checked,true);
}
function markup_controls_and_csp(){
  for(const id of ['death_style','death_animation','slot_frame','slot_frame_upload','info_in_composition','info_size',
    'info_show_level','info_show_types','info_show_shiny','info_show_gender','stats_show_captures','stats_show_deaths',
    'stats_show_alive','stats_show_missed','stats_direction','stats_size','preset-list','preset-name','preset-save',
    'preset-apply','preset-delete','preset-pin','overlay-export','overlay-import','preview-layer','preview-frame'])
    assert.ok(ids.includes(id),id);
  for(const value of ['gray','tombstone','hide'])assert.match(markup,new RegExp('<option value="'+value+'">'));
  for(const value of ['none','fade','shake'])assert.match(markup,new RegExp('<option value="'+value+'">'));
  assert.match(markup,/Guardar como…/);
  assert.match(markup,/Fijar enlaces a este perfil/);
  // Preset controls must not autosave as overlay settings.
  const presetBlock=markup.slice(markup.indexOf('id="presets-heading"'),markup.indexOf('</section>',markup.indexOf('id="presets-heading"')));
  assert.doesNotMatch(presetBlock,/class="controls/);
  // CSP: no inline scripts or on…= handlers, only same-origin script files.
  assert.doesNotMatch(markup,/\son[a-z]+=/i);
  assert.doesNotMatch(markup,/<script(?![^>]*\ssrc=)/);
  assert.match(editorCss,/\.preview-stage\{[^}]*background-color:var\(--checker-bg\)/);
  assert.match(source,/save_export\('obs'\)/);
  assert.doesNotMatch(source,/innerHTML/);
}

(async()=>{
  for(const test of [new_sources_and_dimensions_are_listed,pinned_links_carry_the_preset_name,preview_follows_layer_and_slot,
    presets_save_apply_and_delete,export_prefers_native_dialog_of_the_parent_window,import_posts_bundle_and_refreshes_editor,
    slot_frame_upload_uses_kind_slot,markup_controls_and_csp]){
    await test();console.log('PASS',test.name);
  }
})().catch(error=>{console.error(error);process.exit(1);});
