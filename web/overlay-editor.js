'use strict';
(() => {
  const $=id=>document.getElementById(id), fields=[
    'direction','gap','slot_width','sprite_size','name_size','name_color',
    'name_weight','font','font_file','name_outline','hp_height','hp_radius',
    'hp_background','hp_border','hp_border_width','hp_good','hp_mid','hp_low',
    'hp_low_threshold','hp_mid_threshold','hp_label','hp_text_color','hp_text_size',
    'hp_style','hp_reverse','hp_glow','show_empty','hp_custom_fill','hp_custom_frame',
  ];
  const numberFields=new Set(['gap','slot_width','sprite_size','name_size','name_weight','hp_height',
    'hp_radius','hp_border_width','hp_low_threshold','hp_mid_threshold','hp_text_size']);
  const checkFields=new Set(['hp_reverse','hp_glow','show_empty','hp_custom_fill','hp_custom_frame']);
  const status=$('status');
  let token='',pending=null,defaultConfig=null,loading=true;
  let shared={enabled:false,ip:'',port:null,base_url:''};
  function say(text,problem=false){status.textContent=text;status.dataset.error=String(problem)}
  function setupLinks(){
    const slot=$('slot').value,container=$('links');container.replaceChildren();
    const remote=$('link-target').value==='vpn'&&shared.enabled;
    const base=remote?shared.base_url:location.origin;
    for(const [label,layer] of [['Composición','all'],['Sprites','sprites'],['Motes','names'],['Vida','hp']]){
      const url=base+'/overlay?layer='+layer+(slot?'&slot='+slot:'');
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
      if(loading||control.type==='file')return;
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
      displayShare();say('Fuente VPN activada · comparte estas URL con tu compañero');
    }catch(error){say('VPN: '+error.message,true)}
  };
  $('share-disable').onclick=async()=>{
    try{
      shared=await post('/api/overlay/share',{enabled:false});
      $('link-target').value='local';
      displayShare();say('Acceso VPN desactivado');
    }catch(error){say('VPN: '+error.message,true)}
  };
  const encodeFile=async(file)=>{
    const bytes=new Uint8Array(await file.arrayBuffer());
    let result='';
    for(let i=0;i<bytes.length;i+=24000){
      result+=btoa(String.fromCharCode(...bytes.subarray(i,i+24000)));
    }
    return result;
  };
  async function importHealth(kind){
    const control=$('hp_'+kind+'_upload');
    const file=control.files?.[0];if(!file)return;
    try{
      if(file.size>2_000_000)throw new Error('El PNG supera los 2 MB');
      if(!file.name.toLowerCase().endsWith('.png'))throw new Error('Selecciona un archivo PNG');
      const info=await post('/api/overlay/hp-image',{kind,data:await encodeFile(file)});
      $('hp_custom_'+kind).checked=true;
      await save();
      say('Imagen de '+(kind==='fill'?'relleno':'marco')+' importada ('+info.width+'×'+info.height+')');
    }catch(error){say('PNG: '+error.message,true)}
    finally{control.value=''}
  }
  $('hp_fill_upload').onchange=()=>importHealth('fill');
  $('hp_frame_upload').onchange=()=>importHealth('frame');
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
      const [response,fontRes,shareRes]=await Promise.all([
        fetch('/api/overlay/settings'),fetch('/api/overlay/fonts'),fetch('/api/overlay/share')]);
      if(!response.ok||!fontRes.ok||!shareRes.ok)throw new Error('No se encuentra el editor local');
      const current=await response.json();populateFonts(await fontRes.json());
      shared=await shareRes.json();
      try{$('share-ip').value=shared.ip||localStorage.getItem('progressive-obs-vpn-ip')||''}catch(_){}
      $('link-target').value=shared.enabled?'vpn':'local';
      displayShare();
      defaultConfig=await(await fetch('/api/overlay/defaults')).json();
      fill(current);say('Listo · los cambios se guardan automáticamente');
    }catch(error){say('No se pudo abrir el editor: '+error.message,true)}
  }
  init();
})();