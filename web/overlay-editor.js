'use strict';
(() => {
  const $=id=>document.getElementById(id), fields=[
    'direction','gap','slot_width','sprite_size','name_size','name_color',
    'name_weight','font','font_file','name_outline','hp_height','hp_radius',
    'hp_background','hp_border','hp_border_width','hp_good','hp_mid','hp_low',
    'hp_low_threshold','hp_mid_threshold','hp_label','hp_text_color','hp_text_size',
    'hp_style','hp_reverse','hp_glow','show_empty',
  ];
  const numberFields=new Set(['gap','slot_width','sprite_size','name_size','name_weight','hp_height',
    'hp_radius','hp_border_width','hp_low_threshold','hp_mid_threshold','hp_text_size']);
  const checkFields=new Set(['hp_reverse','hp_glow','show_empty']);
  const status=$('status');
  let token='',pending=null,defaultConfig=null,loading=true;
  function say(text,problem=false){status.textContent=text;status.dataset.error=String(problem)}
  function setupLinks(){
    const slot=$('slot').value,container=$('links');container.replaceChildren();
    for(const [label,layer] of [['Composición','all'],['Sprites','sprites'],['Motes','names'],['Vida','hp']]){
      const url=location.origin+'/overlay?layer='+layer+(slot?'&slot='+slot:'');
      const row=document.createElement('div');row.className='link-line';
      const title=document.createElement('span');title.textContent=label;
      const input=document.createElement('input');input.readOnly=true;input.value=url;
      const copy=document.createElement('button');copy.textContent='Copiar';
      copy.onclick=async()=>{try{await navigator.clipboard.writeText(url);say('Enlace de '+label+' copiado');}catch(e){input.select();say('Selecciona y copia el enlace')}};
      row.append(title,input,copy);container.append(row);
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
      const input=$(key);if(!input)continue;
      if(checkFields.has(key))input.checked=settings[key];
      else input.value=settings[key];
      const output=document.querySelector('[data-for="'+key+'"]');
      if(output)output.textContent=String(settings[key]);
    }
    $('order').value=settings.order.join(',');
    loading=false;
  }
  async function post(endpoint,payload){
    const response=await fetch(endpoint,{method:'POST',headers:{'X-Tracker-Token':token,
      'Content-Type':'application/json'},body:JSON.stringify(payload)});
    const data=await response.json();
    if(!response.ok)throw new Error(data.error||'No se pudo guardar');
    return data;
  }
  async function save(){
    if(loading)return;
    try{
      const saved=await post('/api/overlay/settings',read());
      say('Personalización guardada');
      document.getElementById('preview').contentWindow?.postMessage({type:'overlay-refresh'},location.origin);
      return saved;
    }catch(error){say(error.message,true)}
  }
  $('save').onclick=save;
  $('reset').onclick=()=>{if(!defaultConfig)return;fill(defaultConfig);save()};
  $('slot').onchange=setupLinks;
  for(const control of [...document.querySelectorAll('.controls input,.controls select'),$('order')]){
    control.addEventListener('input',()=>{
      const output=document.querySelector('[data-for="'+control.id+'"]');
      if(output)output.textContent=control.value;
      if(loading||control.id==='upload')return;
      clearTimeout(pending);pending=setTimeout(save,350);
    });
  }
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
      await save();
    }catch(error){say(error.message,true)}
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
      const [response,fontRes]=await Promise.all([fetch('/api/overlay/settings'),fetch('/api/overlay/fonts')]);
      if(!response.ok||!fontRes.ok)throw new Error('No se encuentra el editor local');
      const current=await response.json();populateFonts(await fontRes.json());
      defaultConfig=await(await fetch('/api/overlay/defaults')).json();
      fill(current);say('Listo · los cambios se guardan automáticamente');
    }catch(error){say('No se pudo abrir el editor: '+error.message,true)}
  }
  init();
})();