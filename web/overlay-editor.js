'use strict';
(() => {
  const $=id=>document.getElementById(id), fields=[
    'frame_enabled','frame_color','frame_width','frame_radius',
    'frame_names_height','frame_items_height','frame_info_height','graveyard_layout','graveyard_gap',
    'direction','gap','slot_width','sprite_size','name_size','name_color',
    'name_weight','font','font_file','name_outline','hp_height','hp_radius',
    'hp_background','hp_border','hp_border_width','hp_good','hp_mid','hp_low',
    'hp_low_threshold','hp_mid_threshold','hp_label','hp_text_color','hp_text_size',
    'hp_style','hp_reverse','hp_glow','show_empty','hp_custom_fill','hp_custom_frame',
    'counter_mode','counter_total','counter_lost','counter_icon_size','counter_in_composition','counter_custom_icon',
    'render_scale','sprite_scaling','sprite_shadow','sprite_padding','hp_animation_ms',
    'items_in_composition','item_size','item_color','item_display','item_icon_size',
    'sprite_set','graveyard_max','graveyard_columns','graveyard_sprite_size','graveyard_order',
    'graveyard_title','graveyard_show_name','graveyard_show_species','graveyard_show_level','graveyard_show_route',
    'death_style','death_animation','slot_frame',
    'info_in_composition','info_size','info_show_level','info_show_types','info_show_shiny','info_show_gender',
    'stats_show_captures','stats_show_deaths','stats_show_alive','stats_show_missed','stats_direction','stats_size',
  ];
  const numberFields=new Set(['frame_width','frame_radius','frame_names_height','frame_items_height','frame_info_height','graveyard_gap','gap','slot_width','sprite_size','name_size','name_weight','hp_height',
    'hp_radius','hp_border_width','hp_low_threshold','hp_mid_threshold','hp_text_size',
    'render_scale','sprite_padding','hp_animation_ms','counter_total','counter_icon_size','item_size','item_icon_size',
    'graveyard_max','graveyard_columns','graveyard_sprite_size','info_size','stats_size']);
  const checkFields=new Set(['frame_enabled','hp_reverse','hp_glow','show_empty','hp_custom_fill','hp_custom_frame','sprite_shadow','counter_in_composition','counter_custom_icon','items_in_composition',
    'graveyard_title','graveyard_show_name','graveyard_show_species','graveyard_show_level','graveyard_show_route',
    'slot_frame','info_in_composition','info_show_level','info_show_types','info_show_shiny','info_show_gender',
    'stats_show_captures','stats_show_deaths','stats_show_alive','stats_show_missed']);
  // OBS sources drawn once for the whole team: a slot number does not apply.
  const SINGLE_LAYERS=new Set(['counter','graveyard','stats']);
  const LINKS=[['Composición','all'],['Sprites','sprites'],['Motes','names'],['Vida','hp'],['Objetos','items'],
    ['Datos','info'],['Muertes / vidas','counter'],['Cementerio','graveyard'],['Estadísticas','stats']];
  // Same rule as the server (tracker/overlay/presets.py): 1-40 characters, no surrounding spaces.
  const PRESET_NAME=/^[A-Za-z0-9 _\-áéíóúüñÁÉÍÓÚÜÑ]{1,40}$/;
  const status=$('status');
  let token='',pending=null,defaultConfig=null,loading=true;
  let shared={enabled:false,ip:'',port:null,base_url:''},lastEdited=null,publicParty=[];
  function localMessage(control,text,problem=false){
    if(!control)return;
    const id='message-'+control.id;
    let message=$(id);
    if(!message){
      message=document.createElement('p');message.id=id;message.className='control-status';
      message.setAttribute('role','status');message.setAttribute('aria-live','polite');
      const anchor=control.closest('label')||control;
      anchor.insertAdjacentElement('afterend',message);
      const described=control.getAttribute('aria-describedby')||'';
      control.setAttribute('aria-describedby',(described+' '+id).trim());
    }
    message.textContent=text;message.dataset.error=String(problem);
    if(problem&&control.matches('input,select'))control.setAttribute('aria-invalid','true');
    else control.removeAttribute('aria-invalid');
  }
  function say(text,problem=false,control=null){
    status.textContent=text;status.dataset.error=String(problem);
    if(control)localMessage(control,text,problem);
  }
  function reportHeight(){
    if(window.parent===window)return;
    const height=Math.ceil(document.body.getBoundingClientRect().height);
    if(height===reportHeight.last)return;
    reportHeight.last=height;
    window.parent.postMessage({type:'tracker-overlay-resize',height},location.origin);
  }
  let resizePending=false;
  function scheduleHeight(){
    if(resizePending)return;
    resizePending=true;requestAnimationFrame(()=>{resizePending=false;reportHeight()});
  }
  if(typeof ResizeObserver!=='undefined')new ResizeObserver(scheduleHeight).observe(document.body);
  window.addEventListener('resize',scheduleHeight);
  document.fonts?.ready.then(scheduleHeight);
  function sourceDimensions(){
    const c=read(),scale=c.render_scale||1;
    const boxes=OverlayLayout.measure(c,$('slot').value?1:6);
    for(const el of document.querySelectorAll('[data-source-size]')){
      const box=boxes[el.dataset.sourceSize];
      el.textContent=Math.ceil(box.width*scale)+' \u00d7 '+Math.ceil(box.height*scale)+' px';
    }
    $('source-size').textContent='Dimensiones fijas para OBS. El contenido se ajusta dentro del recuadro.';
    const box=boxes[$('preview-layer').value];
    updatePreview(Math.ceil(box.width*scale),Math.ceil(box.height*scale));
    $('graveyard_columns').disabled=c.graveyard_layout!=='custom';
  }
  // Live preview: the real overlay page in a same-origin iframe. It re-reads the
  // saved settings by itself, so only its URL and its box size are managed here.
  function previewUrl(){
    const layer=$('preview-layer').value,slot=$('slot').value;
    return '/overlay?layer='+encodeURIComponent(layer)+(slot&&!SINGLE_LAYERS.has(layer)?'&slot='+slot:'')+($('preview-bounds').checked?'&bounds=1':'');
  }
  function updatePreview(width,height){
    const frame=$('preview-frame'),stage=$('preview-stage');
    const url=previewUrl();
    if(frame.dataset.src!==url){frame.dataset.src=url;frame.src=url;}
    const w=Math.max(40,width),h=Math.max(40,height);
    const available=stage.clientWidth||w;
    const fit=Math.min(1,available/w);
    frame.style.width=w+'px';frame.style.height=h+'px';
    frame.style.transform=fit<1?'scale('+fit+')':'';
    stage.style.height=Math.ceil(h*fit)+'px';
    $('preview-size').textContent='Fuente de '+width+' × '+height+' px'+
      (fit<1?', mostrada al '+Math.round(fit*100)+' % para que quepa.':'.');
  }
  function setupLinks(){
    const slot=$('slot').value,container=$('links');container.replaceChildren();
    const remote=$('link-target').value==='vpn'&&shared.enabled;
    const base=remote?shared.base_url:location.origin;
    const pinned=$('preset-pin').checked?$('preset-list').value:'';
    for(const [label,layer] of LINKS){
      const url=base+'/overlay?layer='+layer+(slot&&!SINGLE_LAYERS.has(layer)?'&slot='+slot:'')+
        (pinned?'&preset='+encodeURIComponent(pinned):'');
      const row=document.createElement('div');row.className='link-line';
      const title=document.createElement('label');title.textContent=label;title.htmlFor='source-url-'+layer;
      const input=document.createElement('input');input.id='source-url-'+layer;input.readOnly=true;input.value=url;
      const copy=document.createElement('button');copy.type='button';copy.textContent='Copiar';copy.setAttribute('aria-label','Copiar enlace de '+label);
      copy.onclick=async()=>{try{await navigator.clipboard.writeText(url);say('Enlace de '+label+' copiado',false,input);}catch(e){input.select();say('Selecciona y copia el enlace',false,input)}};
      const size=document.createElement('small');size.className='source-dimensions';size.dataset.sourceSize=layer;
      row.append(title,input,copy,size);container.append(row);
    }
  }
  function read(){
    const out={};
    for(const key of fields) {
      const control=$(key);
      out[key]=checkFields.has(key)?control.checked:
        numberFields.has(key)?Number(control.value):control.value;
    }
    out.order=$('order').value.split(',');
    return out;
  }
  function fill(settings){
    loading=true;
    for(const key of fields){
      // A key the server did not send keeps the control's own default value.
      const input=$(key);if(!input||!(key in settings))continue;
      if(checkFields.has(key))input.checked=settings[key];
      else input.value=settings[key];
      const output=document.querySelector('[data-for="'+key+'"]');
      if(output)output.textContent=String(settings[key]);
    }
    $('order').value=settings.order.join(',');
    loading=false;sourceDimensions();scheduleHeight();
  }
  async function post(endpoint,payload){
    const response=await fetch(endpoint,{method:'POST',headers:{'X-Tracker-Token':token,
      'Content-Type':'application/json'},body:JSON.stringify(payload)});
    const data=await response.json();
    if(!response.ok)throw new Error(data.error||'No se pudo guardar');
    return data;
  }
  // Serialize saves: two overlapping POSTs could land out of order and leave
  // the older configuration stored. A request made while one is in flight is
  // coalesced and sent with the latest values once the previous one finishes.
  // `queue` resolves only after the values current at call time are stored,
  // and a coalesced save reports on the control edited last.
  let queue=null,queuedControl=null;
  function save(control=lastEdited||$('save')){
    if(loading)return Promise.resolve();
    queuedControl=control;
    if(queue)return queue;
    queue=(async()=>{
      let result=null;
      while(queuedControl){
        const target=queuedControl;queuedControl=null;
        result=await saveNow(target);
      }
      // Same synchronous step as the loop check: no call can slip in between.
      queue=null;
      return result;
    })();
    return queue;
  }
  async function saveNow(control){
    try{
      const saved=await post('/api/overlay/settings',read());
      say('Personalización guardada');
      if($('message-'+control.id))localMessage(control,'Personalización guardada');
      $('save-status').textContent='Personalización guardada';sourceDimensions();
      return saved;
    }catch(error){say(error.message,true,control);$('save-status').textContent=error.message;return null;}
  }
  $('save').onclick=()=>save($('save'));
  $('reset').onclick=()=>{if(!defaultConfig)return;fill(defaultConfig);save()};
  $('slot').onchange=()=>{setupLinks();sourceDimensions()};
  for(const control of [...document.querySelectorAll('.controls input,.controls select'),$('order')]){
    control.addEventListener('input',()=>{
      const output=document.querySelector('[data-for="'+control.id+'"]');
      if(output)output.textContent=control.value;
      if(loading||control.type==='file')return;
      lastEdited=control;sourceDimensions();
      clearTimeout(pending);pending=setTimeout(save,350);
    });
  }
  function displayShare(){
    const status=$('share-status');
    status.textContent=shared.enabled
      ?'Compartiendo solo el overlay en '+shared.base_url+'. Comparte los enlaces VPN con tu compañero.'
      :'Acceso remoto apagado: únicamente puedes usar las URL de 127.0.0.1.';
    $('share-disable').disabled=!shared.enabled;
    setupLinks();
  }
  $('link-target').onchange=setupLinks;
  $('share-enable').onclick=async()=>{
    try{
      const ip=$('share-ip').value.trim();
      const result=await post('/api/overlay/share',{enabled:true,ip});
      shared=result;
      try{localStorage.setItem('progressive-obs-vpn-ip',ip)}catch(_){}
      $('link-target').value='vpn';
      displayShare();sourceDimensions();say('Fuente VPN activada · comparte estas URL con tu compañero',false,$('share-ip'));
    }catch(error){say('VPN: '+error.message,true,$('share-ip'))}
  };
  $('share-disable').onclick=async()=>{
    try{
      shared=await post('/api/overlay/share',{enabled:false});
      $('link-target').value='local';
      displayShare();sourceDimensions();say('Acceso VPN desactivado',false,$('share-ip'));
    }catch(error){say('VPN: '+error.message,true,$('share-ip'))}
  };
  const encodeFile=async(file)=>{
    const bytes=new Uint8Array(await file.arrayBuffer());
    let result='';
    for(let i=0;i<bytes.length;i+=24000){
      result+=btoa(String.fromCharCode(...bytes.subarray(i,i+24000)));
    }
    return result;
  };
  $('counter_icon_upload').onchange=async()=>{
    const control=$('counter_icon_upload'),file=control.files?.[0];
    if(!file)return;
    try{
      if(file.size>8_000_000)throw new Error('El PNG supera los 8 MB');
      if(!file.name.toLowerCase().endsWith('.png'))throw new Error('Selecciona un archivo PNG');
      await post('/api/overlay/counter-icon',{data:await encodeFile(file)});
      $('counter_custom_icon').checked=true;
      if(!await save(control))return;
      say('Icono de vidas importado',false,control);
    }catch(error){say('Icono: '+error.message,true,control)}
    finally{control.value=''}
  };
  // Destination set for imports: the typed new name, else the selected set.
  function importTarget(){
    const typed=$('sprite-set-new').value.trim();
    if(typed&&!/^[A-Za-z0-9][A-Za-z0-9 _-]{0,39}$/.test(typed))
      throw new Error('Nombre de conjunto inválido: letras, números, espacios, - o _ (máx. 40)');
    return typed||$('sprite_set').value||'';
  }
  async function importImages(control,endpoint,noun){
    const files=[...(control.files||[])];
    if(!files.length)return;
    if(files.length>30){say('Importa hasta 30 archivos por lote',true,control);return;}
    let imported=0,folder='';
    try{
      const target=importTarget();
      for(const file of files){
        if(file.size>8_000_000)throw new Error(file.name+': máximo 8 MB por archivo');
        const ext=(file.name.split('.').pop()||'').toLowerCase();
        if(!['png','apng','gif','webp','jpg','jpeg','bmp'].includes(ext))
          throw new Error(file.name+': extensión no admitida');
        const rawName=file.name.slice(0,-ext.length-1);
        const stem=rawName.normalize('NFKD').replace(/[\u0300-\u036f]/g,'')
          .replace(/[^A-Za-z0-9_-]+/g,'-').replace(/^-+|-+$/g,'').slice(0,80);
        if(!stem)throw new Error('Nombre de archivo inválido');
        const result=await post(endpoint,{name:stem+'.'+ext,data:await encodeFile(file),sprite_set:target});
        folder=result.path_hint||folder;
        imported++;
        say(noun+' importados: '+imported+' / '+files.length,false,control);
      }
      return {imported,folder,target};
    }catch(error){say('Importación ('+imported+'/'+files.length+'): '+error.message,true,control);return null;}
    finally{control.value='';}
  }
  $('sprite-upload').onchange=async()=>{
    const result=await importImages($('sprite-upload'),'/api/overlay/sprite','Sprites');
    if(!result)return;
    $('sprite-import-info').textContent='Importados '+result.imported+' sprites en '+result.folder+'. OBS los actualizará automáticamente.';
    if(result.target&&result.target!==$('sprite_set').value){$('sprite-set-new').value='';await loadSpriteSets(result.target);}
  };
  // Outside .controls, so it is wired explicitly: switching sets saves at once.
  $('sprite_set').onchange=()=>{if(loading)return;lastEdited=$('sprite_set');save($('sprite_set'));};
  $('item-sprite-upload').onchange=async()=>{
    const result=await importImages($('item-sprite-upload'),'/api/overlay/item-sprite','Iconos');
    if(!result)return;
    $('item-sprite-info').textContent='Importados '+result.imported+' iconos en '+result.folder+'.';
    if(result.target&&result.target!==$('sprite_set').value){$('sprite-set-new').value='';await loadSpriteSets();}
  };
  async function loadSpriteSets(select){
    try{
      const response=await fetch('/api/overlay/sprite-sets');
      if(!response.ok)return;
      const data=await response.json(),input=$('sprite_set'),prior=select??input.value;
      input.replaceChildren(new Option('Carpeta principal',''));
      for(const name of Array.isArray(data.sets)?data.sets:[])input.add(new Option(name,name));
      if([...input.options].some(o=>o.value===prior))input.value=prior;
      if(select!==undefined&&input.value===select&&!loading){lastEdited=input;save(input);}
    }catch(_){}
  }
  async function importHealth(kind){
    const control=$('hp_'+kind+'_upload');
    const file=control.files?.[0];if(!file)return;
    try{
      if(file.size>8_000_000)throw new Error('El PNG supera los 8 MB');
      if(!file.name.toLowerCase().endsWith('.png'))throw new Error('Selecciona un archivo PNG');
      const info=await post('/api/overlay/hp-image',{kind,data:await encodeFile(file)});
      $('hp_custom_'+kind).checked=true;
      if(!await save(control))return;
      say('Imagen de '+(kind==='fill'?'relleno':'marco')+' importada ('+info.width+'×'+info.height+')',false,control);
    }catch(error){say('PNG: '+error.message,true,control)}
    finally{control.value=''}
  }
  $('hp_fill_upload').onchange=()=>importHealth('fill');
  $('hp_frame_upload').onchange=()=>importHealth('frame');
  // Frame behind each sprite: same PNG endpoint as the HP bar, kind 'slot'.
  $('slot_frame_upload').onchange=async()=>{
    const control=$('slot_frame_upload'),file=control.files?.[0];
    if(!file)return;
    try{
      if(file.size>8_000_000)throw new Error('El PNG supera los 8 MB');
      if(!file.name.toLowerCase().endsWith('.png'))throw new Error('Selecciona un archivo PNG');
      const info=await post('/api/overlay/hp-image',{kind:'slot',data:await encodeFile(file)});
      $('slot_frame').checked=true;
      if(!await save(control))return;
      say('Marco importado'+(info.width?' ('+info.width+'×'+info.height+')':''),false,control);
    }catch(error){say('Marco: '+error.message,true,control)}
    finally{control.value=''}
  };

  // --- Preview -------------------------------------------------------------
  $('preview-layer').onchange=sourceDimensions;
  $('preview-bounds').onchange=sourceDimensions;
  let stageWidth=0;
  if(typeof ResizeObserver!=='undefined')new ResizeObserver(entries=>{
    const width=Math.round(entries[0].contentRect.width);
    if(width!==stageWidth){stageWidth=width;sourceDimensions();}
  }).observe($('preview-stage'));

  // --- Style presets -------------------------------------------------------
  function sectionMessage(id,text,problem=false,control=null){
    say(text,problem);
    const message=$(id);message.textContent=text;message.dataset.error=String(problem);
    for(const el of document.querySelectorAll('[aria-invalid="true"]'))
      if(el.closest('.panel')===message.closest('.panel'))el.removeAttribute('aria-invalid');
    if(control&&problem)control.setAttribute('aria-invalid','true');
  }
  const presetSay=(text,problem,control)=>sectionMessage('preset-status',text,problem,control);
  const backupSay=(text,problem,control)=>sectionMessage('backup-status',text,problem,control);
  let presetNames=[],deleteTimer=null;
  function resetDeleteConfirm(){
    clearTimeout(deleteTimer);
    const button=$('preset-delete');delete button.dataset.confirm;button.textContent='Eliminar';
  }
  function updatePresetButtons(){
    const has=Boolean($('preset-list').value);
    $('preset-apply').disabled=!has;$('preset-delete').disabled=!has;$('preset-pin').disabled=!has;
    if(!has)$('preset-pin').checked=false;
    resetDeleteConfirm();
  }
  function renderPresets(list,select){
    presetNames=(Array.isArray(list)?list:[]).map(p=>typeof p==='string'?p:p?.name)
      .filter(name=>typeof name==='string'&&name);
    const input=$('preset-list'),prior=select??input.value;
    input.replaceChildren();
    if(!presetNames.length)input.add(new Option('Sin perfiles guardados',''));
    for(const name of presetNames)input.add(new Option(name,name));
    input.value=presetNames.includes(prior)?prior:(presetNames[0]||'');
    updatePresetButtons();setupLinks();sourceDimensions();
  }
  // Settings replaced on the server (preset applied or file imported).
  async function loadReplacedSettings(settings){
    await settleSaves();
    await loadSpriteSets();
    if(settings)fill(settings);
  }
  // Store a debounced edit now, so a preset or export never misses the last
  // change. Resolves to null when that save failed.
  async function flushEdits(){
    const waiting=pending!==null;
    clearTimeout(pending);pending=null;
    if(waiting)return save();
    if(queue)return queue;
    return true;
  }
  // Drop a debounced edit and wait for saves in flight: used right before the
  // server replaces the settings, so an older save cannot land afterwards.
  async function settleSaves(){
    clearTimeout(pending);pending=null;
    if(queue)await queue;
  }
  $('preset-list').onchange=()=>{updatePresetButtons();setupLinks();sourceDimensions();};
  $('preset-pin').onchange=()=>{
    setupLinks();sourceDimensions();
    presetSay($('preset-pin').checked
      ?'Los enlaces copiados mostrarán siempre el perfil «'+$('preset-list').value+'».'
      :'Los enlaces copiados siguen la personalización actual.');
  };
  $('preset-save').onclick=async()=>{
    const control=$('preset-name'),name=control.value.trim();
    if(!PRESET_NAME.test(name)){
      presetSay('Escribe un nombre de 1 a 40 caracteres: letras, números, espacios, - o _',true,control);
      control.focus();return;
    }
    const existed=presetNames.some(n=>n.toLowerCase()===name.toLowerCase());
    try{
      if(await flushEdits()===null)throw new Error('no se pudo guardar el último cambio');
      const result=await post('/api/overlay/presets',{action:'save',name});
      control.value='';
      renderPresets(result.presets,name);
      presetSay('Perfil «'+name+'» '+(existed?'actualizado':'guardado')+' con la personalización actual.');
    }catch(error){presetSay('Perfil: '+error.message,true,control)}
  };
  $('preset-name').addEventListener('keydown',event=>{
    if(event.key==='Enter'){event.preventDefault();$('preset-save').click();}
  });
  $('preset-apply').onclick=async()=>{
    const name=$('preset-list').value;if(!name)return;
    try{
      await settleSaves();
      const result=await post('/api/overlay/presets',{action:'apply',name});
      renderPresets(result.presets,name);
      await loadReplacedSettings(result.settings);
      presetSay('Perfil «'+name+'» aplicado. Las fuentes de OBS lo mostrarán en unos segundos.');
    }catch(error){presetSay('Perfil: '+error.message,true,$('preset-list'))}
  };
  $('preset-delete').onclick=async()=>{
    const name=$('preset-list').value,button=$('preset-delete');if(!name)return;
    if(button.dataset.confirm!==name){
      resetDeleteConfirm();
      button.dataset.confirm=name;button.textContent='Confirmar eliminación';
      presetSay('Pulsa «Confirmar eliminación» para borrar «'+name+'». Las fuentes fijadas a él volverán a la personalización actual.');
      deleteTimer=setTimeout(resetDeleteConfirm,6000);
      return;
    }
    resetDeleteConfirm();
    try{
      const result=await post('/api/overlay/presets',{action:'delete',name});
      renderPresets(result.presets);
      presetSay('Perfil «'+name+'» eliminado.');
    }catch(error){presetSay('Perfil: '+error.message,true,$('preset-list'))}
  };
  async function loadPresets(){
    try{
      const response=await fetch('/api/overlay/presets',{cache:'no-store'});
      if(!response.ok)throw new Error('sin perfiles');
      renderPresets((await response.json()).presets);
    }catch(_){renderPresets([]);}
  }
  updatePresetButtons();

  // --- Export / import -------------------------------------------------------
  function nativeApi(){
    // The editor lives in an iframe of the main window: the bridge is the parent's.
    for(const host of [window.parent,window]){
      try{if(host?.pywebview?.api?.save_export)return host.pywebview.api;}catch(_){}
    }
    return null;
  }
  // Exports stay under the import limit: very large fonts/images may be left out.
  const omittedNote=list=>Array.isArray(list)&&list.length
    ?' No se incluyeron por tamaño: '+list.map(String).slice(0,8).join(', ')+'.':'';
  $('overlay-export').onclick=async()=>{
    const control=$('overlay-export');
    control.disabled=true;
    try{
      if(await flushEdits()===null)throw new Error('no se pudo guardar el último cambio');
      const api=nativeApi();
      if(api){
        const result=await api.save_export('obs');
        if(result?.saved)backupSay('Ajustes exportados en '+result.name+'.'+omittedNote(result.omitted));
        else if(result?.cancelled)backupSay('Exportación cancelada.');
        else throw new Error(result?.error||'No se pudo exportar');
        return;
      }
      const response=await fetch('/api/overlay/export',{cache:'no-store'});
      if(!response.ok)throw new Error('No se pudo preparar el archivo');
      const text=await response.text();
      let omitted=[];
      try{omitted=JSON.parse(text).omitted||[];}catch(_){}
      const blob=new Blob([text],{type:'application/json'});
      const url=URL.createObjectURL(blob),link=document.createElement('a');
      const day=new Date().toISOString().slice(0,10);
      link.href=url;link.download='overlay-obs-'+day+'.json';
      document.body.append(link);link.click();link.remove();
      setTimeout(()=>URL.revokeObjectURL(url),2000);
      backupSay('Archivo de ajustes descargado.'+omittedNote(omitted));
    }catch(error){backupSay('Exportación: '+error.message,true,control)}
    finally{control.disabled=false}
  };
  $('overlay-import').onchange=async()=>{
    const control=$('overlay-import'),file=control.files?.[0];
    if(!file)return;
    try{
      if(file.size>45_000_000)throw new Error('el archivo supera los 45 MB');
      let bundle;
      try{bundle=JSON.parse(await file.text());}catch(_){throw new Error('el archivo no es un JSON válido');}
      await settleSaves();
      const result=await post('/api/overlay/import',{bundle});
      try{
        const fontRes=await fetch('/api/overlay/fonts');
        if(fontRes.ok)populateFonts(await fontRes.json());
      }catch(_){}
      renderPresets(result.presets);
      await loadReplacedSettings(result.settings);
      backupSay('Ajustes importados desde '+file.name+'.');
    }catch(error){backupSay('Importación: '+error.message,true,control)}
    finally{control.value=''}
  };
  $('upload').onchange=async()=>{
    const file=$('upload').files?.[0];if(!file)return;
    try{
      if(file.size>3_000_000)throw new Error('La fuente supera 3 MB');
      const bytes=await file.arrayBuffer();
      const array=new Uint8Array(bytes);let text='';
      // Convert small user-selected fonts to base64 without external libraries.
      for(let i=0;i<array.length;i+=24000){
        text+=btoa(String.fromCharCode(...array.subarray(i,i+24000)));
      }
      // Each part's length is divisible by 3, so individual btoa chunks concatenate.
      const ext=(file.name.split('.').pop()||'').toLowerCase();
      if(!['ttf','otf','woff','woff2'].includes(ext))throw new Error('Formato de fuente no compatible');
      const rawName=file.name.slice(0,-ext.length-1);
      const stem=(rawName.normalize('NFKD').replace(/[\u0300-\u036f]/g,'')
        .replace(/[^A-Za-z0-9_-]+/g,'_').slice(0,60))||'Fuente';
      const safeName=stem+'.'+ext;
      const fonts=await post('/api/overlay/font',{name:safeName,data:text});
      populateFonts(fonts);
      $('font_file').value=safeName;
      if(await save($('upload')))say('Fuente importada',false,$('upload'));
    }catch(error){say(error.message,true,$('upload'))}
    $('upload').value='';
  };
  function populateFonts(fonts){
    const input=$('font_file'),prior=input.value;input.replaceChildren(new Option('Usar fuente del sistema',''));
    for(const name of fonts)input.add(new Option(name,name));
    if(fonts.includes(prior))input.value=prior;
  }
  async function init(){
    setupLinks();
    try{
      const session=await(await fetch('/api/session')).json();token=session.token;
      const [response,fontRes,shareRes]=await Promise.all([
        fetch('/api/overlay/settings'),fetch('/api/overlay/fonts'),fetch('/api/overlay/share')]);
      if(!response.ok||!fontRes.ok||!shareRes.ok)throw new Error('No se encuentra el editor local');
      const current=await response.json();populateFonts(await fontRes.json());
      await loadSpriteSets(current.sprite_set||'');
      shared=await shareRes.json();
      try{$('share-ip').value=shared.ip||localStorage.getItem('progressive-obs-vpn-ip')||''}catch(_){}
      $('link-target').value=shared.enabled?'vpn':'local';
      displayShare();
      defaultConfig=await(await fetch('/api/overlay/defaults')).json();
      fill(current);say('Listo · los cambios se guardan automáticamente');
      await loadPresets();
      try{publicParty=(await(await fetch('/api/overlay/public')).json()).party||[];sourceDimensions()}catch(_){}
      scheduleHeight();
    }catch(error){say('No se pudo abrir el editor: '+error.message,true)}
  }
  init();
})();
