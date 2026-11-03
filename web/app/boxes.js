'use strict';
// Boxes, Living Dex and box scan status.
for(let i=1;i<=32;i++)$('box').add(new Option(`Caja ${i}`,i));
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
function gen6ScanStatus(snapshot){
  return 'Gen6 experimental: '
    +(snapshot.box_verified?'cajas PK6 verificadas':'cajas pendientes de verificación; deposita un Pokémon en el PC y actualiza la lectura')
    +` · ${Object.keys(snapshot.boxes).length} / 31 cajas leídas`
    +(snapshot.scan.active?` · Escaneo: ${snapshot.scan.completed}/31`:'');
}
$('box').onchange=()=>{renderBoxes();command({action:'box',number:Number($('box').value)})};$('search').oninput=renderBoxes;$('global').onchange=renderBoxes;$('living-dex').onchange=()=>{$('box').disabled=$('living-dex').checked;$('global').disabled=$('living-dex').checked;$('living-dex-sprites').disabled=!$('living-dex').checked;boxSignature='';renderBoxes()};$('living-dex-sprites').onchange=()=>{boxSignature='';renderBoxes()};$('cancel').onclick=()=>command({action:'cancel'});
