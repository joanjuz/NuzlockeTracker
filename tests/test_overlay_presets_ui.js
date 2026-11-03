'use strict';
// Ejecuta overlay.js real: capas «Datos» y «Estadísticas», estilos de muerte
// (animación solo al morir), marco por posición y ?preset=<nombre>.
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const read=file=>fs.readFileSync(path.join(__dirname,'../web',file),'utf8');
const source=read('overlay.js'),css=read('overlay.css');

class Element {
  constructor(tag){
    this.tag=tag;this.children=[];this.dataset={};this.attributes={};this.className='';
    this.style={setProperty(){}};
    const self=this;
    this.classList={
      toggle(name,on){const set=new Set(self.className.split(' ').filter(Boolean));
        if(on===undefined?!set.has(name):on)set.add(name);else set.delete(name);
        self.className=[...set].join(' ');},
      contains(name){return self.className.split(' ').includes(name);},
    };
  }
  append(child){this.children.push(child);}
  addEventListener(type,fn){(this.listeners??={})[type]=fn;}
  replaceChildren(){this.children=[];}
  setAttribute(name,value){this.attributes[name]=value;}
  removeAttribute(name){delete this.attributes[name];}
  get firstElementChild(){return this.children[0]||null;}
  get lastElementChild(){return this.children[this.children.length-1]||null;}
}

function harness(query){
  const root=new Element('main'),timers=[],vars={};
  const context={location:{search:query},URLSearchParams,
    setTimeout(fn,ms){timers.push({fn,ms});},
    fetch:async()=>{throw new Error('sin red');},
    document:{getElementById:id=>id==='overlay'?root:null,createElement:tag=>new Element(tag),
      documentElement:{clientWidth:1280,style:{setProperty(key,value){vars[key]=value;}}}}};
  vm.createContext(context);
  vm.runInContext(source.replace(/\r?\n  poll\(\);\r?\n/,'\n  globalThis.overlayTest={appearance,draw,poll};\n'),context);
  const config={order:['sprites','names','hp'],direction:'row',font:'Arial',slot_width:142,
    hp_border_width:1,hp_label:'none',hp_low_threshold:25,hp_mid_threshold:50,counter_mode:'off',
    death_style:'gray',death_animation:'none',info_in_composition:false,info_size:14,
    info_show_level:true,info_show_types:true,info_show_shiny:true,info_show_gender:true,slot_frame:false,
    stats_show_captures:true,stats_show_deaths:true,stats_show_alive:true,stats_show_missed:true,
    stats_direction:'row',stats_size:20,death_image_version:'builtin',slot_frame_version:'0'};
  return {root,timers,vars,context,config,
    apply(changes={}){Object.assign(config,changes);context.overlayTest.appearance({...config});},
    draw(state){context.overlayTest.draw(state);}};
}
const mon=(n,extra={})=>({slot:n,present:true,species_id:6,nickname:'Brasa',item:'',hp:30,max_hp:60,percent:50,
  dead:false,stale:false,image_rev:'1',image_format:'png',level:36,types:['Fuego','Volador'],shiny:false,gender:0,...extra});
const party=(slots,extra={})=>{const all=[1,2,3,4,5,6].map(n=>({slot:n,present:false}));
  for(const s of slots)all[s.slot-1]=s;return {party:all,death_count:0,...extra};};
const layerOf=(h,name)=>h.root.children.find(el=>el.dataset.layer===name);
const info=(h,i=0)=>layerOf(h,'info').children[i].firstElementChild;
const spans=box=>box.children.map(el=>[el.className,el.textContent]);

function info_layer_shows_level_types_shiny_and_gender(){
  const h=harness('?layer=info');h.apply();
  h.draw(party([mon(1,{shiny:true}),mon(2,{level:5,types:['Eléctrico'],gender:1}),mon(3,{gender:2,types:[]})]));
  assert.deepEqual(spans(info(h,0)),[['info-level','Nv. 36'],['info-type type-fuego','Fuego'],
    ['info-type type-volador','Volador'],['info-shiny','★'],['info-gender male','♂']]);
  assert.equal(info(h,0).children[3].attributes['aria-label'],'Variocolor');
  assert.deepEqual(spans(info(h,1)),[['info-level','Nv. 5'],['info-type type-electrico','Eléctrico'],
    ['info-gender female','♀']]);
  assert.deepEqual(spans(info(h,2)),[['info-level','Nv. 36']],'sin género: no se muestra símbolo');
  assert.equal(info(h,3).children.length,0,'hueco vacío sin datos');
}
function info_options_hide_parts_and_level_null_is_skipped(){
  const h=harness('?layer=info');
  h.apply({info_show_types:false,info_show_gender:false});
  h.draw(party([mon(1,{shiny:true,level:null})]));
  assert.deepEqual(spans(info(h,0)),[['info-shiny','★']]);
  h.apply({info_show_types:true,info_show_shiny:false});
  h.draw(party([mon(1,{shiny:true,level:null})]));
  assert.deepEqual(spans(info(h,0)),[['info-type type-fuego','Fuego'],['info-type type-volador','Volador']]);
}
function info_text_is_never_html_and_unknown_types_are_neutral(){
  const h=harness('?layer=info&slot=4');h.apply();
  h.draw(party([mon(4,{types:['<img src=x onerror=alert(1)>','Fuego','Agua']})]));
  const group=layerOf(h,'info');
  assert.equal(group.children.length,1,'fuente de un solo Pokémon');
  const badges=info(h,0).children.filter(el=>el.className.startsWith('info-type'));
  assert.equal(badges.length,2,'como máximo dos tipos');
  assert.equal(badges[0].className,'info-type type-desconocido');
  assert.equal(badges[0].textContent,'<img src=x onerror=alert(1)>');
  assert.equal(badges[0].innerHTML,undefined);
}
function info_is_not_rebuilt_when_nothing_changes(){
  const h=harness('?layer=info');h.apply();
  h.draw(party([mon(1)]));
  const first=info(h,0).children[0];
  h.draw(party([mon(1,{hp:10,percent:17})]));
  assert.equal(info(h,0).children[0],first,'mismo nodo: sin parpadeo');
  h.draw(party([mon(1,{level:37})]));
  assert.equal(info(h,0).children[0].textContent,'Nv. 37');
}
function composition_places_info_after_names_and_items(){
  const h=harness('?layer=all');h.apply();
  assert.deepEqual(h.root.children.map(el=>el.dataset.layer),['sprites','names','hp']);
  h.apply({info_in_composition:true});
  assert.deepEqual(h.root.children.map(el=>el.dataset.layer),['sprites','names','info','hp']);
  h.apply({items_in_composition:true});
  assert.deepEqual(h.root.children.map(el=>el.dataset.layer),['sprites','names','items','info','hp']);
  h.apply({order:['hp','names','sprites']});
  assert.deepEqual(h.root.children.map(el=>el.dataset.layer),['hp','names','items','info','sprites']);
  assert.ok(!h.root.children.some(el=>el.dataset.layer==='stats'),'estadísticas solo como fuente aparte');
}
const statTexts=group=>group.children.map(item=>item.children.map(el=>el.textContent).join(' '));
function stats_layer_row_column_and_options(){
  const h=harness('?layer=stats&slot=2');h.apply();
  const stats={captures:14,deaths:3,alive:9,missed:2};
  h.draw(party([],{stats}));
  const group=layerOf(h,'stats');
  assert.equal(group.className,'overlay-stats');
  assert.equal(group.dataset.direction,'row');
  assert.deepEqual(statTexts(group),['Capturas 14','Muertes 3','Vivos 9','Rutas perdidas 2']);
  h.apply({stats_show_deaths:false,stats_direction:'column'});
  h.draw(party([],{stats}));
  assert.equal(group.dataset.direction,'column');
  assert.deepEqual(statTexts(group),['Capturas 14','Vivos 9','Rutas perdidas 2']);
  h.apply({stats_show_captures:false,stats_show_alive:false,stats_show_missed:false});
  h.draw(party([],{stats}));
  assert.equal(group.hidden,true);
  assert.equal(group.children.length,0);
}
function stats_bad_values_become_zero_and_size_variable(){
  const h=harness('?layer=stats');h.apply({stats_size:32,info_size:18});
  h.draw(party([],{stats:{captures:-1,deaths:'7',alive:2.5}}));
  assert.deepEqual(statTexts(layerOf(h,'stats')),['Capturas 0','Muertes 0','Vivos 0','Rutas perdidas 0']);
  h.draw(party([]));
  assert.equal(h.vars['--stats-size'],'32px');
  assert.equal(h.vars['--info-size'],'18px');
  assert.match(css,/\.overlay-stats\{[^}]*font-size:var\(--stats-size/);
  assert.match(css,/\.overlay-stats\[data-direction=column\]\{flex-direction:column/);
}
const sprite=(h,i=0)=>layerOf(h,'sprites').children[i];
function death_styles_gray_hide_and_tombstone(){
  const h=harness('?layer=sprites');h.apply();
  assert.equal(h.root.dataset.death,'gray');
  h.draw(party([mon(1,{dead:true,hp:0,percent:0}),mon(2)]));
  assert.equal(sprite(h).classList.contains('dead'),true);
  assert.equal(sprite(h).lastElementChild.src,undefined,'la lápida no se pide si no se usa');
  h.apply({death_style:'hide'});
  assert.equal(h.root.dataset.death,'hide');
  h.apply({death_style:'tombstone',death_image_version:'123'});
  h.draw(party([mon(1,{dead:true,hp:0,percent:0}),mon(2)]));
  const tomb=sprite(h).lastElementChild;
  assert.equal(tomb.className,'overlay-death');
  assert.equal(tomb.src,'/overlay/death-image?v=123');
  assert.equal(tomb.alt,'');
  assert.equal(sprite(h,1).lastElementChild.src,undefined,'vivo: sin lápida');
  // Revivir devuelve el sprite (la clase «dead» desaparece).
  h.draw(party([mon(1),mon(2)]));
  assert.equal(sprite(h).classList.contains('dead'),false);
  h.apply({death_style:'otro'});
  assert.equal(h.root.dataset.death,'gray','valor desconocido: gris');
  assert.match(css,/#overlay\[data-death=hide\] \.overlay-slot\.dead \.overlay-image/);
  assert.match(css,/#overlay\[data-death=tombstone\] \.overlay-slot\.dead \.overlay-death\{display:block\}/);
}
function death_animation_only_on_alive_to_dead_transition(){
  const h=harness('?layer=sprites');h.apply({death_animation:'fade'});
  // Primera carga con el Pokémon ya debilitado: sin animación.
  h.draw(party([mon(1,{dead:true}),mon(2)]));
  assert.equal(sprite(h).classList.contains('dying-fade'),false);
  h.draw(party([mon(1,{dead:true}),mon(2)]));
  assert.equal(sprite(h).classList.contains('dying-fade'),false,'seguir muerto no anima');
  // Muere durante la partida: una sola vez.
  h.draw(party([mon(1,{dead:true}),mon(2,{dead:true})]));
  assert.equal(sprite(h,1).classList.contains('dying-fade'),true);
  assert.equal(h.timers.length,1);
  assert.ok(h.timers[0].ms>=1000);
  h.draw(party([mon(1,{dead:true}),mon(2,{dead:true})]));
  assert.equal(h.timers.length,1,'no se vuelve a programar');
  h.timers.shift().fn();
  assert.equal(sprite(h,1).classList.contains('dying-fade'),false,'la clase se retira al terminar');
  assert.equal(sprite(h,1).classList.contains('dead'),true);
  // Revivir y volver a caer con sacudida.
  h.apply({death_animation:'shake'});
  h.draw(party([mon(1,{dead:true}),mon(2)]));
  h.draw(party([mon(1,{dead:true}),mon(2,{dead:true})]));
  assert.equal(sprite(h,1).classList.contains('dying-shake'),true);
  assert.match(css,/\.overlay-slot\.dying-shake\{animation:death-shake/);
  assert.match(css,/\.overlay-slot\.dying-fade \.overlay-image\{animation:death-gray/);
}
function no_animation_when_other_pokemon_or_disabled_or_rebuilt(){
  const h=harness('?layer=sprites');h.apply({death_animation:'fade'});
  h.draw(party([mon(1)]));
  // Otro Pokémon ocupa el hueco ya debilitado (cambio de equipo): no es una muerte.
  h.draw(party([mon(1,{species_id:25,nickname:'Chispa',dead:true})]));
  assert.equal(sprite(h).classList.contains('dying-fade'),false);
  h.apply({death_animation:'none'});
  h.draw(party([mon(1)]));h.draw(party([mon(1,{dead:true})]));
  assert.equal(sprite(h).classList.contains('dying-fade'),false);
  // Reconstrucción (cambio de distribución) con el Pokémon ya muerto: sin animación.
  h.apply({death_animation:'fade'});
  h.draw(party([mon(1)]));
  h.apply({direction:'column'});
  h.draw(party([mon(1,{dead:true})]));
  assert.equal(sprite(h).classList.contains('dying-fade'),false);
  assert.equal(h.timers.length,0);
}
function slot_frame_variable_follows_setting_and_version(){
  const h=harness('?layer=sprites');h.apply();
  assert.equal(h.vars['--slot-frame'],'none');
  h.apply({slot_frame:true,slot_frame_version:'17 a'});
  assert.equal(h.vars['--slot-frame'],'url("/overlay/slot-frame.png?v=17%20a")');
  assert.match(css,/background:var\(--slot-frame,none\) center\/contain no-repeat/);
}
function response(status,body){return {ok:status>=200&&status<300,status,json:async()=>body};}
async function preset_param_reads_preset_and_falls_back_on_404(){
  const h=harness('?layer=sprites&preset=Combate%20A');
  const urls=[];
  h.context.fetch=async url=>{
    urls.push(url);
    if(url==='/api/overlay/public')return response(200,party([mon(1)]));
    if(url.includes('preset='))return response(200,{...h.config,name_size:31});
    return response(200,{...h.config});
  };
  await h.context.overlayTest.poll();
  assert.deepEqual(urls,['/api/overlay/public?preset=Combate%20A','/api/overlay/settings?preset=Combate%20A']);
  assert.equal(h.vars['--name'],'31px');

  const missing=harness('?layer=sprites&preset=Borrado');
  const seen=[];
  missing.context.fetch=async url=>{
    seen.push(url);
    // Like the server: public state never 404s (unknown preset → current style).
    if(url.startsWith('/api/overlay/public'))return response(200,party([mon(1)]));
    if(url.includes('preset='))return response(404,{error:'Perfil de overlay desconocido'});
    return response(200,{...missing.config,name_size:22});
  };
  await missing.context.overlayTest.poll();
  assert.deepEqual(seen,['/api/overlay/public?preset=Borrado','/api/overlay/settings?preset=Borrado','/api/overlay/settings']);
  assert.equal(missing.vars['--name'],'22px','se usa la personalización actual');
  // Siguientes lecturas de ajustes: no insiste en cada sondeo.
  seen.length=0;
  for(let i=0;i<3;i++)await missing.timers.shift().fn();
  assert.ok(seen.filter(u=>u.includes('preset=')).length===0);
  assert.ok(seen.includes('/api/overlay/settings'));
}
async function no_preset_param_keeps_plain_settings_url(){
  const h=harness('?layer=all&preset=');
  const urls=[];
  h.context.fetch=async url=>{urls.push(url);
    return response(200,url.includes('settings')?{...h.config}:party([mon(1)]));};
  await h.context.overlayTest.poll();
  assert.deepEqual(urls,['/api/overlay/public','/api/overlay/settings']);
}

(async()=>{
  for(const test of [info_layer_shows_level_types_shiny_and_gender,info_options_hide_parts_and_level_null_is_skipped,
    info_text_is_never_html_and_unknown_types_are_neutral,info_is_not_rebuilt_when_nothing_changes,
    composition_places_info_after_names_and_items,stats_layer_row_column_and_options,
    stats_bad_values_become_zero_and_size_variable,death_styles_gray_hide_and_tombstone,
    death_animation_only_on_alive_to_dead_transition,no_animation_when_other_pokemon_or_disabled_or_rebuilt,
    slot_frame_variable_follows_setting_and_version,preset_param_reads_preset_and_falls_back_on_404,
    no_preset_param_keeps_plain_settings_url]){
    await test();console.log('PASS',test.name);
  }
})().catch(error=>{console.error(error);process.exit(1);});
