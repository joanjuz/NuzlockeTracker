'use strict';
/* Browser source reads six sanitized slots and a death total from the public API. */
(() => {
  const args = new URLSearchParams(location.search);
  const allowed = new Set(['all','sprites','names','hp','items','info','counter','graveyard','stats']);
  const layer = allowed.has(args.get('layer')) ? args.get('layer') : 'all';
  const slotArg = Number(args.get('slot'));
  const slot = Number.isInteger(slotArg) && slotArg >= 1 && slotArg <= 6 ? slotArg : null;
  // ?preset=<name>: read that saved style instead of the current one.
  const presetArg = (args.get('preset') || '').trim();
  const preset = presetArg.length >= 1 && presetArg.length <= 40 ? presetArg : '';
  const root = document.getElementById('overlay');
  let settings = null, lastConfig = '', nodes = {};
  const mk = (tag, cls, parent) => {
    const el = document.createElement(tag);
    if (cls) el.className = cls;
    if (parent) parent.append(el);
    return el;
  };
  const css = (key, value) => document.documentElement.style.setProperty(key,value);
  // Objects are optional in the composition: placed right after the nicknames
  // so the layer order saved before this option existed keeps working.
  // Info (level, types, shiny, gender) goes after the nicknames and objects.
  const compositionLayers = () => {
    const order = [...settings.order];
    if (settings.items_in_composition) order.splice(order.indexOf('names') + 1, 0, 'items');
    if (settings.info_in_composition) {
      const after = order.includes('items') ? order.indexOf('items') : order.indexOf('names');
      order.splice(after + 1, 0, 'info');
    }
    if (settings.counter_in_composition) order.push('counter');
    return order;
  };
  const visibleLayers = () => layer === 'all' ? compositionLayers() : [layer];
  function rebuild() {
    root.replaceChildren(); nodes = {};
    const types = visibleLayers();
    for (const type of types) {
      const group = mk('section','overlay-layer',root);
      group.dataset.layer = type;
      group.dataset.direction = settings.direction;
      if (type === 'counter') {
        group.className = 'overlay-counter';
        group.setAttribute('aria-live','polite');
        nodes.counter = group;
        continue;
      }
      if (type === 'graveyard') {
        group.className = 'overlay-graveyard';
        nodes.graveyard = group;
        continue;
      }
      if (type === 'stats') {
        group.className = 'overlay-stats';
        nodes.stats = group;
        continue;
      }
      for (const n of (slot ? [slot] : [1,2,3,4,5,6])) {
        const node = mk('div','overlay-slot',group);
        nodes[type+':'+n] = node;
        if (type === 'sprites') {
          const image = mk('img','overlay-image',node);
          image.alt = ''; image.draggable = false;
          // Shown instead of the sprite while dead when death_style is 'tombstone'.
          const tomb = mk('img','overlay-death',node);
          tomb.alt = ''; tomb.draggable = false;
        } else if (type === 'info') {
          mk('div','overlay-info',node);
        } else if (type === 'names') {
          mk('span','overlay-name',node);
        } else if (type === 'items') {
          const icon = mk('img','overlay-item-icon',node);
          icon.alt = ''; icon.draggable = false; icon.hidden = true;
          // Unknown or offline icon: hide it (the name is shown instead in icon mode).
          icon.addEventListener('error', () => {
            icon.hidden = true; icon.dataset.failed = icon.dataset.src || ''; icon.dataset.failedAt = String(Date.now());
          });
          mk('span','overlay-item',node);
        } else {
          const hp = mk('div','overlay-health',node);
          const track = mk('div','hp-outline',hp);
          const fill=mk('div','hp-fill',track);
          mk('div','hp-fill-art',fill);
          mk('span','hp-label',hp);
        }
      }
    }
  }
  function fitViewport() {
    // Viewport units are not divided by CSS zoom: wrap within the source's
    // actual visible width while preserving configured icon and font sizes.
    const scale=settings?.render_scale||1;
    css('--overlay-viewport',(document.documentElement.clientWidth/scale)+'px');
  }
  if(typeof window!=='undefined')window.addEventListener('resize',fitViewport);
  function appearance(value) {
    if (!value) return;
    const signature=JSON.stringify(value);
    if(signature===lastConfig)return;
    const structural = !settings || settings.direction !== value.direction ||
        JSON.stringify(settings.order)!==JSON.stringify(value.order) ||
        settings.counter_in_composition !== value.counter_in_composition ||
        settings.items_in_composition !== value.items_in_composition ||
        Boolean(settings.info_in_composition) !== Boolean(value.info_in_composition);
    settings=value;lastConfig=signature;
    // CSS zoom reflows/rasterizes fonts and vector HP tracks at real scaled
    // dimensions; transform:scale only enlarges previously rasterized pixels.
    root.style.zoom=String(settings.render_scale||1);
    fitViewport();
    css('--counter-icon',(settings.counter_icon_size||36)+'px');
    css('--sprite-render',settings.sprite_scaling==='smooth'?'auto':'pixelated');
    css('--sprite-padding',(settings.sprite_padding||0)+'px');
    // Empty (not 'none') when disabled: the dead rule composes
    // "grayscale(1) var(--sprite-shadow,)" and "grayscale(1) none" is invalid.
    css('--sprite-shadow',settings.sprite_shadow?'drop-shadow(0 4px 7px #000a)':'');
    css('--item-size',(settings.item_size||14)+'px');
    css('--item-icon',(settings.item_icon_size||32)+'px');
    css('--grave-cols',String(settings.graveyard_columns||6));
    css('--grave-sprite',(settings.graveyard_sprite_size||64)+'px');css('--item-color',settings.item_color||'#f2c15c');
    css('--hp-speed',(settings.hp_animation_ms??250)+'ms');
    css('--slot',settings.slot_width+'px');css('--gap',settings.gap+'px');
    css('--sprite',settings.sprite_size+'px');
    css('--name',settings.name_size+'px');css('--fg',settings.name_color);
    css('--outline',settings.name_outline);css('--weight',String(settings.name_weight));
    css('--hp-h',settings.hp_height+'px');css('--radius',settings.hp_radius+'px');
    css('--border',settings.hp_border_width+'px');css('--border-color',settings.hp_border);
    css('--track',settings.hp_background);css('--hp-text',settings.hp_text_color);
    css('--hp-size',settings.hp_text_size+'px');
    const versions=settings.hp_asset_versions||{};
    const png=(kind)=>'url("/overlay/hp-image/'+kind+'.png?v='+encodeURIComponent(versions[kind]||'0')+'")';
    css('--hp-fill-image',settings.hp_custom_fill?png('fill'):'none');
    css('--hp-frame-image',settings.hp_custom_frame?png('frame'):'none');
    css('--hp-art-width','calc('+settings.slot_width+'px - '+(2*settings.hp_border_width)+'px)');
    css('--info-size',(settings.info_size||14)+'px');
    css('--stats-size',(settings.stats_size||20)+'px');
    css('--slot-frame',settings.slot_frame?'url("/overlay/slot-frame.png?v='+
      encodeURIComponent(settings.slot_frame_version||'0')+'")':'none');
    root.dataset.death=deathStyle();
    let font=settings.font === 'monospace'?'monospace':'"'+settings.font.replaceAll('"','')+'",sans-serif';
    if(settings.font_file) {
      const family='UserOverlayFont';
      let sheet=document.getElementById('custom-font-rule');
      if(!sheet){sheet=document.createElement('style');sheet.id='custom-font-rule';document.head.append(sheet);}
      const filename=encodeURIComponent(settings.font_file);
      sheet.textContent='@font-face{font-family:"UserOverlayFont";src:url("/overlay/font/'+filename+'") format("'+
        (settings.font_file.endsWith('.woff2')?'woff2':settings.font_file.endsWith('.woff')?'woff':
        settings.font_file.endsWith('.otf')?'opentype':'truetype')+'");font-display:swap}';
      font='"'+family+'",sans-serif';
    } else document.getElementById('custom-font-rule')?.remove();
    css('--font',font);
    if(structural)rebuild();
  }
  function healthLabel(p) {
    if(p.hp===null||p.max_hp===null)return '';
    if(settings.hp_label==='fraction')return p.hp+' / '+p.max_hp;
    if(settings.hp_label==='percent')return Math.round(p.percent)+'%';
    if(settings.hp_label==='both')return p.hp+' / '+p.max_hp+' · '+Math.round(p.percent)+'%';
    return '';
  }
  function drawCounter(state) {
    const group=nodes.counter;
    if(!group)return;
    const signature=JSON.stringify([state.death_count,settings.counter_mode,
      settings.counter_total,settings.counter_lost,settings.counter_custom_icon,
      settings.counter_icon_version]);
    if(group.dataset.signature===signature)return;
    group.dataset.signature=signature;
    group.replaceChildren();
    group.removeAttribute('aria-label');
    group.hidden=!settings.counter_mode || settings.counter_mode==='off';
    if(group.hidden)return;
    const deaths=Number.isInteger(state.death_count)&&state.death_count>=0?state.death_count:0;
    if(settings.counter_mode==='deaths'){
      mk('span','counter-number',group).textContent='Muertes: '+deaths;
      return;
    }
    const remaining=Math.max(0,settings.counter_total-deaths);
    group.setAttribute('aria-label','Vidas: '+remaining+' de '+settings.counter_total);
    mk('span','counter-number',group).textContent='Vidas: '+remaining;
    for(let i=0;i<settings.counter_total;i++){
      const lost=i>=remaining;
      if(lost && settings.counter_lost==='hide')continue;
      const icon=mk(settings.counter_custom_icon?'img':'span','counter-icon'+(lost?' lost':''),group);
      icon.setAttribute('aria-hidden','true');
      if(settings.counter_custom_icon){
        icon.alt='';
        icon.src='/overlay/counter-icon.png?v='+encodeURIComponent(settings.counter_icon_version||'0');
      }else icon.textContent='♥';
    }
  }
  // Graveyard: rebuilt only when its contents or options change (no flicker).
  // Images are requested by a stable id; a sprite still downloading is retried.
  const GRAVE_RETRIES=6, GRAVE_RETRY_MS=5000;
  const setQuery=()=>settings?.sprite_set?'?set='+encodeURIComponent(settings.sprite_set):'';
  const withParam=(url,param)=>url+(url.includes('?')?'&':'?')+param;
  function graveImage(record){
    const img=mk('img','grave-sprite');
    img.alt='';img.draggable=false;
    const src='/overlay/graveyard/'+encodeURIComponent(record.image_rev)+setQuery();
    let attempts=0;
    img.addEventListener('error',()=>{
      img.style.visibility='hidden';
      if(++attempts>GRAVE_RETRIES)return;
      setTimeout(()=>{img.src=withParam(src,'retry='+attempts);},GRAVE_RETRY_MS);
    });
    img.addEventListener('load',()=>{img.style.visibility='visible';});
    img.src=src;
    return img;
  }
  function drawGraveyard(state){
    const group=nodes.graveyard;
    if(!group)return;
    const all=Array.isArray(state.graveyard)?state.graveyard:[];
    const max=Math.max(1,Math.min(60,settings.graveyard_max||12));
    // The server already sends the list in the chosen order.
    const shown=all.slice(0,max);
    const signature=JSON.stringify([settings.sprite_set||'',shown.map(g=>[g.image_rev,g.nickname,g.species,g.level,g.route]),
      state.graveyard_total,settings.graveyard_title,settings.graveyard_show_name,settings.graveyard_show_species,
      settings.graveyard_show_level,settings.graveyard_show_route]);
    if(group.dataset.signature===signature)return;
    group.dataset.signature=signature;
    group.replaceChildren();
    if(settings.graveyard_title){
      const fallen=Number.isInteger(state.graveyard_total)?state.graveyard_total:all.length;
      mk('div','grave-title',group).textContent='Cementerio · '+fallen;
    }
    const grid=mk('div','grave-grid',group);
    for(const record of shown){
      const card=mk('div','grave-card',grid);
      card.append(graveImage(record));
      if(settings.graveyard_show_name)mk('span','grave-name',card).textContent=record.nickname||record.species||'';
      if(settings.graveyard_show_species&&record.species&&record.species!==record.nickname)
        mk('span','grave-species',card).textContent=record.species;
      if(settings.graveyard_show_level&&Number.isInteger(record.level))
        mk('span','grave-level',card).textContent='Nv. '+record.level;
      if(settings.graveyard_show_route&&record.route)mk('span','grave-route',card).textContent=record.route;
    }
  }
  // Stats: run totals in one line (or one column); each figure is optional.
  const STAT_ENTRIES=[['captures','Capturas'],['deaths','Muertes'],['alive','Vivos'],['missed','Rutas perdidas']];
  function drawStats(state){
    const group=nodes.stats;
    if(!group)return;
    const raw=state.stats&&typeof state.stats==='object'?state.stats:{};
    const count=key=>Number.isInteger(raw[key])&&raw[key]>=0?raw[key]:0;
    const shown=STAT_ENTRIES.filter(([key])=>settings['stats_show_'+key]!==false);
    const direction=settings.stats_direction==='column'?'column':'row';
    const signature=JSON.stringify([direction,shown.map(([key,label])=>[label,count(key)])]);
    if(group.dataset.signature===signature)return;
    group.dataset.signature=signature;
    group.dataset.direction=direction;
    group.replaceChildren();
    group.hidden=!shown.length;
    for(const [key,label] of shown){
      const item=mk('span','stat stat-'+key,group);
      mk('span','stat-label',item).textContent=label;
      mk('span','stat-value',item).textContent=String(count(key));
    }
  }
  // Info: «Nv. 50», type badges, ★ when shiny and ♂/♀. Type names come from
  // the game data, so they are only ever written with textContent.
  const TYPE_SLUGS=new Set(['normal','fuego','agua','planta','electrico','hielo','lucha','veneno','tierra',
    'volador','psiquico','bicho','roca','fantasma','dragon','siniestro','acero','hada']);
  const typeSlug=name=>{
    const slug=String(name).normalize('NFD').replace(/[̀-ͯ]/g,'').toLowerCase();
    return TYPE_SLUGS.has(slug)?slug:'desconocido';
  };
  function drawInfo(el,p){
    const box=el.firstElementChild;
    const level=Number.isInteger(p.level)&&p.level>0?p.level:null;
    const types=Array.isArray(p.types)?p.types.filter(t=>typeof t==='string'&&t).slice(0,2):[];
    const gender=p.gender===0||p.gender===1?p.gender:null;
    const show=['level','types','shiny','gender'].map(key=>settings['info_show_'+key]!==false);
    const signature=JSON.stringify([Boolean(p.present),level,types,p.shiny===true,gender,show]);
    if(box.dataset.signature===signature)return;
    box.dataset.signature=signature;
    box.replaceChildren();
    if(!p.present)return;
    const [showLevel,showTypes,showShiny,showGender]=show;
    if(showLevel&&level!==null)mk('span','info-level',box).textContent='Nv. '+level;
    if(showTypes)for(const type of types)mk('span','info-type type-'+typeSlug(type),box).textContent=type;
    if(showShiny&&p.shiny===true){
      const star=mk('span','info-shiny',box);
      star.textContent='★';star.setAttribute('aria-label','Variocolor');
    }
    if(showGender&&gender!==null){
      const sign=mk('span','info-gender '+(gender===1?'female':'male'),box);
      sign.textContent=gender===1?'♀':'♂';sign.setAttribute('aria-label',gender===1?'Hembra':'Macho');
    }
  }
  // Dead sprites: gray (default), hidden, or replaced by a tombstone image.
  const DEATH_STYLES=new Set(['gray','tombstone','hide']), DEATH_ANIMATION_MS=1100;
  let dyingCount=0;
  function deathStyle(){return DEATH_STYLES.has(settings?.death_style)?settings.death_style:'gray';}
  function clearDying(el){
    el.classList.toggle('dying-fade',false);el.classList.toggle('dying-shake',false);delete el.dataset.dyingAt;
  }
  // The animation plays once, only when a Pokémon seen alive in this slot dies.
  // A source opened (or rebuilt) with the Pokémon already dead shows it at rest.
  function deathTransition(el,p,dead){
    const identity=String(p.species_id??'')+'|'+String(p.nickname??'');
    const before=el.dataset.life, sameMon=el.dataset.identity===identity;
    el.dataset.life=p.present?(dead?'dead':'alive'):'';
    el.dataset.identity=identity;
    if(!dead){clearDying(el);return;}
    const kind=settings.death_animation;
    if(before!=='alive'||!sameMon||(kind!=='fade'&&kind!=='shake'))return;
    clearDying(el);
    el.classList.toggle('dying-'+kind,true);
    const stamp=String(++dyingCount);
    el.dataset.dyingAt=stamp;
    // Removing the class afterwards keeps a later style change from replaying it.
    setTimeout(()=>{if(el.dataset.dyingAt===stamp)clearDying(el);},DEATH_ANIMATION_MS);
  }
  function draw(state) {
    if(!settings||!state?.party)return;
    drawCounter(state);
    drawGraveyard(state);
    drawStats(state);
    for (const p of state.party) {
      for(const type of visibleLayers()) {
        const el=nodes[type+':'+p.slot]; if(!el)continue;
        el.classList.toggle('empty',!p.present&&!settings.show_empty);
        el.classList.toggle('stale',Boolean(p.stale));
        if(type==='sprites'){
          const img=el.firstElementChild;
          const ver=p.image_rev||'0';
          // Keep GIF animation playing between state polls. Reload only on file changes.
          const format=['png','gif','webp'].includes(p.image_format)?p.image_format:'png';
          const src='/overlay/media/pokemon_'+p.slot+'.'+format+'?v='+encodeURIComponent(ver);
          if(img.dataset.src!==src){img.dataset.src=src;img.src=src;}
          img.style.visibility=p.present?'visible':'hidden';
          // Gray here too: the exported file may still be the colored one
          // (slow animated conversion, HD sprite limits or an older cache).
          const dead=Boolean(p.present&&p.dead);
          el.classList.toggle('dead',dead);
          const tomb=el.lastElementChild;
          if(dead&&deathStyle()==='tombstone'){
            const tombSrc='/overlay/death-image?v='+encodeURIComponent(settings.death_image_version||'0');
            if(tomb.dataset.src!==tombSrc){tomb.dataset.src=tombSrc;tomb.src=tombSrc;}
          }
          deathTransition(el,p,dead);
        } else if(type==='info'){
          drawInfo(el,p);
        } else if(type==='names'){
          const label=el.firstElementChild;
          label.textContent=p.present?p.nickname:(settings.show_empty?'—':'');
        } else if(type==='items'){
          const icon=el.firstElementChild,label=el.lastElementChild;
          const mode=['name','icon','both'].includes(settings.item_display)?settings.item_display:'name';
          const id=Number.isInteger(p.item_id)&&p.item_id>0&&p.present&&p.item?p.item_id:0;
          const src=id?'/overlay/item/'+id+'.png'+setQuery():'';
          const wantIcon=mode!=='name'&&Boolean(src);
          if(wantIcon&&icon.dataset.src!==src){icon.dataset.src=src;icon.src=src;}
          // Offline when OBS started: retry a failed icon once a minute.
          if(wantIcon&&icon.dataset.failed===src&&Date.now()-Number(icon.dataset.failedAt||0)>ICON_RETRY_MS){
            delete icon.dataset.failed;icon.src=withParam(src,'retry='+Date.now());
          }
          const failed=wantIcon&&icon.dataset.failed===src;
          icon.hidden=!wantIcon||failed;
          const showName=p.present&&p.item&&(mode!=='icon'||failed);
          label.textContent=showName?p.item:'';
        } else {
          const line=el.firstElementChild, track=line.firstElementChild, fill=track.firstElementChild, caption=line.lastElementChild;
          const pct=p.percent??0;
          const healthColor=p.dead?settings.hp_low:(pct<=settings.hp_low_threshold?settings.hp_low:
             pct<=settings.hp_mid_threshold?settings.hp_mid:settings.hp_good);
          line.style.setProperty('--hp-color',healthColor);
          track.classList.toggle('reverse',settings.hp_reverse);
          track.classList.toggle('custom-frame',settings.hp_custom_frame);
          fill.className='hp-fill '+(settings.hp_custom_fill?'custom-fill':settings.hp_style)+
            (settings.hp_glow?' glow':'');
          fill.style.width=(p.present?Math.min(100,Math.max(0,pct)):0)+'%';
          caption.textContent=p.present?healthLabel(p):'';
          caption.style.display=settings.hp_label==='none'?'none':'';
        }
      }
    }
  }
  // One request chain at a time: a slow backend never stacks requests, and an
  // older response can no longer repaint over a newer one. Appearance changes
  // are rarer than HP changes, so settings are refreshed every third tick.
  const POLL_MS=500, SETTINGS_EVERY=3, ICON_RETRY_MS=60000, PRESET_RETRY_TICKS=60;
  let tick=0, presetMissing=false;
  // Unknown preset (deleted or misspelled): fall back to the current style and
  // look for the preset again every ~30 s, one request after the other.
  async function fetchSettings(){
    if(preset&&(!presetMissing||tick%PRESET_RETRY_TICKS===0)){
      const response=await fetch('/api/overlay/settings?preset='+encodeURIComponent(preset),{cache:'no-store'});
      if(response.status!==404){presetMissing=false;return response;}
      presetMissing=true;
    }
    return fetch('/api/overlay/settings',{cache:'no-store'});
  }
  async function poll() {
    try {
      const wantSettings=!settings||tick%SETTINGS_EVERY===0;
      const [a,b]=await Promise.all([
        // The pinned preset also decides server-side choices (graveyard order).
        fetch('/api/overlay/public'+(preset&&!presetMissing?'?preset='+encodeURIComponent(preset):''),{cache:'no-store'}),
        wantSettings?fetchSettings():null]);
      if(!a.ok||(b&&!b.ok))throw new Error('overlay unavailable');
      if(b)appearance(await b.json());
      draw(await a.json());
    }catch(error){ /* disconnected backend: preserve the last rendered values */ }
    finally{tick++;setTimeout(poll,POLL_MS);}
  }
  poll();
})();
