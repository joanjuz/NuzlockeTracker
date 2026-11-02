'use strict';
// Named runs keep all UI state fresh by reloading after the backend swaps services.
async function profileRequest(payload){
  const response=await fetch('/api/profiles',payload?{method:'POST',headers:{'Content-Type':'application/json','X-Tracker-Token':token},body:JSON.stringify(payload)}:{});
  const result=await response.json();
  if(!response.ok)throw Error(result.error||'No se pudo abrir la partida.');
  return result;
}
async function selectRunProfile(ident){
  const select=$('run-profile'),previous=select.dataset.active;
  select.disabled=true;$('new-run-profile').disabled=true;
  try{
    await profileRequest({action:'select',id:ident});
    window.location.reload();
  }catch(error){
    select.value=previous;
    $('status').textContent=error.message;
    throw error;
  }finally{select.disabled=false;$('new-run-profile').disabled=false;}
}
async function loadRunProfiles(known){
  try{
    const result=known||await profileRequest(),select=$('run-profile');
    select.replaceChildren(...result.profiles.map(profile=>new Option(profile.name,profile.id)));
    select.value=result.active;select.dataset.active=result.active;
    $('run-profile-controls').hidden=false;
    configureProfileDeletion(result);
    select.onchange=()=>selectRunProfile(select.value).catch(()=>{});
    $('new-run-profile').onclick=()=>{
      $('run-profile-feedback').textContent='';
      $('run-profile-name').value='';
      $('run-profile-dialog').showModal();$('run-profile-name').focus();
    };
    $('run-profile-close').onclick=()=>$('run-profile-dialog').close();
    $('run-profile-form').onsubmit=async event=>{
      event.preventDefault();
      const button=$('run-profile-create'),name=$('run-profile-name').value.trim();
      if(!name){$('run-profile-feedback').textContent='Escribe un nombre para la partida.';return;}
      button.disabled=true;$('run-profile-close').disabled=true;
      $('run-profile-feedback').textContent='Creando partida…';
      try{
        const created=await profileRequest({action:'create',name});
        // Keep a newly created run accessible even if switching must be retried.
        await loadRunProfiles();
        await selectRunProfile(created.created);
      }catch(error){$('run-profile-feedback').textContent=error.message;}
      finally{button.disabled=false;$('run-profile-close').disabled=false;}
    };
  }catch(error){$('run-profile-controls').hidden=true;}
}
function configureProfileDeletion(result){
  const open=$('delete-run-profile');if(!open)return;
  open.onclick=()=>{
    const options=result.profiles.map(profile=>{
      const option=new Option(profile.name,profile.id);
      option.disabled=profile.id==='principal'||profile.id===result.active;
      return option;
    });
    const picker=$('delete-run-profile-select');picker.replaceChildren(...options);
    const available=result.profiles.filter(profile=>profile.id!=='principal'&&profile.id!==result.active);
    picker.value=available[0]?.id||'';
    const check=()=>{$('delete-run-profile-confirm').disabled=!available.some(profile=>profile.id===picker.value);};
    picker.onchange=check;check();
    $('delete-run-profile-feedback').textContent=available.length?'':'Abre otra partida para poder eliminar la actual. La partida Principal se conserva.';
    $('delete-run-profile-dialog').showModal();
  };
  $('delete-run-profile-close').onclick=()=>$('delete-run-profile-dialog').close();
  $('delete-run-profile-confirm').onclick=()=>deleteRunProfile($('delete-run-profile-select').value,result);
}
async function deleteRunProfile(ident,result){
  const profile=result.profiles.find(profile=>profile.id===ident),feedback=$('delete-run-profile-feedback');
  if(!profile||ident==='principal'||ident===result.active){feedback.textContent='No se puede eliminar Principal ni la partida abierta. Abre otra partida primero.';return;}
  const button=$('delete-run-profile-confirm');button.disabled=true;$('delete-run-profile-select').disabled=true;$('delete-run-profile-close').disabled=true;
  try{
    const updated=await profileRequest({action:'delete',id:ident});
    await loadRunProfiles(updated);$('delete-run-profile-dialog').close();
    $('status').textContent='Partida «'+profile.name+'» eliminada.';
  }catch(error){feedback.textContent=error.message;}
  finally{button.disabled=false;$('delete-run-profile-select').disabled=false;$('delete-run-profile-close').disabled=false;}
}
// End named run controls.
// Shared helpers (companion.js uses them too). Partner snapshots are untrusted.
const $=id=>document.getElementById(id);
const esc=value=>String(value??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const num=value=>{const n=typeof value==='number'?value:typeof value==='string'&&value.trim()?Number(value):NaN;return Number.isFinite(n)?String(n):'—'};
const list=value=>Array.isArray(value)?value:[];
const GAME_FAMILIES=Object.freeze({'Pokémon X 1.0':'xy','Pokémon Y 1.0':'xy','Omega Ruby 1.0':'oras','Alpha Sapphire 1.0':'oras','Ultra Sun 1.0':'usum','Ultra Moon 1.0':'usum'});
const GEN6_GAMES=Object.freeze(Object.keys(GAME_FAMILIES).filter(game=>GAME_FAMILIES[game]!=='usum'));
const gameFamily=game=>Object.prototype.hasOwnProperty.call(GAME_FAMILIES,game)?GAME_FAMILIES[game]:null;
const spriteId=value=>{const n=Number(value);return Number.isInteger(n)&&n>0?n:0};
// End shared helpers.
async function getJSON(url,options){
  const response=await fetch(url,options);
  if(!response.ok)throw Error('Respuesta '+response.status+' de '+url);
  return response.json();
}
// One delegated fallback for every sprite: local file -> PokeAPI -> number (or Poké Ball).
const SPRITE_REMOTE='https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/';
function spriteFallback(event){
  const img=event.target;
  if(!img||img.tagName!=='IMG'||!img.dataset||img.dataset.fallback===undefined)return;
  const id=Number(img.dataset.fallback);
  if(!img.dataset.remote&&Number.isInteger(id)&&id>0){img.dataset.remote='1';img.src=SPRITE_REMOTE+id+'.png';return;}
  if(img.dataset.fallbackDone)return;
  img.dataset.fallbackDone='1';
  if(img.dataset.fallbackFinal==='ball'){img.src='/app-icon.png';img.classList.add('living-dex-ball');return;}
  img.hidden=true;const next=img.nextElementSibling;if(next)next.hidden=false;
}
document.addEventListener('error',spriteFallback,true);
let routeGame='';
let state=null,localState=null,companionView=false,token=null,selected=null,boxSignature='',socket,miniSignature='',placeSignature='',detailSignature='',routeCatalog=[],detailPokemon=null,moveRequest=0,analysisData=null,analysisSignature='',analysisTeamSignature='',deadSignature='';
const labels=[['ATQ','Ataque'],['DEF','Defensa'],['ATE','At. esp.'],['DEE','Def. esp.'],['VEL','Velocidad']];
// Consume both halves of card activation, even when the dialog moves focus.
const cardActivationKeys=new Set();
function activatePartyCard(event,node){
  if(event.key!=='Enter'&&event.key!==' ')return;
  event.preventDefault();event.stopPropagation();
  if(event.repeat)return;
  cardActivationKeys.add(event.key);node.click();
}
document.addEventListener('keyup',event=>{
  if(!cardActivationKeys.delete(event.key))return;
  event.preventDefault();event.stopPropagation();
},true);
window.addEventListener('blur',()=>cardActivationKeys.clear());
const nodes=Array.from({length:6},(_,i)=>{const node=document.createElement('article');node.className='card empty';node.innerHTML=`<strong>0${i+1}</strong><p>Esperando equipo</p>`;node.tabIndex=0;node.setAttribute('role','button');node.setAttribute('aria-label',`Abrir Pokémon ${i+1}`);node.onclick=()=>openDetail(state?.party[i],`party:${i}`);node.onkeydown=e=>activatePartyCard(e,node);$('party').append(node);return node});
for(let i=1;i<=32;i++)$('box').add(new Option(`Caja ${i}`,i));
function portrait(p){const id=spriteId(p.species_id);return `<div class="portrait"><img src="/sprites/${id}.png" data-fallback="${id}" alt="${esc(p.species)}" loading="lazy"><div class="sprite-fallback" hidden>${num(p.species_id)}</div><div><h2>${esc(p.nickname||p.species)}</h2><p>${esc(p.species)} · ${p.level?`Nivel ${num(p.level)}`:'En caja'}</p></div></div>`}
function card(p,i){if(!p)return `<strong>0${i+1}</strong><p>Sin Pokémon</p>`;const ratio=Number(p.hp)/Number(p.max_hp)*100,hp=Number.isFinite(ratio)?Math.max(0,Math.min(100,ratio)):0;return `<div class="card-top"><span>EQUIPO / 0${i+1}</span><span>${p.hp===0?'DEBILITADO':`NIVEL ${num(p.level)}`}</span></div>${portrait(p)}<div class="hp-label"><span>PS</span><span>${num(p.hp)} / ${num(p.max_hp)}</span></div><div class="hp-track"><span style="width:${hp}%"></span></div><div class="stats">${labels.map(([key,name])=>`<div class="stat"><small>${name}</small><strong>${num(p.stats?.[key])}</strong></div>`).join('')}</div><div class="traits"><div><span>Habilidad</span>${esc(p.ability)}</div><div><span>Objeto</span>${esc(p.item)}</div><div><span>Origen</span>${esc(p.met_location||'Sin lugar registrado')}</div></div><div class="moves">${list(p.move_names).map(m=>`<div class="move">${esc(m)}</div>`).join('')}</div>`}
function openDetail(p,key){if(!p)return;selected=key;detailSignature='';detail(p);if(!$('detail').open)$('detail').showModal()}
function wikidexUrl(name){return 'https://www.wikidex.net/wiki/'+encodeURIComponent(String(name||'').trim().replace(/\s+/g,'_'))}
function wikiPokemonName(p){return Number(p.form)===1&&[20,26,27,28,37,38,50,51,52,53,74,75,76,88,89,103,105].includes(Number(p.species_id))?p.species+' de Alola':p.species}
function detail(p){
detailPokemon=p;
const signature=JSON.stringify(p);
if(signature===detailSignature)return;
detailSignature=signature;
const content=$('detail-content'),active=document.activeElement;
const focusedMove=content.contains(active)?active?.getAttribute('data-move-index'):null;
content.innerHTML=portrait(p)
  +`<p class="subtitle">${esc(p.nature)} · ${esc(p.ability)} · ${esc(p.item)}</p>`
  +detailMoves(p)
  +detailBaseStats(p)
  +detailEvolutions(p)
  +detailOrigin(p)
  +detailTraining(p);
const title=content.querySelector('h2');if(title)title.id='detail-pokemon-title';
if(focusedMove!==null&&$('detail').open){
  const replacement=content.querySelector('[data-move-index="'+focusedMove+'"]');
  if(replacement&&!replacement.disabled)replacement.focus({preventScroll:true});
}
}
// Pieces of the detail dialog. Every snapshot value goes through esc/num/list.
function detailMoves(p){
  const buttons=list(p.move_names).map((m,i)=>
    `<button class="move move-button" data-move-index="${i}" ${list(p.moves)[i]?'':'disabled'}>${esc(m)} <span>↗</span></button>`
  );
  return `<div class="moves">${buttons.join('')}</div>`;
}
function detailBaseStats(p){
  if(!(p.base_stats&&typeof p.base_stats==='object'))return '';
  const cells=Object.entries(p.base_stats).map(([key,val])=>
    `<div><small>${esc(key)}</small><strong>${esc(val)}</strong></div>`
  );
  return '<section class="template-base-stats">'
    +'<h3>Estadísticas base · pk3DS Progressive</h3>'
    +`<div class="template-base-grid">${cells.join('')}</div>`
    +'<p class="subtitle">Los valores actuales de la partida y los IV/EV se muestran por separado.</p>'
    +'</section>';
}
function evolutionOption(e){
  const sourceNote=e.source==='pk3DS Progressive'
    ?'<small class="evolution-modified">Método modificado por pk3DS Progressive</small>'
    :'<small class="reference-note">Referencia de evolución</small>';
  return '<div class="evolution-option">'
    +`<img src="/sprites/${spriteId(e?.sprite_id||e?.target)}.png" data-fallback="${spriteId(e?.sprite_id||e?.target)}" alt="${esc(e?.target_name||'Pokémon '+e?.target)}" loading="lazy">`
    +`<span class="sprite-fallback" hidden>#${num(e?.target)}</span>`
    +'<div>'
    +'<div class="evolution-pokemon-title">'
    +`<strong>${esc(e.target_name||'#'+e.target)}</strong>`
    +`<a class="evolution-wiki" href="${esc(wikidexUrl(e.target_name||'Pokémon '+e.target))}" target="_blank" rel="noopener noreferrer" aria-label="Ver ${esc(e.target_name||'Pokémon '+e.target)} en WikiDex">WikiDex ↗</a>`
    +'</div>'
    +`<p>${esc(e.method)}</p>`
    +sourceNote
    +'</div>'
    +'</div>';
}
function detailEvolutions(p){
  if(!list(p.evolutions).some(e=>e&&typeof e==='object'))return '';
  const options=list(p.evolutions).filter(e=>e&&typeof e==='object').map(e=>evolutionOption(e));
  return '<section class="evolution-info">'
    +'<div class="evolution-heading">'
    +'<h3>Cómo evoluciona</h3>'
    +`<a class="evolution-wiki" href="${esc(wikidexUrl(wikiPokemonName(p)))}" target="_blank" rel="noopener noreferrer" aria-label="Consultar ${esc(wikiPokemonName(p))} en WikiDex">WikiDex ↗</a>`
    +'</div>'
    +options.join('')
    +'</section>';
}
function detailOrigin(p){
  const egg=p.egg_location_id?`<br>Origen del huevo: ${esc(p.egg_location)}`:'';
  return '<div class="origin-info">'
    +'<strong>Lugar registrado</strong>'
    +`<p>${esc(p.met_location||'Sin lugar registrado')}</p>`
    +`<small>Nivel de encuentro: ${p.met_level?num(p.met_level):'—'} · Fecha: ${esc(p.met_date)}${egg}</small>`
    +'</div>';
}
function detailTraining(p){
  // IV/EV arrays use the game order: PS, Ataque, Defensa, Velocidad, At. esp., Def. esp.
  const rows=[['PS',0],['Ataque',1],['Defensa',2],['At. especial',4],['Def. especial',5],['Velocidad',3]].map(([name,i])=>
    `<tr><td>${name}</td><td>${num(list(p.iv)[i])}</td><td>${num(list(p.ev)[i])}</td></tr>`
  );
  return '<h3>Valores individuales y esfuerzo</h3>'
    +'<table class="detail-stats">'
    +'<thead><tr><th>Estadística</th><th>IV</th><th>EV</th></tr></thead>'
    +`<tbody>${rows.join('')}</tbody>`
    +'</table>';
}
function normalize(v){return String(v).normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase()}
function nationalDexLimit(game){return GEN6_GAMES.includes(game)?721:807}
function livingDexEntries(boxes,limit){
  const bySpecies=new Map();
  for(const key of Object.keys(boxes||{}).sort((a,b)=>Number(a)-Number(b))){
    for(const [slot,p] of list(boxes[key]).entries()){
      if(!p||!Number.isInteger(p.species_id)||p.species_id<1||p.species_id>limit)continue;
      const item=bySpecies.get(p.species_id);
      if(item)item.count++;
      else bySpecies.set(p.species_id,{pokemon:p,box:key,slot,count:1});
    }
  }
  return bySpecies;
}
function renderBoxes(){
  if(!state)return;
  const living=$('living-dex').checked;
  const showSprites=living&&$('living-dex-sprites').checked;
  const all=$('global').checked;
  const query=normalize($('search').value).trim().split(/\s+/).filter(Boolean);
  const number=$('box').value;
  const keys=all?Object.keys(state.boxes).sort((a,b)=>a-b):[number];
  const dexLimit=nationalDexLimit(state.game);
  const boxCount=dexLimit===721?31:32;
  // Only the fields this view draws or searches: avoids serialising whole PK6/PK7 records per message.
  const boxView=k=>{const box=state.boxes[k];return [k,Array.isArray(box)?box.length:-1,list(box).map(p=>p?[p.species_id,p.species,p.nickname,p.ability,p.item,
    p.met_location,p.move_names,p.origin_version,p.encryption_constant]:0)]};
  const signature=JSON.stringify([state.game,living,showSprites,companionView,state.stale,state.connection?.status,state.box_verified,
    (living?Object.keys(state.boxes).sort((a,b)=>a-b):keys).map(boxView),query,all,Object.keys(state.progress?.deaths||{})]);
  if(signature===boxSignature)return;
  boxSignature=signature;
  $('boxes').className=living?'box-grid living-dex-grid':'box-grid';
  $('boxes').replaceChildren();
  $('living-dex-status').hidden=!living;
  if(living){
    const complete=state.box_verified===true &&
      Array.from({length:boxCount},(_,i)=>String(i+1)).every(key=>
        Array.isArray(state.boxes[key])&&state.boxes[key].length===30);
    // Protect only live, local scans. Saved/offline and companion snapshots
    // are browseable even if their original box_verified flag is absent.
    const liveLocal=!companionView&&state.connection?.status==='connected'&&!state.stale;
    const hasSavedBoxes=Object.values(state.boxes||{}).some(box=>Array.isArray(box)&&box.length===30);
    if((liveLocal&&!complete)||(!liveLocal&&!hasSavedBoxes)){
      $('living-dex-status').textContent=liveLocal?
        'Living Dex: esperando las '+boxCount+' cajas verificadas.':
        'Living Dex: no hay cajas guardadas para mostrar.';
      const notice=document.createElement('p');
      notice.className='subtitle';
      notice.textContent=liveLocal?
        'Esperando el escaneo automático completo para no marcar como ausentes Pokémon todavía sin leer.':
        'No hay lecturas anteriores de cajas disponibles.';
      $('boxes').append(notice);
      return;
    }
    const entries=livingDexEntries(state.boxes,dexLimit);
    const context=companionView?' · cajas del compañero (último registro)':
      !liveLocal?' · última lectura guardada':'';
    const incomplete=!complete?' · datos parciales, las ausencias son orientativas':'';
    $('living-dex-status').textContent='Living Dex nacional · '+entries.size+' / '+dexLimit+' especies en cajas'+context+incomplete;
    let visible=0;
    for(let id=1;id<=dexLimit;id++){
      const national='#'+String(id).padStart(3,'0');
      const item=entries.get(id);
      const search=normalize([national,id,item?.pokemon?.species||'',item?.pokemon?.nickname||'',
        item?.pokemon?.ability||'',item?.pokemon?.item||''].join(' '));
      if(!query.every(q=>search.includes(q)))continue;
      visible++;
      if(item){
        const b=document.createElement('button');
        b.className='box-pokemon living-dex-owned';
        b.title=(item.pokemon.species||national)+' · '+item.count+' en cajas';
        b.innerHTML=sprite(item.pokemon)+`<strong>${esc(item.pokemon.nickname||item.pokemon.species)}</strong><small>${national}</small>`+
          (item.count>1?`<span class="living-dex-copies" title="${item.count} ejemplares">×${item.count}</span>`:'');
        b.onclick=()=>openDetail(state.boxes[item.box]?.[item.slot]||item.pokemon,`box:${item.box}:${item.slot}`);
        $('boxes').append(b);
      }else{
        const empty=document.createElement('div');
        empty.className='box-pokemon living-dex-missing';
        empty.title=national+(complete?' · no está en las cajas':' · sin registro en las cajas disponibles');
        empty.innerHTML=showSprites?
          `<img class="living-dex-missing-sprite" src="/sprites/${id}.png" data-fallback="${id}" data-fallback-final="ball" alt="" loading="lazy"><small>${national}</small>`:
          `<img class="living-dex-ball" src="/app-icon.png" alt="" loading="lazy"><small>${national}</small>`;
        $('boxes').append(empty);
      }
    }
    if(!visible){
      const p=document.createElement('p');p.className='subtitle';p.textContent='Sin coincidencias en Living Dex.';
      $('boxes').append(p);
    }
    return;
  }
  let found=0;
  for(const key of keys){
    const box=state.boxes[key];if(!box)continue;
    list(box).forEach((p,i)=>{
      if(!p)return;
      const text=normalize([p.species,p.nickname,p.ability,p.item,p.met_location,...list(p.move_names)].join(' '));
      if(!query.every(q=>text.includes(q)))return;
      found++;const b=document.createElement('button');
      b.className='box-pokemon';
      b.innerHTML=`${sprite(p)}<strong>${esc(p.nickname||p.species)}</strong><small>Caja ${esc(key)} · ${i+1}</small>`;
      b.onclick=()=>openDetail(state.boxes[key]?.[i]||p,`box:${key}:${i}`);$('boxes').append(b);
    });
  }
  if(!found){const p=document.createElement('p');p.className='subtitle';
    p.textContent=keys.some(k=>state.boxes[k])?'Sin resultados o caja vacía.':'Caja sin leer.';
    $('boxes').append(p);}
}
function gen7ScanStatus(snapshot){
  const count=Object.keys(snapshot.boxes||{}).length;
  const pending={pending:'Verificando la dirección de las cajas',pending_empty:'PC vacío: dirección pendiente de confirmar; deposita un Pokémon y vuelve a leer',ambiguous:'Se encontraron varias ubicaciones de cajas; vuelve a leer para confirmar',invalid:'No se pudieron validar las cajas; vuelve a leer'};
  const unverified=snapshot.box_verified===false;
  const label=unverified?(pending[snapshot.box_status]||'Dirección de cajas sin validar')+' · ':'';
  const cached=unverified&&count?' · Cajas guardadas: no verificadas en esta conexión':'';
  return label+count+' / 32 cajas leídas'+cached+(snapshot.scan?.active?' · Lectura global: '+snapshot.scan.completed+' / 32':snapshot.stale&&count?' · Última lectura guardada (sin conexión)':'');
}
// Live regions announce only real changes, not every websocket frame.
function setText(node,text){if(node.textContent!==text)node.textContent=text}
function render(next){localState=next;if(!companionView)renderScreen(next)}
function renderScreen(next){
state=next;
$('game-name').textContent=state.game.replace(' 1.0','');
const gen6=GEN6_GAMES.includes(state.game);
const region=gen6?(state.game.startsWith('Pokémon')?'Kalos':'Hoenn'):'Alola';
$('game-region').textContent=region+' · versión 1.0'+(gen6?' (experimental)':'');
$('places-heading').textContent='Rutas de '+region;
$('route-intro').textContent='Sin menús desplegables. Marca «Fósil» junto a «Muerte». '
  +'Los intercambios se identifican con lecturas completas de '+(gen6?'31':'32')
  +' cajas; «Intercambiado» queda bajo MISS en rutas vacías.';
$('analysis-source-note').textContent=gen6?
  'Análisis aproximado con referencias USUM: confirmar habilidades, movimientos y formas en Gen6 antes de usarlo para decisiones.':
  'Referencia USUM · Puede variar con el randomizer.';
$('box').disabled=$('living-dex').checked;
$('global').disabled=$('living-dex').checked;
$('living-dex-sprites').disabled=!$('living-dex').checked;
$('open-companion').disabled=gen6;
const totalBoxes=gen6?31:32;
if($('box').options?.length>=32){
  $('box').options[31].hidden=gen6;$('box').options[31].disabled=gen6;
}
if(gen6&&Number($('box').value)>31)$('box').value='1';
$('game').disabled=Boolean(state.demo)||companionView;
if(routeGame!==state.game){routeGame=state.game;placeSignature='';}
routeCatalog=routeCatalogFor(state.game);
$('eyebrow').textContent=companionView?'AVENTURA DE TU COMPAÑERO':state.demo?'MODO DEMO':'';
$('eyebrow').hidden=!companionView&&!state.demo;
renderMini();
$('dead-count').textContent=Object.keys(state.progress?.deaths||{}).length;
renderActiveView();
$('demo-tools').hidden=!state.demo;
if(state.demo){$('demo-scenario').value=state.demo_scenario;$('box').value=state.selected_box;}
renderConnectionStatus(state);
renderPartyCards(state);
$('scan-status').textContent=gen6?gen6ScanStatus(state):gen7ScanStatus(state);
$('cancel').hidden=companionView||!state.scan.active;
refreshOpenDetail(state);
}
// Header status, live badge and reconnection notice (setText avoids re-announcing).
function renderConnectionStatus(snapshot){
  setText($('status'),String(snapshot.connection.message??'')+(snapshot.persist_warning&&!companionView?' · ⚠ '+String(snapshot.persist_warning):''));
  if(!companionView)showCommandError(snapshot.last_command_error);
  const connected=snapshot.connection.status==='connected'&&!snapshot.stale;
  setText($('badge'),connectionBadgeText(snapshot,connected));
  $('badge').classList.toggle('live',connected);
  $('notice').hidden=companionView||!snapshot.stale;
  setText($('notice'),'Última lectura · Esperando reconexión.');
}
function connectionBadgeText(snapshot,connected){
  if(companionView)return '● Última sesión';
  if(connected)return snapshot.demo?'● Demostración':snapshot.battle_hp?'● PS de combate':'● En vivo';
  if(snapshot.connection.status==='connecting')return 'Localizando RAM';
  if(snapshot.connection.status==='retrying')return 'Reconectando';
  return 'Sin datos actuales';
}
// Party cards repaint only when their Pokémon changes.
function renderPartyCards(snapshot){
  nodes.forEach((node,i)=>{
    const p=snapshot.party[i],sig=JSON.stringify(p);
    node.setAttribute('aria-label',p?'Abrir ficha de '+(p.nickname||p.species):'Espacio '+(i+1)+' vacío');
    node.setAttribute('aria-disabled',String(!p));
    node.tabIndex=p?0:-1;
    if(node.dataset.signature===sig)return;
    node.dataset.signature=sig;
    node.classList.toggle('empty',!p);
    node.innerHTML=card(p,i);
  });
}
function gen6ScanStatus(snapshot){
  return 'Gen6 experimental: '
    +(snapshot.box_verified?'cajas PK6 verificadas':'cajas pendientes de verificación; deposita un Pokémon en el PC y actualiza la lectura')
    +` · ${Object.keys(snapshot.boxes).length} / 31 cajas leídas`
    +(snapshot.scan.active?` · Escaneo: ${snapshot.scan.completed}/31`:'');
}
// Keeps an open detail dialog in sync with the snapshot, or closes it if the Pokémon is gone.
function refreshOpenDetail(snapshot){
  if(!(selected&&$('detail').open))return;
  const [kind,a,b]=selected.split(':');
  const p=kind==='dead'?snapshot.progress?.deaths?.[`${a}:${b}`]?.pokemon:kind==='party'?snapshot.party[a]:snapshot.boxes[a]?.[b];
  if(p)detail(p);
  else $('detail').close();
}
// Route catalogs are cached per game: the partner's snapshot may belong to another region.
const routeCatalogs=new Map(),routeRequests=new Set(),routeFailures=new Map();
function routeCatalogFor(game){
  if(!game)return [];
  if(routeCatalogs.has(game))return routeCatalogs.get(game);
  loadRouteCatalog(game);
  return [];
}
async function loadRouteCatalog(game){
  if(routeRequests.has(game)||Date.now()-(routeFailures.get(game)||0)<5000)return;
  // The plain endpoint keeps serving the local game; other games ask for theirs explicitly.
  const local=game===localState?.game;
  routeRequests.add(game);
  try{
    const data=await getJSON(local?'/api/routes':'/api/routes?game='+encodeURIComponent(game));
    if(local&&localState?.game!==game)return;
    routeCatalogs.set(game,list(data?.routes));routeFailures.delete(game);
    if(state?.game===game){routeCatalog=routeCatalogs.get(game);placeSignature='';if(!$('places-view').hidden)renderPlaces()}
  }catch(error){routeFailures.set(game,Date.now())}
  finally{routeRequests.delete(game)}
}
async function exportWithDialog(kind){
 const button=$(kind==='diagnostic'?'diagnostic':'save-session');
 if(!button||button.disabled)return;
 const label=button.textContent;
 button.disabled=true;
 try{
   if(!window.pywebview?.api?.save_export)
     throw Error('El selector de archivos requiere abrir Pokémon Tracker desde su ejecutable de Windows.');
   const result=await window.pywebview.api.save_export(kind);
   if(result?.error)throw Error(result.error);
   if(result?.saved)showExportFeedback('Archivo guardado: '+result.name);
 }catch(error){showExportFeedback('No se pudo guardar: '+error.message);}
 finally{button.disabled=false;}
}
// A queued command (for example «Marcar muerto» twice) can be rejected by the
// worker after the HTTP request already returned 202: show it for a while.
let shownCommandError=null,commandErrorTimer=null;
function showCommandError(failed){
 if(!failed||typeof failed.message!=='string'||failed.at===shownCommandError)return;
 shownCommandError=failed.at;
 if(Date.now()/1000-Number(failed.at)>15)return;
 showExportFeedback('No se pudo completar: '+failed.message);
 clearTimeout(commandErrorTimer);
 commandErrorTimer=setTimeout(()=>{const note=$('export-feedback');if(note)note.hidden=true;},8000);
}
function showExportFeedback(message){
 const note=$('export-feedback');
 if(note){note.textContent=message;note.hidden=false;}
}
async function command(cmd){try{if(companionView)throw Error('La sesión del compañero es de solo lectura.');if(!token)throw Error('El servidor local aún no está disponible.');const response=await fetch('/api/command',{method:'POST',headers:{'Content-Type':'application/json','X-Tracker-Token':token},body:JSON.stringify(cmd)});const result=await response.json();if(!response.ok)throw Error(result.error||'No se pudo realizar la acción.')}catch(e){$('status').textContent=e.message}}
function subscribe(){socket=new WebSocket(`ws://${location.host}/ws`);socket.onmessage=e=>{try{render(JSON.parse(e.data))}catch(error){console.error(error)}};socket.onclose=()=>{$('badge').textContent='Servidor local desconectado';$('badge').classList.remove('live');$('notice').hidden=false;$('notice').textContent='Mantén abierta la ventana del servidor. Intentando reconectar…';setTimeout(start,2000)};socket.onerror=()=>socket.close()}
async function start(){try{const session=await getJSON('/api/session');token=session.token;if(typeof session.version==='string'&&/^\d+\.\d+\.\d+$/.test(session.version))setText($('app-version'),'Progressive '+session.version);await loadRunProfiles();document.title='Pokémon Tracker';const saved=session.saved_connection;if(saved){$('game').value=saved.game;$('mode').value=saved.mode;$('pid').value=saved.pid??'';$('port').value=saved.port??24689;$('port-label').hidden=saved.mode!=='gdb';$('saved-session-status').textContent='Sesión guardada · '+saved.game+' · conexión automática al iniciar'+(saved.pid?' · PID '+saved.pid:'');}analysisData=await getJSON('/api/analysis');render(await getJSON('/api/state'));subscribe()}catch(e){$('status').textContent='Esperando al servidor local…';setTimeout(start,2000)}}
$('connect').onclick=()=>command({action:'connect',game:$('game').value,mode:$('mode').value,pid:$('pid').value?Number($('pid').value):null,port:Number($('port').value)});$('disconnect').onclick=()=>command({action:'disconnect'});$('save-session').onclick=()=>exportWithDialog('session');$('mode').onchange=()=>{$('port-label').hidden=$('mode').value!=='gdb'};$('box').onchange=()=>{renderBoxes();command({action:'box',number:Number($('box').value)})};$('search').oninput=renderBoxes;$('global').onchange=renderBoxes;$('living-dex').onchange=()=>{$('box').disabled=$('living-dex').checked;$('global').disabled=$('living-dex').checked;$('living-dex-sprites').disabled=!$('living-dex').checked;boxSignature='';renderBoxes()};$('living-dex-sprites').onchange=()=>{boxSignature='';renderBoxes()};$('cancel').onclick=()=>command({action:'cancel'});$('close-detail').onclick=()=>$('detail').close();$('diagnostic').onclick=()=>exportWithDialog('diagnostic');
const filesToImport=[['moves','template-moves'],['stats','template-stats'],['evolutions','template-evolutions']];
async function templateStatus(){try{const r=await fetch('/api/templates');const j=await r.json();if(r.ok)$('template-status').textContent=`Plantillas guardadas: ${j.counts.moves} movimientos · ${j.counts.stats} especies · ${j.counts.evolutions} especies con evoluciones modificadas.`;}catch(e){$('template-status').textContent=e.message}}
$('import-templates').onclick=async()=>{const button=$('import-templates');button.disabled=true;try{const files={};for(const [key,id] of filesToImport){const file=$(id).files?.[0];if(file){if(file.size>180000)throw Error('Plantilla demasiado grande: '+file.name);files[key]=await file.text();}}if(!Object.keys(files).length)throw Error('Selecciona al menos un archivo CSV.');const r=await fetch('/api/templates',{method:'POST',headers:{'Content-Type':'application/json','X-Tracker-Token':token},body:JSON.stringify({files})});const j=await r.json();if(!r.ok)throw Error(j.error||'No se pudo importar');$('template-status').textContent='Plantillas importadas y guardadas. Los datos de equipo y cajas se actualizarán.';for(const [,id] of filesToImport)$(id).value='';await templateStatus()}catch(e){$('template-status').textContent='Error: '+e.message}finally{button.disabled=false}};
templateStatus();
const views={dead:['Muertos',''],party:['Equipo actual',''],boxes:['Tus cajas',''],places:['Rutas',''],analysis:['Análisis del equipo',''],overlay:['Diseñar overlay para OBS',''],connection:['Conexión','']};
function switchTab(tab){if(companionView&&tab==='connection'){return;}if(tab==='overlay'){const frame=$('overlay-editor-frame');if(!frame.src)frame.src=frame.dataset.src;} document.querySelectorAll('nav button').forEach(b=>{const active=b.dataset.tab===tab;b.classList.toggle('active',active);if(active)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current')});for(const key of Object.keys(views))$(key+'-view').hidden=key!==tab;$('title').textContent=views[tab][0];$('subtitle').textContent=views[tab][1];$('subtitle').hidden=!views[tab][1];renderActiveView();if(tab==='connection')refreshProcesses();}
function renderActiveView(){
  if(!state)return;
  if(!$('boxes-view').hidden)renderBoxes();
  if(!$('places-view').hidden)renderPlaces();
  if(!$('dead-view').hidden)renderDead();
  if(!$('analysis-view').hidden)renderAnalysis();
}

// The editor reports its natural content height; only this iframe may resize it.
function resizeOverlayEditor(event){
  const frame=$('overlay-editor-frame'),data=event.data;
  if(event.origin!==location.origin||event.source!==frame.contentWindow||!data||data.type!=='tracker-overlay-resize')return;
  if(typeof data.height!=='number'||!Number.isFinite(data.height)||data.height<1||data.height>20000)return;
  frame.style.height=Math.max(240,Math.ceil(data.height))+'px';
  frame.style.minHeight='0';frame.setAttribute('scrolling','no');
}
window.addEventListener('message',resizeOverlayEditor);

function updateNavigationOverflow(){
  const nav=$('section-nav');if(!nav)return;
  const overflow=nav.scrollWidth>nav.clientWidth+1;
  $('nav-scroll-back').hidden=$('nav-scroll-forward').hidden=!overflow;
  $('nav-scroll-back').disabled=nav.scrollLeft<=1;
  $('nav-scroll-forward').disabled=nav.scrollLeft+nav.clientWidth>=nav.scrollWidth-1;
}
for(const [id,step] of [['nav-scroll-back',-1],['nav-scroll-forward',1]]){
  const button=$(id);if(button)button.onclick=()=>{$('section-nav').scrollBy({left:step*180,behavior:'auto'});};
}
if($('section-nav')){
  $('section-nav').addEventListener('scroll',updateNavigationOverflow);
  if(typeof ResizeObserver!=='undefined')new ResizeObserver(updateNavigationOverflow).observe($('section-nav'));
  window.addEventListener('resize',updateNavigationOverflow);updateNavigationOverflow();
}

// Process discovery only suggests candidates; it never silently changes a PID.
let processCandidates=[],processRequest=0;
function showProcessCandidates(){
  const picker=$('process-picker');if(!picker)return;
  const selectedGame=$('game').value;
  picker.replaceChildren(new Option('Elegir un emulador abierto…',''));
  const ranked=[...processCandidates].sort((a,b)=>Number(b.game===selectedGame)-Number(a.game===selectedGame));
  for(const item of ranked){
    const mismatch=Boolean(item.game&&item.game!==selectedGame);
    const label=[item.pid,item.name,item.title||item.game||'Juego sin identificar'].filter(Boolean).join(' · ');
    const option=new Option(label,String(item.pid));option.disabled=mismatch;option.title=label+(mismatch?' · Selecciona su juego para usarlo.':'');picker.add(option);
  }
  picker.value='';
}
async function refreshProcesses(){
  const picker=$('process-picker'),button=$('refresh-processes');if(!picker||!button)return;
  const request=++processRequest;button.disabled=true;
  $('process-status').textContent='Buscando emuladores abiertos…';
  try{
    const response=await fetch('/api/processes',{cache:'no-store'}),result=await response.json();
    if(request!==processRequest)return;
    if(!response.ok||result.error)throw Error(result.error||'No se pudieron consultar los emuladores.');
    processCandidates=(result.processes||[]).filter(item=>Number.isInteger(item.pid)&&item.pid>0);
    showProcessCandidates();
    $('process-status').textContent=processCandidates.length?'Elige la ventana de tu partida; también puedes escribir el PID.':'No hay emuladores detectados. Puedes escribir el PID manualmente.';
  }catch(error){if(request===processRequest){processCandidates=[];showProcessCandidates();$('process-status').textContent=error.message+' Puedes escribir el PID manualmente.';}}
  finally{if(request===processRequest)button.disabled=false;}
}
if($('refresh-processes'))$('refresh-processes').onclick=refreshProcesses;
if($('process-picker'))$('process-picker').onchange=()=>{
  const item=processCandidates.find(item=>String(item.pid)===$('process-picker').value);
  if(!item||(item.game&&item.game!==$('game').value))return;
  $('pid').value=String(item.pid);$('process-status').textContent='Seleccionado PID '+item.pid+' · '+(item.title||item.name)+'.';
};
$('game').onchange=showProcessCandidates;

document.querySelectorAll('nav button').forEach(button=>button.onclick=()=>switchTab(button.dataset.tab));$('quick-connect').onclick=()=>switchTab('connection');
function setCompanionView(enabled,remote){
  if(companionView&&enabled){renderScreen(remote);return;}
  companionView=Boolean(enabled);$('quick-connect').hidden=companionView;$('quick-connect').disabled=companionView;selected=null;for(const id of ['detail','move-detail'])if($(id).open)$(id).close();
  miniSignature='';boxSignature='';placeSignature='';deadSignature='';analysisSignature='';analysisTeamSignature='';detailSignature='';
  $('box').value='1';
  document.querySelector('nav button[data-tab="connection"]').disabled=companionView;
  renderScreen(companionView?remote:localState);
  if(companionView&&document.querySelector('nav button.active')?.dataset.tab==='connection')switchTab('party');
}
window.setCompanionView=setCompanionView;
function renderMini(){
  if($('death-counter-value'))$('death-counter-value').textContent=String(state.progress?.death_count??Object.keys(state.progress?.deaths||{}).length);
  const signature=JSON.stringify(state.party.map(p=>p?[p.species_id,p.nickname,p.hp===0]:null));
  $('party-count').textContent=state.party.filter(Boolean).length;
  $('box-count').textContent=Object.keys(state.boxes).length;
  if(signature===miniSignature)return;
  miniSignature=signature;
  $('mini-team').replaceChildren();
  state.party.forEach((p,i)=>$('mini-team').append(miniTeamButton(p,i)));
}
// Top-bar button for one party slot; it opens the same detail as the large card.
function miniTeamButton(p,i){
  const b=document.createElement('button');
  b.title=p?`${p.nickname||p.species} · ${p.species}`:`Espacio ${i+1} vacío`;
  if(!p)b.setAttribute('aria-label','Espacio vacío');
  b.className=p?.hp===0?'fainted':'';
  b.innerHTML=p
    ?`<img src="/sprites/${spriteId(p.species_id)}.png" data-fallback="${spriteId(p.species_id)}" alt="${esc(p.species)}" loading="lazy"><span hidden>${i+1}</span>`
    :`<span aria-hidden="true">·</span>`;
  b.onclick=()=>{switchTab('party');if(p)openDetail(state.party[i],`party:${i}`)};
  return b;
}
function pokemonKey(p){return `${p.origin_version??33}:${p.encryption_constant}`}
function isDead(p){return Boolean(state?.progress?.deaths?.[pokemonKey(p)])}
function renderDead(){
 const deaths=state.progress?.deaths||{},signature=JSON.stringify(deaths);
 $('dead-count').textContent=Object.keys(deaths).length;
 if(signature===deadSignature)return;deadSignature=signature;$('dead').replaceChildren();
 for(const [key,record] of Object.entries(deaths)){
  const p=record?.pokemon;if(!p||typeof p!=='object')continue;
  const entry=document.createElement('article'),detailButton=document.createElement('button'),reviveButton=document.createElement('button');
  entry.className='dead-entry';detailButton.className='box-pokemon';
  detailButton.innerHTML=`${sprite(p)}<strong>${esc(p.nickname||p.species)}</strong><small>${esc(p.met_location||'Origen desconocido')}</small>`;
  detailButton.onclick=()=>openDetail(p,`dead:${key}`);
  reviveButton.className='revive-button';reviveButton.textContent='Revivir';reviveButton.setAttribute('aria-label',`Revivir a ${p.nickname||p.species}`);
  reviveButton.title='Quitar de Muertos. No cambia los PS del juego.';
  reviveButton.disabled=typeof companionView!=='undefined'&&companionView;reviveButton.onclick=async()=>{reviveButton.disabled=true;try{const lower=confirm('¿Quieres reducir también el contador de muertes en 1?');await command({action:'revive',key,decrement_counter:lower})}finally{reviveButton.disabled=false}};
  entry.append(detailButton,reviveButton);$('dead').append(entry);
 }
 if(!Object.keys(deaths).length)$('dead').innerHTML='<p class="subtitle">Sin muertes registradas.</p>';
}
function sprite(p){return `<div class="route-sprite ${isDead(p)?'dead-sprite':''}" title="${isDead(p)?'Muerto · ':''}${esc(p.nickname||p.species)} · ${esc(p.species)}"><img src="/sprites/${spriteId(p.species_id)}.png" data-fallback="${spriteId(p.species_id)}" alt="${esc(p.species)}" loading="lazy"><span class="sprite-number" hidden>#${num(p.species_id)}</span></div>`}

const ORIGIN_TYPES={
  route:'Ruta',fossil:'Fósil',gift:'Regalo',egg:'Huevo',trade:'Intercambio'
};
const catalogIds=new WeakMap();let catalogSequence=0;
function catalogIdentity(catalog){
  if(!catalog||typeof catalog!=='object')return 0;
  if(!catalogIds.has(catalog))catalogIds.set(catalog,++catalogSequence);
  return catalogIds.get(catalog);
}
function originCategory(p){
  const category=state.progress?.origins?.[pokemonKey(p)];
  if(Object.prototype.hasOwnProperty.call(ORIGIN_TYPES,category))return category;
  // El lugar donde se recibió el huevo permanece tras eclosionar.
  // No inferimos fósiles ni regalos por la especie o la ruta.
  return p.egg===true||(Number.isInteger(p.egg_location_id)&&p.egg_location_id>0)?'egg':'route';
}

function routePokemon(p, historical=false){
  const key=pokemonKey(p),dead=isDead(p),marked=state.progress?.route_marks?.[key];
  const valid=(historical||p.checksum_valid===true)&&Number.isInteger(p.encryption_constant);
  const category=originCategory(p);
  const actions=[];
  if(dead&&!marked)actions.push('<small class="route-death-status">Muerto</small>');
  if(marked){
    actions.push(`<small class="route-marked" title="Esta ruta conserva el historial">${marked.kind==='trade'?'Intercambiado':'Fósil'}</small>`);
    if(!companionView)actions.push(`<button class="route-death" type="button" data-route-undo="${esc(key)}">Deshacer</button>`);
  }else if(!companionView&&valid){
    if(!dead&&!historical&&!p.egg)actions.push(`<button class="route-death" type="button" data-route-death="${esc(key)}">Muerte</button>`);
    if(historical)actions.push('<small class="route-not-found">Ya no está en las lecturas</small>');
    if(category==='route'||category==='fossil')
      actions.push(`<button class="route-death" type="button" data-route-mark="${esc(key)}" data-kind="fossil" title="Clasificar este Pokémon como fósil sin perder la ruta">Fósil</button>`);
  }else if(historical&&!marked)actions.push('<small class="route-not-found">Ya no está en las lecturas</small>');
  else if(dead)actions.push('<small class="route-death-status">Muerto</small>');
  else if(companionView)actions.push('<small class="route-death-status">Solo lectura</small>');
  // El origen se reconoce por la sección/estado: evita etiquetas repetidas
  // debajo de Deshacer y deja visibles solamente sprites y acciones.
  return `<div class="route-pokemon-entry ${historical?'route-historical':''}">
    ${sprite(p)}${actions.join('')}</div>`;
}
function routeFootprint(p,kind){
  const key=pokemonKey(p),name=p.nickname||p.species||('Pokémon #'+p.species_id);
  return `<div class="route-footprint" title="${esc(name)} · origen registrado: ${esc(p.met_location||'Desconocido')}">
    <span class="route-footprint-symbol">${kind==='trade'?'↔':'◆'}</span>
    <small>${kind==='trade'?'Intercambiado':'Fósil'}</small>
    ${!companionView?`<button class="route-death" data-route-undo="${esc(key)}" type="button">Deshacer</button>`:''}
  </div>`;
}
function renderPlaces(){
  if(!state)return;
  const query=normalize($('route-search').value||'').trim();
  const family=gameFamily(state.game);
  const versions=family==='xy'?[24,25]:family==='oras'?[26,27]:[30,31,32,33];
  const entries=[...state.party,...Object.values(state.boxes||{}).flat(),
    ...Object.values(state.progress?.deaths||{}).map(d=>d?.pokemon)];
  const active=new Map();
  for(const p of entries){
    if(!p)continue;
    const key=pokemonKey(p);
    if(!active.has(key))active.set(key,p);
  }
  const history=state.progress?.encounters||{};
  const tradedRoutes=state.progress?.traded_routes||[];
  const marks=state.progress?.route_marks||{};
  const locations=new Map(),special=new Map();
  const addLocation=(p,type,kind)=>{const key=`${p.origin_version}:${p.met_location_id}`;
    if(!locations.has(key))locations.set(key,[]);
    locations.get(key).push({p,type,kind});
  };
  const addSpecial=(p,kind,historical)=>{if(!special.has(kind))special.set(kind,[]);
    special.get(kind).push({p,historical});
  };
  const keys=new Set([...Object.keys(history),...active.keys(),...Object.keys(marks)]);
  for(const key of keys){
    const p=active.get(key)||history[key]||marks[key]?.pokemon;
    if(!p)continue;
    const marked=marks[key];
    if(marked?.kind==='trade'){
      addLocation(marked.pokemon||p,'mark','trade');
      continue;
    }
    const category=originCategory(p);
    const historical=!active.has(key);
    if(category==='fossil'||marked?.kind==='fossil'){
      addSpecial(p,'fossil',historical);
      addLocation(p,'mark','fossil');
    }else if(category!=='route'){
      addSpecial(p,category,historical);
    }else{
      addLocation(p,'pokemon',historical?'historical':'active');
    }
  }
  // Catalog by identity and Pokémon by the fields routes draw; no full-record serialisation.
  const progress=state.progress||{},routeView=p=>p&&typeof p==='object'?[pokemonKey(p),p.species_id,p.species,p.nickname,
    p.met_location,p.met_location_id,p.egg_location_id,p.origin_version,p.egg,p.checksum_valid]:0;
  const signature=JSON.stringify([state.game,catalogIdentity(routeCatalog),query,companionView,
    Object.keys(progress.deaths||{}),progress.origins,progress.traded_routes,progress.missed_routes,
    Object.entries(progress.route_marks||{}).map(([key,mark])=>[key,mark?.kind,routeView(mark?.pokemon)]),
    Object.entries(progress.encounters||{}).map(([key,p])=>[key,routeView(p)]),
    [...active.values()].map(routeView)]);
  if(signature===placeSignature)return;
  placeSignature=signature;
  $('places').replaceChildren();
  let filled=0;
  for(const r of routeCatalog)
    if(tradedRoutes.includes(String(r.id))||versions.some(v=>(r.ids||[r.id]).some(id=>locations.has(`${v}:${id}`))))filled++;
  $('places-count').textContent=routeCatalog.length?`${filled} / ${routeCatalog.length} zonas con historial`:`${locations.size} lugares registrados · catálogo pendiente`;
  const routes=routeCatalog.filter(r=>normalize(r.name).includes(query));
  if(routes.length){
    const section=document.createElement('section');section.className='route-section';
    section.innerHTML=`<div class="route-grid">${routes.map(r=>{
      const list=versions.flatMap(v=>(r.ids||[r.id]).flatMap(id=>locations.get(`${v}:${id}`)||[]));
      const missed=(state.progress?.missed_routes||[]).includes(String(r.id));
      const traded=tradedRoutes.includes(String(r.id));
      const routeVacant=!list.some(item=>item.type==='mark'||(item.type==='pokemon'&&item.kind==='active'));
      const note=r.manual_only?'El juego comparte esta ubicación con otra zona; la asignación puede ser ambigua.':'';
      return `<fieldset class="route-tile ${list.length?'occupied':'unfilled'}" title="${esc(note)}">
       <legend class="route-legend">${esc(r.name)}</legend>
       <div class="route-sprites">${list.length?list.map(({p,type,kind})=>type==='mark'?routeFootprint(p,kind):routePokemon(p,kind==='historical')).join(''):
          traded?'<span class="trade-route-symbol" aria-label="Ruta intercambiada">↔</span>':
          missed?'<span class="miss-mark" aria-label="Encuentro perdido">MISS</span>':
          '<img class="empty-sprite" src="/empty-pokemon.svg" alt="Sin Pokémon registrado">'}</div>
       <div class="route-actions"><button class="miss-toggle" data-route-miss="${esc(r.id)}" ${companionView?'disabled':''}
         aria-pressed="${missed}" aria-label="${missed?'Quitar Miss de':'Marcar Miss en'} ${esc(r.name)}">${missed?'↶ Quitar Miss':'Marcar Miss'}</button>
       ${routeVacant?`<button class="miss-toggle route-trade-toggle" type="button"
         data-route-trade="${esc(r.id)}" ${companionView?'disabled':''}
         aria-pressed="${traded}">${traded?'↶ Quitar intercambio':'Intercambiado'}</button>`:''}
       ${traded?'<small class="route-marked">↔ Intercambiado</small>':''}
       ${missed&&list.length?'<small class="miss-label">MISS</small>':''}
       </div>
      </fieldset>`;
    }).join('')}</div>`;
    $('places').append(section);
  }
  const headings={fossil:'Fósiles',gift:'Regalos',egg:'Huevos',trade:'Intercambios recibidos'};
  for(const [kind,title] of Object.entries(headings)){
    const matching=(special.get(kind)||[]).filter(({p})=>[p.nickname,p.species,p.met_location]
      .some(s=>normalize(s||'').includes(query))||normalize(title).includes(query));
    if(!matching.length)continue;
    const section=document.createElement('section');section.className='route-section origin-section';section.dataset.origin=kind;
    // Fósiles, regalos, etc.: una tarjeta por lugar, con sus sprites juntos.
    const groups=new Map();
    for(const item of matching){
      const p=item.p;
      const key=`${p.origin_version}:${p.met_location_id}`;
      if(!groups.has(key))groups.set(key,[]);
      groups.get(key).push(item);
    }
    section.innerHTML=`<h3>${title} <span class="origin-count">${matching.length}</span></h3>
      <div class="route-grid">${[...groups.values()].map(group=>`<fieldset class="route-tile occupied">
      <legend class="route-legend">${esc(group[0].p.met_location||'Lugar desconocido')}</legend>
      <div class="route-sprites">${group.map(({p,historical})=>routePokemon(p,historical)).join('')}</div>
      </fieldset>`).join('')}</div>`;
    $('places').append(section);
  }
  const extras=[...locations.values()].filter(items=>
    !versions.includes(items[0].p.origin_version) ||
    !routeCatalog.some(r=>(r.ids||[r.id]).includes(items[0].p.met_location_id)));
  const visible=extras.filter(items=>normalize(items[0].p.met_location||'').includes(query));
  if(visible.length){
    const section=document.createElement('section');section.className='route-section';
    section.innerHTML=`<h3>Otros orígenes registrados</h3><div class="route-grid">
      ${visible.map(items=>`<fieldset class="route-tile occupied">
        <legend class="route-legend">${esc(items[0].p.met_location||'Origen desconocido')}</legend>
        <div class="route-sprites">${items.map(({p,type,kind})=>type==='mark'?routeFootprint(p,kind):routePokemon(p,kind==='historical')).join('')}</div>
      </fieldset>`).join('')}</div>`;
    $('places').append(section);
  }
  if(!$('places').children.length)$('places').innerHTML='<p class="subtitle">Sin rutas coincidentes.</p>';
}
$('route-search').oninput=renderPlaces;
$('places').addEventListener('click',event=>{
  if(companionView)return;
  const routeTrade=event.target.closest('[data-route-trade]');
  if(routeTrade){
    command({action:'route_trade',route:routeTrade.dataset.routeTrade,
      traded:routeTrade.getAttribute('aria-pressed')!=='true'});
    return;
  }
  const marker=event.target.closest('[data-route-mark]');
  if(marker){
    command({action:'mark_route',key:marker.dataset.routeMark,kind:marker.dataset.kind});
    return;
  }
  const undo=event.target.closest('[data-route-undo]');
  if(undo){
    command({action:'clear_route_mark',key:undo.dataset.routeUndo});
    return;
  }
  const death=event.target.closest('[data-route-death]');
  if(death){
    const key=death.dataset.routeDeath;
    const candidates=[...state.party,...Object.values(state.boxes).flat()];
    const pokemon=candidates.find(p=>p&&pokemonKey(p)===key);
    if(!pokemon||isDead(pokemon))return;
    command({action:'mark_dead',key});
    return;
  }
  const button=event.target.closest('[data-route-miss]');
  if(button)command({action:'route_miss',route:button.dataset.routeMiss,missed:button.getAttribute('aria-pressed')!=='true'});
});
$('detail-content').addEventListener('click',event=>{const button=event.target.closest('[data-move-index]');if(button&&detailPokemon)openMove(detailPokemon,Number(button.dataset.moveIndex))});
async function openMove(p,index){
  const id=Number(list(p.moves)[index]);
  if(!Number.isInteger(id)||id<1)return;
  const request=++moveRequest;
  $('move-content').innerHTML='<h2 id="move-title">Movimiento</h2><p class="subtitle">Cargando ficha…</p>';
  if(!$('move-detail').open)$('move-detail').showModal();
  try{
    const response=await fetch(`/api/move/${id}`);
    const m=await response.json();
    if(!response.ok)throw Error(m.error||'No se pudo cargar el movimiento.');
    if(request!==moveRequest)return;
    $('move-content').innerHTML=moveSheet(m,id,list(p.move_pp)[index],list(p.move_pp_ups)[index]);
  }catch(e){
    if(request===moveRequest)$('move-content').innerHTML=`<h2 id="move-title">Movimiento</h2><p>${esc(e.message)}</p>`;
  }
}
// Move dialog body: reference data from /api/move plus the live PP of this Pokémon.
function moveSheet(m,id,current,ups){
  const maximum=Number.isInteger(ups)&&ups>=0&&ups<=3?Math.floor(m.pp*(5+ups)/5):null;
  const typeClass=normalize(m.type).replace(/[^a-z]/g,'');
  const power=m.power!=null?num(m.power):(m.category==='Estado'?'—':'Variable');
  const livePp=current!=null
    ?`<p class="live-pp">PP actuales: <strong>${num(current)}</strong>${maximum!=null?` · Máximo: ${num(maximum)}`:''}</p>`
    :'';
  const notes=esc(m.source)
    +(m.rom_override?'':' · Puede variar con el randomizer.')
    +(m.template_notes?` · ${esc(m.template_notes)}`:'')
    +(m.battle_patch?' · Efecto especial requiere parche validado en la ROM.':'');
  return `<p class="eyebrow">MOVIMIENTO / ${num(id)}</p>`
    +`<h2 id="move-title">${esc(m.name)}</h2>`
    +`<div class="move-tags"><span class="type-tag type-${typeClass}">${esc(m.type)}</span><span>${esc(m.category)}</span></div>`
    +'<div class="move-facts">'
    +`<div><small>Potencia</small><strong>${power}</strong></div>`
    +`<div><small>Precisión</small><strong>${m.accuracy==null?'—':num(m.accuracy)+'%'}</strong></div>`
    +`<div><small>PP base</small><strong>${num(m.pp)}</strong></div>`
    +`<div><small>Prioridad</small><strong>${m.priority>0?'+':''}${num(m.priority)}</strong></div>`
    +'</div>'
    +livePp
    +`<p class="move-description">${esc(m.description)}</p>`
    +`<p class="reference-note">${notes}</p>`
    +`<a class="wiki-link" href="${esc(m.wikidex_url)}" target="_blank" rel="noopener noreferrer">WikiDex ↗</a>`;
}
$('close-move').onclick=()=>{moveRequest++;$('move-detail').close()};$('move-detail').addEventListener('close',()=>moveRequest++);
$('demo-scenario').onchange=()=>command({action:'demo',scenario:$('demo-scenario').value});
$('theme').value=document.documentElement.dataset.theme||'dark';$('theme').onchange=()=>{document.documentElement.dataset.theme=$('theme').value;try{localStorage.setItem('progressive-theme',$('theme').value)}catch(e){}};
let compact=false;try{compact=localStorage.getItem('progressive-density')==='compact'}catch(e){}function density(){document.body.classList.toggle('compact',compact);$('density').textContent=compact?'Vista amplia':'Vista compacta'}density();$('density').onclick=()=>{compact=!compact;try{localStorage.setItem('progressive-density',compact?'compact':'comfortable')}catch(e){}density()};start();

// Dismiss native dialogs on backdrop click; clicks inside their bounds stay open.
for(const id of ['detail','move-detail'])$(id).addEventListener('click',event=>{if(event.target!==$(id))return;const r=$(id).getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)$(id).close()});
document.addEventListener('pointerdown',event=>{document.querySelectorAll('details[open]').forEach(menu=>{if(!menu.contains(event.target))menu.open=false})});
document.addEventListener('keydown',event=>{if(event.key==='Escape')document.querySelectorAll('details[open]').forEach(menu=>menu.open=false)});
function multiplier(value){return value===null?'—':`${Number(value.toFixed(3))}×`}
function cellClass(value){return value===0?'immune':value>1?'weak':value<1?'resist':'neutral'}
function renderAnalysis(){
  if(!state||!analysisData)return;
  const team=state.party.filter(Boolean);
  syncAnalysisSelectors(team);
  const simple=$('analysis-defense').value==='simple';
  const mode=$('analysis-mode').value,abilities=$('analysis-abilities').checked,dual=$('analysis-dual').checked,a=$('analysis-a').value,b=$('analysis-b').value;
  $('analysis-defense-label').hidden=mode!=='defense';
  $('analysis-a-label').hidden=mode==='defense';
  $('analysis-b-label').hidden=mode!=='double';
  $('analysis-dual-label').hidden=mode==='defense';
  const signature=JSON.stringify([team.map(p=>[p.types,p.ability_id,p.analysis_moves,p.slot,p.nickname]),mode,a,b,abilities,dual,simple]);
  if(signature===analysisSignature)return;
  analysisSignature=signature;
  const content=$('analysis-content');
  if(!team.length){content.innerHTML='<p class="subtitle">Sin Pokémon en el equipo.</p>';return}
  const types=analysisData.types,chart=analysisData.chart;
  if(mode==='defense'){content.innerHTML=defenseTable(team,types,chart,abilities,simple);return}
  const chosen=team.filter(p=>String(p.slot)===a||(mode==='double'&&String(p.slot)===b));
  if(mode==='double'&&(chosen.length<2||a===b)){content.innerHTML='<p class="subtitle">Selecciona dos Pokémon diferentes del equipo.</p>';return}
  content.innerHTML=coverageReport(chosen,types,chart,abilities,dual);
}
// Rebuilds the Pokémon pickers only when the team changes, keeping the current choice.
function syncAnalysisSelectors(team){
  const teamSig=JSON.stringify(team.map(p=>[p.slot,p.nickname,p.species]));
  if(teamSig===analysisTeamSignature)return;
  analysisTeamSignature=teamSig;
  for(const id of ['analysis-a','analysis-b']){
    const before=$(id).value;
    $(id).replaceChildren();
    for(const p of team)$(id).add(new Option(`${p.nickname||p.species} · ${p.species}`,String(p.slot)));
    if(team.some(p=>String(p.slot)===before))$(id).value=before;
  }
  if($('analysis-b').value===$('analysis-a').value&&team.length>1)$('analysis-b').value=String(team[1].slot);
}
function defenseTable(team,types,chart,abilities,simple){
  const teamHeaders=simple?'':team.map(p=>
    `<th>${esc(p.nickname||p.species)}<small>${esc(list(p.types).join(' / '))}<br>${abilities?esc(p.ability):''}</small></th>`
  ).join('');
  const rows=types.map(type=>{
    const values=team.map(p=>TypeAnalysis.defensive(chart,type,p,abilities));
    const cells=simple?'':values.map(v=>`<td class="${cellClass(v)}">${multiplier(v)}</td>`).join('');
    return `<tr><th>${esc(type)}</th>${cells}`
      +`<td>${values.filter(v=>v>1).length}</td>`
      +`<td>${values.filter(v=>v>0&&v<1).length}</td>`
      +`<td>${values.filter(v=>v===0).length}</td></tr>`;
  }).join('');
  return '<div class="analysis-scroll">'
    +`<table class="analysis-table ${simple?'analysis-simple':''}">`
    +`<caption>${simple?'Pokémon por tipo · Sin neutrales':'Efectividad defensiva'}</caption>`
    +`<thead><tr><th>Tipo atacante</th>${teamHeaders}<th>Débiles</th><th>Resisten</th><th>Inmunes</th></tr></thead>`
    +`<tbody>${rows}</tbody>`
    +'</table></div>';
}
function coverageReport(chosen,types,chart,abilities,dual){
  const moves=chosen.flatMap(p=>list(p.analysis_moves).filter(m=>m&&m.category!=='Estado').map(m=>[m,p]));
  const targets=types.map(t=>[t]);
  if(dual)for(let i=0;i<types.length;i++)for(let j=i+1;j<types.length;j++)targets.push([types[i],types[j]]);
  const results=targets.map(target=>({target,best:TypeAnalysis.coverage(chart,chosen,target,abilities)}));
  const moveList=moves.map(([m,p])=>
    `<span>${esc(m.name)} <small>${esc(TypeAnalysis.attackType(m,p,abilities))} · ${esc(p.nickname||p.species)}</small></span>`
  ).join('')||'<p>No hay movimientos ofensivos disponibles.</p>';
  const cells=results.map(({target,best})=>
    `<article class="coverage-cell ${best?cellClass(best.value):'neutral'}">`
    +`<strong>${esc(target.join(' / '))}</strong>`
    +`<b>${multiplier(best?.value??null)}</b>`
    +`<small>${best?esc(best.move.name)+' · '+esc(best.pokemon.nickname||best.pokemon.species):'Sin ataque'}</small>`
    +'</article>'
  ).join('');
  return `<div class="coverage-moves">${moveList}</div>`
    +'<p class="subtitle">Mejor cobertura · Sin sumar ataques</p>'
    +'<div class="coverage-summary">'
    +`<span>${results.filter(r=>r.best?.value>1).length} supereficaces</span>`
    +`<span>${results.filter(r=>r.best?.value===1).length} neutrales</span>`
    +`<span>${results.filter(r=>r.best&&r.best.value<1).length} resistidos / inmunes</span>`
    +'</div>'
    +`<div class="coverage-grid">${cells}</div>`;
}
for(const id of ['analysis-defense','analysis-mode','analysis-a','analysis-b','analysis-abilities','analysis-dual'])$(id).onchange=renderAnalysis;

// Optional Companion dependency can be recovered after a transient local load failure.
let companionRetryPending=false;
function companionScriptFailed(){
  companionRetryPending=false;
  $('companion-load-error').hidden=false;
  $('companion-load-retry').disabled=false;
}
window.companionScriptFailed=companionScriptFailed;
// Loaded from here (not an inline onerror attribute) so the page can run
// under a Content-Security-Policy without inline scripts.
function loadCompanion(){
  const script=document.createElement('script');script.src='/companion.js';
  script.onload=()=>{companionRetryPending=false;$('companion-load-error').hidden=true;};
  script.onerror=companionScriptFailed;document.body.append(script);
}
$('companion-load-retry').onclick=()=>{
  if(companionRetryPending)return;
  companionRetryPending=true;$('companion-load-retry').disabled=true;
  loadCompanion();
};
// companion.js reads dialogs declared after app.js: wait for the full DOM.
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',loadCompanion,{once:true});
else loadCompanion();
