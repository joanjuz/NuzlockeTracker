'use strict';
/** Private-by-default Soul Link presentation. Full remote views only live in memory
 * for the remaining server lease; linked-capture events do not need those views. */
window.PokeJuzSoul = (() => {
  const family = game => game?.startsWith('Ultra ')?'alola':game?.startsWith('Pokémon ')?'xy':'oras';
  const labels = {alive:'Captura enlazada',dead:'Muerto',traded:'Intercambiado',missing:'Fuera de la lectura'};
  function captureIndex(member,catalog){
    const result=new Map(),rows=catalog(member.game)||[];
    for(const [route,capture] of Object.entries(member.soul?.captures||{})){
      const row=rows.find(r=>family(member.game)+':'+r.id===route);
      if(!row||!capture?.key)continue;
      result.set(route,{id:route,name:row.name,order:row.story_order||row.id,missed:false,
        candidates:new Map([[capture.key,{key:capture.key,mon:capture.pokemon||{},status:labels[capture.status]||'Captura enlazada'}]])});
    }
    for(const route of member.soul?.missed_routes||[]){
      const row=rows.find(r=>family(member.game)+':'+r.id===route||String(r.id)===String(route)||(r.ids||[]).some(id=>String(id)===String(route)));
      if(!row)continue;
      const id=family(member.game)+':'+row.id;
      if(!result.has(id))result.set(id,{id,name:row.name,order:row.story_order||row.id,candidates:new Map(),missed:true});
      result.get(id).missed=true;
    }
    return result;
  }
  function groups(room,playerId,ownState,catalog){
    const indexes=room.members.map(m=>m.player_id===playerId&&ownState?.game===m.game
      ?window.PokeJuzRoom.index({...m,state:ownState},catalog):captureIndex(m,catalog));
    const all=new Map();
    for(const map of indexes)for(const [key,row] of map)if(!all.has(key))all.set(key,row);
    return [...all.values()].sort((a,b)=>a.id.split(':')[0].localeCompare(b.id.split(':')[0])||a.order-b.order).map(row=>({
      ...row,members:room.members.map((member,i)=>({member,row:indexes[i].get(row.id),
        selected:member.links?.[row.id]||'',compatible:row.id.startsWith(family(member.game)+':')}))
    }));
  }
  function create({el,action,showMember,backToLocal,catalog,local,propose,resetNotices,enabled,now=()=>Date.now()}){
    const panel=el('room-panel');
    if(!panel)return null;
    let info=null,session='',selected='',busy=false,recoveryShown=false,idleShown=false,seen=new Map(),leases=new Map();
    const node=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
    const button=(text,fn)=>{const n=node('button',text);n.type='button';n.onclick=fn;return n;};
    function reset(){seen.clear();resetNotices();}
    function discardViews(){
      if(info?.room)for(const member of info.room.members)member.state=null;
      for(const lease of leases.values())lease.until=Math.min(lease.until,now());
      if(selected){selected='';backToLocal();}
    }
    function clear(){
      if(!info&&!recoveryShown&&!idleShown)return;
      discardViews();reset();info=null;session='';recoveryShown=false;idleShown=false;
      el('room-roster').removeAttribute?.('data-count');el('room-roster').style?.removeProperty?.('--room-count');
      el('soul-own-sharing').hidden=true;el('soul-admin').hidden=true;
      el('companion-linked').className='';el('companion-joined-text').hidden=false;
      el('companion-share').closest('label').hidden=false;el('companion-copy').hidden=false;
      el('companion-refresh').hidden=false;el('companion-leave').textContent='Desvincular y borrar datos de la pareja';
    }
    function idle(next){
      clear();idleShown=true;recoveryShown=Boolean(next.can_resume||next.can_forget);
      panel.hidden=true;el('companion-title').textContent='Soul Link';
      el('companion-setup').hidden=false;el('companion-linked').hidden=!recoveryShown;
      el('companion-linked').className='soul-linked-controls';el('companion-joined-text').hidden=true;
      el('companion-share').closest('label').hidden=true;el('companion-copy').hidden=true;el('companion-refresh').hidden=true;
      el('companion-leave').textContent='Olvidar conexión guardada';
      el('companion-status').textContent=next.error||(recoveryShown?'Tienes una conexión guardada. Pega la invitación para recuperarla.':'Crea una sala o pega la invitación de tus amigos.');
    }
    function setBusy(value){
      busy=value;if(!info)return;
      for(const control of panel.querySelectorAll?.('button,select,input')||[])control.disabled=busy||Boolean(control.soulBlocked);
      el('soul-new-run').disabled=busy;
    }
    function clampViews(next){
      const current=now(),liveIds=new Set();
      for(const member of next.room.members){
        const id=member.player_id+'|'+member.run_id;liveIds.add(id);
        if(!next.configured||member.sharing!==true||!member.online||!member.source_live||!member.state){member.state=null;leases.set(id,{sequence:member.sequence,until:Math.min(leases.get(id)?.until??current,current)});continue;}
        const ttl=Number.isInteger(member.view_ttl_ms)?Math.max(0,Math.min(12000,member.view_ttl_ms)):0;
        const previous=leases.get(id),deadline=current+ttl;
        // A repeated cached sequence may shorten a lease, never extend it.
        leases.set(id,{sequence:member.sequence,until:previous&&previous.sequence>=member.sequence?Math.min(previous.until,deadline):deadline});
        if(leases.get(id).until<=current)member.state=null;
      }
      for(const id of leases.keys())if(!liveIds.has(id))leases.delete(id);
    }
    function canView(member){
      const lease=leases.get(member.player_id+'|'+member.run_id);
      return Boolean(info?.configured&&member.sharing===true&&member.online&&member.source_live&&member.state&&lease&&lease.until>now());
    }
    function eventFor(notice){
      const member=info?.room.members.find(m=>m.player_id===notice.playerId&&m.run_id===notice.runId);
      return {member,capture:member?.soul?.captures?.[notice.route]};
    }
    function valid(notice){
      if(notice.protocol!==3)return true;
      if(!info?.configured||notice.roomSession!==session)return false;
      const {member,capture}=eventFor(notice),own=info.room.members.find(m=>m.player_id===info.player_id);
      return Boolean(member?.online&&member.source_live&&capture?.status==='dead'&&!capture.response&&
        capture.key===notice.pokemonKey&&String(capture.death_at||'')===notice.recordedAt&&
        member.links?.[notice.route]===notice.pokemonKey&&own?.links?.[notice.route]===notice.localKey);
    }
    function commandContext(notice){
      if(notice.protocol!==3)return {};
      const own=info.room.members.find(m=>m.player_id===info.player_id);
      return {soullink_room:{protocol:3,session_id:info.room.session_id,epoch:info.room.epoch,local_run_id:own.run_id,
        player_id:notice.playerId,run_id:notice.runId,route:notice.route,pokemon_key:notice.pokemonKey,recorded_at:notice.recordedAt}};
    }
    function observe(){
      if(!info.configured)return;
      const own=info.room.members.find(m=>m.player_id===info.player_id),scopes=new Set();
      for(const member of info.room.members){
        const scope=member.player_id+'|'+member.run_id;scopes.add(scope);
        if(member.player_id===info.player_id)continue;
        const previous=seen.get(scope),current=new Set();
        for(const [route,capture] of Object.entries(member.soul?.captures||{})){
          if(capture.status!=='dead')continue;
          const id=capture.key+'|'+String(capture.death_at||'');current.add(id);
          if(!previous||previous.has(id)||!enabled()||capture.response||!member.online||!member.source_live)continue;
          const localKey=own?.links?.[route];
          if(!localKey||member.links?.[route]!==capture.key)continue;
          propose({protocol:3,id:scope+'|'+id,remoteMon:capture.pokemon,remoteGame:member.game,partnerName:member.name,
            remoteName:'su captura enlazada',localKey,roomSession:session,playerId:member.player_id,
            runId:member.run_id,pokemonKey:capture.key,recordedAt:String(capture.death_at||''),route});
        }
        seen.set(scope,current);
      }
      for(const key of seen.keys())if(!scopes.has(key))seen.delete(key);
    }
    function showRoster(){
      const room=info.room,roster=el('room-roster');roster.replaceChildren();
      roster.setAttribute('data-count',String(Math.max(1,room.members.length)));
      roster.style?.setProperty('--room-count',String(Math.max(1,room.members.length)));
      for(const member of room.members){
        const own=member.player_id===info.player_id,card=node('article',undefined,'room-player soul-player');
        card.append(node('strong',member.name+(own?' · Tú':'')+(member.player_id===room.host_id?' · Anfitrión':'')));
        card.append(node('small',member.game));
        card.append(node('p',!info.configured?'Sin conexión':!member.online?'Sin conexión · plaza reservada':!member.source_live?'Conectado · esperando lectura':'Conectado','room-presence'));
        card.append(node('p',member.sharing?'Partida compartida':'Partida privada','soul-privacy '+(member.sharing?'is-shared':'is-private')));
        if(canView(member)){
          const team=node('ul',undefined,'room-team');
          for(const p of member.state.party||[])if(p)team.append(node('li',`${p.nickname||p.species||'Pokémon'} · Nv. ${p.level??'?'} · PS ${p.hp??'?'}/${p.max_hp??'?'}`));
          card.append(team);
          if(!own)card.append(button('Ver partida',()=>{if(!canView(member))return;selected=member.player_id;showMember(member,true);}));
        }else card.append(node('p',member.sharing?'Esperando una vista actual.':own?'Tú decides si muestras tu equipo, cajas y estadísticas.':'Participa en Soul Link sin mostrar su equipo ni sus cajas.','soul-private-note'));
        if(info.configured&&info.direct_role==='host'&&!own){
          const options=node('details'),summary=node('summary','Administrar participante');options.append(summary);
          options.append(button('Liberar plaza',()=>{if(confirm('¿Liberar la plaza de '+member.name+' y cerrar su conexión? Si conserva el enlace podrá volver a unirse.'))action('soul_remove',{player_id:member.player_id});}));
          card.append(options);
        }
        roster.append(card);
      }
    }
    function showGroups(){
      const room=info.room,ownState=local(),own=room.members.find(m=>m.player_id===info.player_id);
      const list=groups(room,info.player_id,ownState,catalog),table=el('room-groups');table.replaceChildren();
      const head=node('tr');head.append(node('th','Ruta'));
      for(const member of room.members)head.append(node('th',member.name));
      const thead=node('thead');thead.append(head);table.append(thead);const tbody=node('tbody');
      for(const group of list){
        const row=node('tr');row.append(node('th',group.name));
        for(const {member,row:entry,selected:choice,compatible} of group.members){
          const cell=node('td'),chosen=entry?.candidates.get(choice);
          const title=chosen?.mon.nickname||chosen?.mon.species||(chosen?'Captura #'+chosen.mon.species_id:'');
          cell.append(node('span',!compatible?'Otro mapa':entry?.missed?'Miss':choice?chosen?title+' · '+chosen.status:'Captura enlazada · fuera de la lectura':'Sin captura elegida'));
          if(compatible&&member.player_id===info.player_id&&info.configured){
            const select=node('select');select.setAttribute('aria-label','Tu captura en '+group.name);
            const empty=node('option','Sin enlace');empty.value='';select.append(empty);
            for(const capture of entry?.candidates.values()||[]){const option=node('option',`${capture.mon.nickname||capture.mon.species||'Captura #'+capture.mon.species_id} · ${capture.status}`);option.value=capture.key;select.append(option);}
            if(choice&&!chosen){const option=node('option','Captura anterior · no sustituir');option.value=choice;select.append(option);}
            select.value=choice;select.soulBlocked=!own?.online||!ownState||ownState.stale||ownState.game!==own.game||ownState.connection?.status!=='connected';select.disabled=busy||select.soulBlocked;
            select.onchange=()=>action('soul_link',{route:group.id,pokemon_key:select.value||null});cell.append(select);
          }
          row.append(cell);
        }
        tbody.append(row);
      }
      table.append(tbody);el('room-no-groups').hidden=list.length>0;
      const log=el('room-events');log.replaceChildren();
      const eventLabels={joined:'Entró en la sala',left:'Salió; su plaza está libre',reconnected:'Recuperó su conexión',death:'Registró una muerte enlazada',revived:'Reanimó una captura enlazada',missed:'Registró una ruta Miss',linked:'Enlazó una captura',unlinked:'Retiró un enlace'};
      for(const event of [...(room.events||[])].reverse().slice(0,30)){
        const member=room.members.find(m=>m.player_id===event.player_id&&m.run_id===event.run_id);
        log.append(node('li',`${member?.name||'Un participante'} · ${eventLabels[event.kind]||'Actualizó Soul Link'}${event.route?' · '+(list.find(g=>g.id===event.route)?.name||'Ruta enlazada'):''}`));
      }
    }
    function render(){
      if(!info)return;
      const room=info.room;
      recoveryShown=Boolean(info.can_resume||info.can_forget);
      panel.hidden=false;el('companion-setup').hidden=Boolean(info.configured);el('companion-linked').hidden=!info.configured&&!recoveryShown;
      el('companion-title').textContent='Soul Link';el('room-title').textContent='Participantes';
      el('companion-linked').className='soul-linked-controls';el('companion-joined-text').hidden=true;
      el('companion-share').value=info.invite_link||'';el('companion-share').closest('label').hidden=!info.invite_link;
      el('companion-copy').hidden=!info.invite_link;el('companion-copy').disabled=busy||!info.invite_link;
      el('companion-leave').textContent=!info.configured?'Olvidar conexión guardada':info.direct_role==='host'?'Cerrar sala':'Salir';
      el('companion-refresh').hidden=!info.configured;
      el('companion-refresh').textContent='Actualizar';
      const online=room.members.filter(m=>m.online).length,reserved=room.members.length-online;
      el('room-summary').textContent=`${room.members.length}/4 participantes${reserved?' · '+reserved+' '+(reserved===1?'plaza reservada':'plazas reservadas'):''}`;
      el('companion-status').textContent=info.error||(!info.configured?'Última sala · sin conexión':info.direct_role==='host'&&!info.invite_link?'Enlace revocado · quienes ya entraron siguen en la sala':room.members.length===4?'Sala completa · todos los lugares están ocupados':`Sala abierta · ${4-room.members.length} ${room.members.length===3?'lugar disponible':'lugares disponibles'}`);
      el('room-host-actions').hidden=true;
      el('soul-own-sharing').hidden=!info.configured;el('soul-sharing').checked=Boolean(info.own_sharing);
      el('soul-sharing').soulBlocked=!info.configured;el('soul-sharing').disabled=busy||!info.configured;
      el('soul-sharing-state').textContent=info.own_sharing?'Tu partida está visible para los participantes.':'Tu partida está privada. Los enlaces y avisos Soul Link continúan funcionando.';
      el('soul-admin').hidden=!info.configured||info.direct_role!=='host';
      el('soul-revoke').soulBlocked=!info.invite_link;el('soul-revoke').disabled=busy||!info.invite_link;
      el('companion-disclaimer').textContent='Solo compartes las capturas que enlazas y sus eventos Soul Link. Compartir mi partida permite además ver tu equipo, estadísticas y cajas leídas. Nadie modifica tu partida.';
      showRoster();showGroups();
      const member=room.members.find(m=>m.player_id===selected);
      if(member&&canView(member))showMember(member,false);else if(selected){selected='';backToLocal();}
      setBusy(busy);
    }
    function update(next){
      if(info?.room.session_id===next.room.session_id&&info.room.epoch===next.room.epoch&&next.room.revision<info.room.revision)return;
      const own=next.room.members.find(m=>m.player_id===next.player_id),key=next.room.session_id+'|'+next.room.epoch+'|'+String(own?.run_id||'');
      if(key!==session){discardViews();reset();session=key;selected='';leases.clear();backToLocal();}
      info=next;clampViews(info);
      if(!info.configured)resetNotices();
      render();observe();
    }
    function tick(){
      if(!info)return;
      let changed=false;
      for(const member of info.room.members)if(member.state&&!canView(member)){member.state=null;changed=true;}
      if(changed)render();
    }
    function failed(){
      if(!info)return;
      discardViews();for(const member of info.room.members){member.online=false;member.source_live=false;}
      resetNotices();render();
    }
    el('soul-sharing').onchange=()=>action('soul_share',{sharing:el('soul-sharing').checked});
    el('soul-regenerate').onclick=()=>{if(confirm('¿Cambiar el enlace? El anterior dejará de admitir personas nuevas. Quienes ya están conectados conservarán su conexión.'))action('soul_invite');};
    el('soul-revoke').onclick=()=>{if(confirm('¿Revocar el enlace? No expulsará a quienes ya están en la sala.'))action('soul_revoke');};
    el('soul-new-run').onclick=()=>{if(confirm('¿Separar este reto del anterior para Soul Link? No se borrará tu progreso local.'))action('soul_new_run',{game:el('companion-game').value});};
    setInterval(tick,500);
    return {update,idle,clear,reset,valid,commandContext,setBusy,failed,tick};
  }
  return {create,groups,captureIndex};
})();
