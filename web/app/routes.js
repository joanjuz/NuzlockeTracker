'use strict';
// Route catalogs, origins and route tiles.
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
