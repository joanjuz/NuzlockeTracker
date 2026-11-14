'use strict';
/** Optional companion view: the existing views render either your state or the last saved partner snapshot. */
(() => {
  const el = id => document.getElementById(id);
  const toggle = el('companion-toggle');
  const dialog = el('companion-dialog');
  const indicator = el('companion-status');
  let roomController = null;
  let soulController = null;
  let sessionProtocol = 0;
  let sessionConfigured = false;
  let statusGeneration = 0;
  let soulRemoteViewed = false;
  const noticeController = notice => notice?.protocol === 3 ? soulController : roomController;
  let remote = null;
  let viewingPartner = false;
  let lastUpdate = -1;
  let working = false;
  let connectionMode = 'direct';
  const transportControl = el('companion-transport');
  function updateTransport() {
    connectionMode = ['cloud','room','soul'].includes(transportControl?.value) ? transportControl.value : 'direct';
    const direct = connectionMode !== 'cloud';
    if(el('room-capacity-label'))el('room-capacity-label').hidden=connectionMode!=='room';
    if(el('companion-direct-host')){el('companion-direct-host').textContent=['room','soul'].includes(connectionMode)?'Crear sala':'Ser host';el('companion-direct-host').hidden=connectionMode==='cloud';}
    if(el('soul-new-run'))el('soul-new-run').hidden=connectionMode!=='soul';
    if(el('room-new-run'))el('room-new-run').hidden=connectionMode!=='room';
    const fields = el('companion-direct-fields');
    if (fields) fields.hidden = !direct;
    el('companion-create').hidden = direct;
    const keyLabel = el('companion-setup-key').closest?.('label');
    if (keyLabel) keyLabel.hidden = direct;
    const urlDetails = el('companion-url').closest?.('details');
    if (urlDetails) urlDetails.hidden = direct;
    el('companion-join').textContent = connectionMode==='soul'?'Unirse':direct ? 'Unirme al host' : 'Unirme por Cloudflare';
    el('companion-invite').placeholder = connectionMode==='soul'?'Pega aquí el enlace de la sala':direct ? 'nuzlocke://192.168.1.10:8770/join#…' : 'Enlace o código de Cloudflare';
  }
  if (transportControl) transportControl.onchange = updateTransport;
  updateTransport();

  function asView(p) {
    if (!p?.state || p.state.schema_version !== 1) return null;
    const source = p.state;
    if (!gameFamily(source.game) || !Array.isArray(source.party) ||
        !source.boxes || typeof source.boxes !== 'object' || !source.progress || typeof source.progress !== 'object')
      return null;
    return {
      ...source, stale: true, demo: false, selected_box: 1, battle_hp: false,
      connection: {status:'disconnected', message: 'Última sesión de ' + p.name},
      scan: {active:false, completed:0}, box_verified: true,
    };
  }
  const soulToggle = el('soullink-enabled');
  const soulNotice = el('soullink-notification');
  const soulDescription = el('soullink-description');
  const souls = {seen:new Set(),pair:'',pending:null,queue:[],initialized:false,busy:false};
  const soulChoice = el('soullink-candidate');
  const soulChoiceRow = el('soullink-choice-row');
  const soulImage = el('soullink-pokemon-icon');
  const soulFallback = el('soullink-sprite-fallback');
  const soulError = el('soullink-notice-error');
  // Storage may be unavailable (privacy mode, locked WebView2 profile): the toggle still works this session.
  try { soulToggle.checked = localStorage.getItem('soullink-manual-enabled') === 'true'; }
  catch (error) { soulToggle.checked = false; }
  soulToggle.onchange = () => {
    try { localStorage.setItem('soullink-manual-enabled',String(soulToggle.checked)); } catch (error) {}
    soulNotice.hidden = true; souls.pending = null; souls.queue = [];
    souls.initialized = false;
    roomController?.reset();
    soulController?.reset();
  };
  function deathIdentity(entry,key){return key+'|'+String(entry?.recorded_at||'')}
  // Location IDs are resolved with the partner game's catalog, not whatever view is on screen.
  function catalogFor(game){
    const cached = typeof routeCatalogFor === 'function' ? routeCatalogFor(game) : [];
    return Array.isArray(cached) && cached.length ? cached : (Array.isArray(routeCatalog) ? routeCatalog : []);
  }
  function sameRoute(a,b,game){
    if(!a||!b||!Number.isInteger(a.met_location_id)||!Number.isInteger(b.met_location_id))return false;
    const ids = catalogFor(game).find(r=>Array.isArray(r?.ids)?r.ids.includes(a.met_location_id):r?.id===a.met_location_id)?.ids;
    return ids ? ids.includes(b.met_location_id) : a.met_location_id===b.met_location_id;
  }
  // Equipo primero, después cajas: una misma captura se muestra UNA sola vez.
  // La clave coincide con la que valida el servidor al marcar una muerte.
  const routeFamily = game => gameFamily(game);
  function routeCandidates(remoteMon,remoteGame){
    const own=localState, family=routeFamily(own?.game);
    // Location IDs are local to each game's region. A traded Pokémon's origin
    // version does not identify the current session or provide a route mapping.
    if(!family || family!==routeFamily(remoteGame))return [];
    if(!remoteMon || !own || own.stale || own.connection?.status!=='connected')return [];
    const members=[];
    (own.party||[]).forEach((mon,i)=>members.push({mon,where:'Equipo '+(i+1)}));
    for(const [box,items] of Object.entries(own.boxes||{})){
      (items||[]).forEach(mon=>members.push({mon,where:'Caja '+box}));
    }
    const unique=new Set(),deaths=own.progress?.deaths||{},eligible=[];
    for(const {mon,where} of members){
      if(!mon || mon.egg || mon.checksum_valid!==true ||
          !Number.isInteger(mon.encryption_constant) || !sameRoute(mon,remoteMon,remoteGame))continue;
      const key=String(mon.origin_version??33)+':'+mon.encryption_constant;
      if(unique.has(key)||deaths[key])continue;
      unique.add(key);
      eligible.push({key,mon,where});
    }
    return eligible;
  }
  function showSoulSprite(pokemon){
    const id=Number(pokemon?.species_id);
    soulImage.hidden=true;
    soulImage.removeAttribute('src');
    soulFallback.hidden=false;
    soulFallback.textContent=Number.isInteger(id)&&id>0?'#'+id:'—';
    soulImage.alt='Sprite de '+(pokemon?.nickname||pokemon?.species||'Pokémon');
    if(!Number.isInteger(id)||id<1||id>10115)return;
    soulImage.onload=()=>{soulImage.hidden=false;soulFallback.hidden=true};
    soulImage.onerror=()=>{soulImage.hidden=true;soulFallback.hidden=false};
    soulImage.src='/soullink/sprite/'+id+'.png';
  }
  function clearSoulError(){soulError.hidden=true;soulError.textContent=''}
  function updateSoulSelection(){
    const notice=souls.pending;
    if(!notice)return;
    const selected=notice.candidates.find(c=>c.key===notice.selectedKey);
    const who=notice.partnerName+' registró la muerte de '+notice.remoteName+'. ';
    soulDescription.textContent=selected
      ?who+'En esa ruta tienes a '+(selected.mon.nickname||selected.mon.species)+'. ¿Quieres marcar su muerte?'
      :who+'Tienes '+notice.candidates.length+' Pokémon de esa ruta. Elige cuál deseas marcar.';
    el('soullink-kill').disabled=!selected||souls.busy;
    showSoulSprite(selected?.mon||notice.remoteMon);
  }
  soulChoice.onchange=()=>{
    if(!souls.pending)return;
    souls.pending.selectedKey=soulChoice.value;
    clearSoulError();
    updateSoulSelection();
  };
  function showNextProposal(){
    if(souls.pending || !soulToggle.checked)return;
    while(souls.queue.length){
      const next=souls.queue.shift();
      if(noticeController(next)&&!noticeController(next).valid(next))continue;
      const candidates=routeCandidates(next.remoteMon,next.remoteGame).filter(c=>!next.localKey||c.key===next.localKey);
      if(!candidates.length)continue;
      souls.pending={...next,candidates,selectedKey:candidates.length===1?candidates[0].key:''};
      soulChoice.replaceChildren();
      if(candidates.length>1){
        const prompt=document.createElement('option');
        prompt.value='';prompt.textContent='Seleccionar Pokémon…';soulChoice.append(prompt);
      }
      for(const candidate of candidates){
        const option=document.createElement('option');
        option.value=candidate.key;
        const mon=candidate.mon;
        option.textContent=(mon.nickname||mon.species||'Pokémon')+
          (mon.nickname&&mon.species&&mon.nickname!==mon.species?' ('+mon.species+')':'')+
          ' · '+candidate.where;
        soulChoice.append(option);
      }
      soulChoiceRow.hidden=candidates.length<=1;
      soulChoice.value=souls.pending.selectedKey;
      clearSoulError();
      updateSoulSelection();
      soulNotice.hidden=false;
      return;
    }
    soulNotice.hidden=true;
  }
  function observePartnerDeaths(info){
    if(!info.configured || !info.partner?.state?.progress?.deaths) return;
    const pair=String(info.transport)+'|'+String(info.host_address||info.worker_url||info.default_worker_url)+'|'+String(info.my_name)+'|'+String(info.partner.name);
    if(souls.pair!==pair){
      souls.pair=pair;souls.seen.clear();souls.initialized=false;
      souls.queue=[];souls.pending=null;soulNotice.hidden=true;
    }
    const deaths=info.partner.state.progress.deaths;
    const remoteGame=info.partner.state.game||info.partner.game;
    // Warm the partner game's route catalog before the first death needs it.
    if(gameFamily(remoteGame))catalogFor(remoteGame);
    if(!souls.initialized || !soulToggle.checked){
      for(const [key,entry] of Object.entries(deaths))souls.seen.add(deathIdentity(entry,key));
      souls.initialized=true;return;
    }
    for(const [key,entry] of Object.entries(deaths)){
      const id=deathIdentity(entry,key);
      if(souls.seen.has(id))continue;
      souls.seen.add(id);
      // Si el compañero marcó esta muerte COMO RESPUESTA a la nuestra,
      // ya está vinculada: no crear una notificación de rebote.
      if(entry?.source==='soullink-response')continue;
      const remoteMon=entry?.pokemon;
      if(!remoteMon || !routeCandidates(remoteMon,remoteGame).length)continue;
      souls.queue.push({
        id,remoteMon,remoteGame,partnerName:String(info.partner.name||'Tu compañero'),
        remoteName:String(remoteMon.nickname||remoteMon.species||'Pokémon'),
      });
    }
    showNextProposal();
  }
  el('soullink-dismiss').onclick=()=>{
    if(souls.busy)return;
    souls.pending=null;soulNotice.hidden=true;showNextProposal();
  };
  el('soullink-kill').onclick=async()=>{
    const current=souls.pending;
    if(!current || !token || souls.busy)return;
    const selected=routeCandidates(current.remoteMon,current.remoteGame).find(p=>p.key===current.selectedKey);
    if(!selected||(current.localKey&&selected.key!==current.localKey)||(noticeController(current)&&!noticeController(current).valid(current))){
      soulError.textContent='Ese Pokémon ya no está disponible. Ignora el aviso si cambió tu equipo.';
      soulError.hidden=false;return;
    }
    souls.busy=true;
    el('soullink-kill').disabled=true;
    try{
      const response=await fetch('/api/command',{method:'POST',
        headers:{'Content-Type':'application/json','X-Tracker-Token':token},
        body:JSON.stringify({action:'mark_dead',key:selected.key,source:'soullink-response',...noticeController(current)?.commandContext(current)})});
      const payload=await response.json();
      if(!response.ok)throw Error(payload.error||'No se pudo registrar la muerte');
      souls.pending=null;soulNotice.hidden=true;
    }catch(err){
      soulError.textContent='No se registró la muerte: '+err.message;
      soulError.hidden=false;
    }finally{
      souls.busy=false;
      if(souls.pending)updateSoulSelection();
      else showNextProposal();
    }
  };
  const stamp = ms => ms ? new Date(ms).toLocaleString('es-CR') : 'Aún no ha compartido una sesión';
  function updatePage(info) {
    sessionProtocol=info.protocol||0;
    sessionConfigured=Boolean(info.configured);
    if(soulController&&info.protocol===3){roomController?.clear();if(info.room)soulController.update(info);else soulController.idle(info);return;}
    if(soulController&&!info.configured&&connectionMode==='soul'){roomController?.clear();soulController.idle(info);return;}
    soulController?.clear();
    if(roomController&&info.protocol===2&&info.room){roomController.update(info);el('companion-title').textContent='Conexión anterior';el('companion-disclaimer').textContent='Esta sala anterior comparte la partida completa. Para controlar su visibilidad, sal y usa Soul Link.';return;}
    roomController?.clear();
    el('companion-title').textContent='Soul Link';
    el('companion-disclaimer').textContent=info.configured?'Esta conexión anterior comparte la última partida completa. Para controlar su visibilidad, sal y usa Soul Link.':'Tu partida está privada al entrar. Solo se comparten las capturas que enlazas y sus eventos Soul Link.';
    const p = info.partner;
    if (info.default_worker_url && !el('companion-url').value) el('companion-url').value = info.default_worker_url;
    const hasPartner = Boolean(p);
    observePartnerDeaths(info);
    const snapshot = asView(p);
    const hasView = hasPartner && Boolean(snapshot);
    toggle.hidden = !hasPartner;
    toggle.textContent = viewingPartner ? '← Mi partida' : 'Compañero';
    el('companion-setup').hidden = Boolean(info.configured);
    el('companion-linked').hidden = !info.configured;
    if (info.configured) {
      const status = hasPartner ? `Sincronizado con ${p.name} · ${p.game}` : 'Esperando a tu compañero';
      el('companion-joined-text').textContent = status + (p?.updated_at ? ` · ${stamp(p.updated_at)}` : '');
      if (info.transport === 'direct') el('companion-joined-text').textContent += info.direct_role === 'host' ? ` · Host: ${info.host_address}` : ' · Conexión directa';
      el('companion-share').value = info.invite_link || info.invite_code || (hasPartner ? 'Compañero vinculado' : 'Código utilizado o no disponible');
      el('companion-copy').disabled = !info.invite_code;
    }
    indicator.textContent = info.error ? `Aviso: ${info.error}` :
      info.configured ? hasPartner ? `Compañero vinculado · última sesión: ${stamp(p.updated_at)}` : 'Pareja creada: comparte el código con tu compañero.' :
      'Todavía no hay compañero vinculado.';
    if (viewingPartner && !hasView) {
      viewingPartner = false;
      window.setCompanionView(false);
      toggle.textContent = 'Compañero';
    }
    if (hasView) {
      remote = snapshot;
      if (viewingPartner && lastUpdate !== p.updated_at) window.setCompanionView(true, remote);
      lastUpdate = p.updated_at;
    } else {
      remote = null;
      lastUpdate = -1;
    }
  }
  async function getStatus() {
    const generation=statusGeneration;
    try {
      const response = await fetch('/api/companion', {cache:'no-store'});
      if (!response.ok) throw Error('No se pudo consultar la sincronización local');
      const info=await response.json();
      if(generation===statusGeneration&&!working)updatePage(info);
    } catch (error) {
      if(generation!==statusGeneration||working)return;
      soulController?.failed();
      indicator.textContent = error.message;
    }
  }
  async function action(actionName, extra = {}) {
    if (working) return;
    working = true;
    statusGeneration++;
    roomController?.setBusy(true);
    soulController?.setBusy(true);
    for(const id of ['companion-create','companion-join','companion-refresh','companion-leave','companion-direct-host']) {if(el(id))el(id).disabled = true;}
    indicator.textContent = 'Procesando…';
    try {
      if (!token) throw Error('Espera a que conecte el servidor local.');
      const response = await fetch('/api/companion', {
        method:'POST',headers:{'Content-Type':'application/json','X-Tracker-Token':token},
        body:JSON.stringify({action:actionName,...extra}),
      });
      const body = await response.json();
      if (!response.ok) throw Error(body.error || 'No se completó la operación');
      if (actionName === 'leave') {viewingPartner = false;remote = null;window.setCompanionView(false);}
      updatePage(body);
    } catch(error) {
      indicator.textContent = error.message;
    } finally {
      el('companion-setup-key').value = '';
      working = false;
      statusGeneration++;
      roomController?.setBusy(false);
      soulController?.setBusy(false);
      for(const id of ['companion-create','companion-join','companion-refresh','companion-leave','companion-direct-host']) {if(el(id))el(id).disabled = false;}
    }
  }
  const fields = () => ({
    worker_url:el('companion-url').value.trim(),
    name:el('companion-name').value.trim(),
    game:el('companion-game').value,
  });
  el('open-companion').onclick = () => {
    document.querySelectorAll('details[open]').forEach(d => d.open = false);
    const game = typeof localState === 'object' ? localState?.game : null;
    if(game && Array.from(el('companion-game').options || []).some(option=>option.value===game))el('companion-game').value=game;
    dialog.showModal();getStatus();
  };
  el('companion-close').onclick = () => dialog.close();
  el('companion-create').onclick = () => action('create', {...fields(),setup_key:el('companion-setup-key').value});
  if (el('companion-direct-host')) el('companion-direct-host').onclick = () => action(connectionMode==='soul'?'soul_host':connectionMode==='room'?'room_host':'direct_host', {
    ...fields(),...(el('companion-host').value.trim()?{host:el('companion-host').value.trim()}:{}),port:Number(el('companion-port').value),...(connectionMode==='room'?{capacity:Number(el('room-capacity')?.value||4)}:{}),
  });
  el('companion-join').onclick = () => {
    const invite=el('companion-invite').value.trim();
    if(connectionMode==='soul'&&(/\/(room|join)#/.test(invite))){
      indicator.textContent='Esta invitación usa una conexión anterior. Elige ese modo en Opciones de conexión; comparte la partida completa.';
      return;
    }
    const selected=invite.includes('/soul#')||connectionMode==='soul'?'soul_join':connectionMode==='room'||invite.includes('/room#')?'room_join':connectionMode==='direct'?'direct_join':'join';
    return action(selected,{...fields(),invite_code:invite});
  };
  el('companion-refresh').onclick = () => action('refresh');
  el('companion-leave').onclick = () => {
    if (confirm(sessionProtocol===3&&!sessionConfigured?'¿Olvidar esta conexión guardada? Si queda una plaza reservada, quien creó la sala podrá liberarla.':sessionProtocol===3?'¿Salir de Soul Link? Si creaste la sala, se cerrará para todos.':'¿Salir de esta conexión? Si eres host, se cerrará para todos. En Cloudflare se eliminará la pareja; la última sala Direct queda de solo lectura.')) action('leave');
  };
  el('companion-copy').onclick = async () => {
    const code = el('companion-share').value;
    if (code && navigator.clipboard) {
      try {await navigator.clipboard.writeText(code);indicator.textContent = 'Invitación copiada. Puedes enviar este mismo enlace a tus amigos.';}
      catch(error) {indicator.textContent = 'Selecciona el texto y cópialo manualmente.';}
    }
  };
  toggle.onclick = () => {
    if (viewingPartner) {viewingPartner = false;window.setCompanionView(false);}
    else if (remote) {viewingPartner = true;window.setCompanionView(true,remote);}
    else {indicator.textContent='Esperando la primera sesión del compañero.';dialog.showModal();}
    toggle.textContent = viewingPartner?'← Mi partida':'Compañero';
  };
  roomController=window.PokeJuzRoom?.create({el,action,
    catalog:game=>typeof routeCatalogFor==='function'?routeCatalogFor(game):[],
    enabled:()=>soulToggle.checked,
    resetNotices:()=>{souls.pending=null;souls.queue=[];souls.initialized=false;souls.pair='';soulNotice.hidden=true;},
    propose:notice=>{souls.queue.push(notice);showNextProposal();},
    backToLocal:()=>{viewingPartner=false;remote=null;window.setCompanionView(false);toggle.hidden=true;},
    showMember:(member,open)=>{
      remote=asView(member);if(!remote)return;
      if(open){viewingPartner=true;dialog.close();}
      if(viewingPartner)window.setCompanionView(true,remote);
      toggle.hidden=false;toggle.textContent=viewingPartner?'← Mi partida':'Ver jugador';
    },
  });
  soulController=window.PokeJuzSoul?.create({el,action,
    catalog:game=>typeof routeCatalogFor==='function'?routeCatalogFor(game):[],
    local:()=>typeof localState==='object'?localState:null,
    enabled:()=>soulToggle.checked,
    resetNotices:()=>{souls.pending=null;souls.queue=[];souls.initialized=false;souls.pair='';soulNotice.hidden=true;},
    propose:notice=>{souls.queue.push(notice);showNextProposal();},
    backToLocal:()=>{
      viewingPartner=false;remote=null;
      if(soulRemoteViewed){
        if(typeof detailPokemon!=='undefined')detailPokemon=null;
        if(typeof detailSignature!=='undefined')detailSignature='';
        if(typeof moveRequest!=='undefined')moveRequest++;
        for(const id of ['detail-content','move-content','boxes','dead','places','analysis-content','analysis-a','analysis-b'])el(id)?.replaceChildren?.();
        if(typeof boxSignature!=='undefined')boxSignature='';
        if(typeof placeSignature!=='undefined')placeSignature='';
        if(typeof deadSignature!=='undefined')deadSignature='';
        if(typeof analysisSignature!=='undefined')analysisSignature='';
        if(typeof analysisTeamSignature!=='undefined')analysisTeamSignature='';
        soulRemoteViewed=false;
      }
      window.setCompanionView(false);toggle.hidden=true;
    },
    showMember:(member,open)=>{
      remote=asView(member);if(!remote)return;
      if(open){viewingPartner=true;dialog.close();}
      if(viewingPartner){soulRemoteViewed=true;window.setCompanionView(true,remote);}
      toggle.hidden=false;toggle.textContent=viewingPartner?'← Mi partida':'Ver partida';
    },
  });
  getStatus();
  setInterval(getStatus, 5000);
})();
