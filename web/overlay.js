'use strict';
/* Browser source reads six sanitized slots and a death total from the public API. */
(() => {
  const args = new URLSearchParams(location.search);
  const allowed = new Set(['all','sprites','names','hp','counter']);
  const layer = allowed.has(args.get('layer')) ? args.get('layer') : 'all';
  const slotArg = Number(args.get('slot'));
  const slot = Number.isInteger(slotArg) && slotArg >= 1 && slotArg <= 6 ? slotArg : null;
  const root = document.getElementById('overlay');
  let settings = null, lastConfig = '', nodes = {};
  const mk = (tag, cls, parent) => {
    const el = document.createElement(tag);
    if (cls) el.className = cls;
    if (parent) parent.append(el);
    return el;
  };
  const css = (key, value) => document.documentElement.style.setProperty(key,value);
  const visibleLayers = () => layer === 'all'
    ? [...settings.order, ...(settings.counter_in_composition ? ['counter'] : [])] : [layer];
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
      for (const n of (slot ? [slot] : [1,2,3,4,5,6])) {
        const node = mk('div','overlay-slot',group);
        nodes[type+':'+n] = node;
        if (type === 'sprites') {
          const image = mk('img','overlay-image',node);
          image.alt = ''; image.draggable = false;
        } else if (type === 'names') {
          mk('span','overlay-name',node);
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
        settings.counter_in_composition !== value.counter_in_composition;
    settings=value;lastConfig=signature;
    // CSS zoom reflows/rasterizes fonts and vector HP tracks at real scaled
    // dimensions; transform:scale only enlarges previously rasterized pixels.
    root.style.zoom=String(settings.render_scale||1);
    fitViewport();
    css('--counter-icon',(settings.counter_icon_size||36)+'px');
    css('--sprite-render',settings.sprite_scaling==='smooth'?'auto':'pixelated');
    css('--sprite-padding',(settings.sprite_padding||0)+'px');
    css('--sprite-shadow',settings.sprite_shadow?'drop-shadow(0 4px 7px #000a)':'none');
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
  function draw(state) {
    if(!settings||!state?.party)return;
    drawCounter(state);
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
        } else if(type==='names'){
          const label=el.firstElementChild;
          label.textContent=p.present?p.nickname:(settings.show_empty?'—':'');
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
  async function poll() {
    try {
      const [a,b]=await Promise.all([
        fetch('/api/overlay/public',{cache:'no-store'}),
        fetch('/api/overlay/settings',{cache:'no-store'})]);
      if(!a.ok||!b.ok)throw new Error('overlay unavailable');
      appearance(await b.json());
      draw(await a.json());
    }catch(error){ /* disconnected backend: preserve the last rendered values */ }
  }
  poll();
  setInterval(poll,500);
})();
