'use strict';
/* Browser source reads only six sanitized slots from the public overlay API. */
(() => {
  const args = new URLSearchParams(location.search);
  const allowed = new Set(['all','sprites','names','hp']);
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
  function rebuild() {
    root.replaceChildren(); nodes = {};
    const types = layer === 'all' ? settings.order : [layer];
    for (const type of types) {
      const group = mk('section','overlay-layer',root);
      group.dataset.layer = type;
      group.dataset.direction = settings.direction;
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
          mk('div','hp-fill',track);
          mk('span','hp-label',hp);
        }
      }
    }
  }
  function appearance(value) {
    if (!value) return;
    const signature=JSON.stringify(value);
    if(signature===lastConfig)return;
    const structural = !settings || settings.direction !== value.direction ||
        JSON.stringify(settings.order)!==JSON.stringify(value.order);
    settings=value;lastConfig=signature;
    css('--slot',settings.slot_width+'px');css('--gap',settings.gap+'px');
    css('--sprite',settings.sprite_size+'px');
    css('--name',settings.name_size+'px');css('--fg',settings.name_color);
    css('--outline',settings.name_outline);css('--weight',String(settings.name_weight));
    css('--hp-h',settings.hp_height+'px');css('--radius',settings.hp_radius+'px');
    css('--border',settings.hp_border_width+'px');css('--border-color',settings.hp_border);
    css('--track',settings.hp_background);css('--hp-text',settings.hp_text_color);
    css('--hp-size',settings.hp_text_size+'px');
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
  function draw(state) {
    if(!settings||!state?.party)return;
    for (const p of state.party) {
      for(const type of (layer==='all'?settings.order:[layer])) {
        const el=nodes[type+':'+p.slot]; if(!el)continue;
        el.classList.toggle('empty',!p.present&&!settings.show_empty);
        el.classList.toggle('stale',Boolean(p.stale));
        if(type==='sprites'){
          const img=el.firstElementChild;
          const ver=p.image_rev||'0';
          // Keep GIF animation playing between state polls. Reload only on file changes.
          const src='/overlay/media/pokemon_'+p.slot+'.gif?v='+encodeURIComponent(ver);
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
          fill.className='hp-fill '+settings.hp_style+(settings.hp_glow?' glow':'');
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