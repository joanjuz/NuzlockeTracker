'use strict';
// Room views never write a local run. The existing explicit Soul Link confirmation
// is the only path from a proposal to a local mark_dead command.
window.PokeJuzRoom = (() => {
  const region = game => game?.startsWith('Ultra ')?'alola':game?.startsWith('Pokémon ')?'xy':'oras';
  const versions = {alola:[30,31,32,33],xy:[24,25],oras:[26,27]};
  const keyOf = p => Number.isInteger(p?.encryption_constant)?String(p.origin_version??33)+':'+p.encryption_constant:null;
  function index(member,catalog) {
    const result=new Map(),s=member.state;
    if(!s)return result;
    const family=region(member.game), rows=catalog(member.game)||[];
    const entries=[];
    for(const p of s.party||[])entries.push([keyOf(p),p,'Equipo']);
    for(const [box,mons] of Object.entries(s.boxes||{}))for(const p of mons)entries.push([keyOf(p),p,'Caja '+box]);
    for(const [key,d] of Object.entries(s.progress?.deaths||{}))entries.push([key,d.pokemon,'Muerto']);
    for(const [key,m] of Object.entries(s.progress?.route_marks||{}))entries.push([key,m.pokemon,m.kind==='trade'?'Intercambiado':'Fósil']);
    for(const [key,p,where] of entries){
      if(!key||!p||p.egg||!versions[family].includes(p.origin_version)||
         ![undefined,'route'].includes(s.progress?.origins?.[key]))continue;
      const route=rows.find(r=>(r.ids||[r.id]).includes(p.met_location_id));
      if(!route)continue;
      const id=family+':'+route.id;
      if(!result.has(id))result.set(id,{id,name:route.name,order:route.story_order||route.id,candidates:new Map(),missed:false});
      const group=result.get(id);
      const dead=Boolean(s.progress?.deaths?.[key]),mark=s.progress?.route_marks?.[key];
      if(!group.candidates.has(key))group.candidates.set(key,{key,mon:p,where,
        status:dead?'Muerto':mark?.kind==='trade'?'Intercambiado':where==='Fósil'?'Fósil':where});
    }
    for(const missed of s.progress?.missed_routes||[]){
      const route=rows.find(r=>String(r.id)===String(missed)||(r.ids||[]).some(id=>String(id)===String(missed)));
      if(!route)continue;
      const id=family+':'+route.id;
      if(!result.has(id))result.set(id,{id,name:route.name,order:route.story_order||route.id,candidates:new Map(),missed:false});
      result.get(id).missed=true;
    }
    // Explicit previous selections remain visible if the current scan no longer
    // contains the capture; never substitute a different Pokémon silently.
    for(const id of Object.keys(member.links||{}))if(!result.has(id)){
      const route=rows.find(r=>family+':'+r.id===id);
      if(route)result.set(id,{id,name:route.name,order:route.story_order||route.id,candidates:new Map(),missed:false});
    }
    return result;
  }
  function groups(room,catalog){
    const indexes=room.members.map(m=>index(m,catalog)), all=new Map();
    for(const map of indexes)for(const [key,row] of map)if(!all.has(key))all.set(key,row);
    return [...all.values()].sort((a,b)=>a.id.split(':')[0].localeCompare(b.id.split(':')[0])||a.order-b.order).map(row=>({
      ...row,members:room.members.map((member,i)=>({member,row:indexes[i].get(row.id),
        selected:member.links?.[row.id]||'',compatible:row.id.startsWith(region(member.game)+':')}))
    }));
  }
  function create({el,action,showMember,backToLocal,catalog,propose,resetNotices,enabled}){
    const panel=el('room-panel');
    if(!panel)return null;
    let info=null,session='',selected='',seen=new Map(),busy=false;
    const node=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
    const button=(text,fn)=>{const n=node('button',text);n.type='button';n.onclick=fn;return n;};
    function setBusy(value){busy=value;for(const control of panel.querySelectorAll?.('button,select')||[])control.disabled=busy||Boolean(control.roomBlocked);el('room-new-run').disabled=busy;}
    function reset(){seen.clear();resetNotices();}
    function clear(){panel.hidden=true;if(session){reset();session='';selected='';info=null;el('companion-linked').className='';el('companion-share').closest('label').hidden=false;el('companion-copy').hidden=false;el('companion-joined-text').hidden=false;el('companion-leave').textContent='Desvincular y borrar datos de la pareja';el('companion-title').textContent='Sincronizar compañero';}}
    function routeFor(member,key){return Object.entries(member.links||{}).find(([,v])=>v===key)?.[0];}
    function valid(notice){
      if(!notice.roomSession)return true;
      if(!info?.configured||notice.roomSession!==session)return false;
      const m=info.room.members.find(m=>m.player_id===notice.playerId&&m.run_id===notice.runId);
      const own=info.room.members.find(m=>m.player_id===info.player_id);
      const entry=m?.state?.progress?.deaths?.[notice.pokemonKey];
      return Boolean(m?.online&&m?.source_live&&entry&&entry.source!=='soullink-response'&&
        String(entry.recorded_at||'')===notice.recordedAt&&m.links?.[notice.route]===notice.pokemonKey&&own?.links?.[notice.route]===notice.localKey);
    }
    function commandContext(notice){
      if(!notice.roomSession)return {};
      const own=info.room.members.find(m=>m.player_id===info.player_id);
      return {soullink_room:{session_id:info.room.session_id,epoch:info.room.epoch,local_run_id:own.run_id,
        player_id:notice.playerId,run_id:notice.runId,route:notice.route,pokemon_key:notice.pokemonKey,
        recorded_at:notice.recordedAt}};
    }
    function observe(){
      if(!info.configured)return;
      const own=info.room.members.find(m=>m.player_id===info.player_id);
      for(const m of info.room.members){
        if(m.player_id===info.player_id||!m.state)continue;
        const scope=m.player_id+'|'+m.run_id,deaths=m.state.progress?.deaths||{};
        const previous=seen.get(scope),current=new Set(Object.entries(deaths).map(([key,d])=>key+'|'+String(d.recorded_at||'')));
        seen.set(scope,current);
        if(!previous||!enabled())continue;
        for(const [key,d] of Object.entries(deaths)){
          const id=key+'|'+String(d.recorded_at||''),route=routeFor(m,key),localKey=own?.links?.[route];
          if(previous.has(id)||d.source==='soullink-response'||!route||!localKey||!m.online||!m.source_live)continue;
          propose({id:scope+'|'+id,remoteMon:d.pokemon,remoteGame:m.game,partnerName:m.name,
            remoteName:d.pokemon?.nickname||d.pokemon?.species||'Pokémon',localKey,
            roomSession:session,playerId:m.player_id,runId:m.run_id,pokemonKey:key,
            recordedAt:String(d.recorded_at||''),route});
        }
      }
    }
    function update(next){
      if(info?.room?.session_id===next.room.session_id&&info.room.epoch===next.room.epoch&&next.room.revision<info.room.revision)return;
      info=next;panel.hidden=false;
      const room=info.room,own=room.members.find(m=>m.player_id===info.player_id);
      const key=room.session_id+'|'+room.epoch+'|'+String(own?.run_id||'');
      if(key!==session){reset();session=key;selected='';backToLocal();}
      if(!info.configured)resetNotices();
      el('companion-setup').hidden=Boolean(info.configured);
      el('companion-linked').hidden=!info.configured;
      el('companion-linked').className='room-linked-controls';
      el('companion-share').value=info.invite_link||'';
      el('companion-share').closest('label').hidden=!info.invite_link;
      el('companion-copy').hidden=!info.invite_link;
      el('companion-joined-text').hidden=true;
      el('companion-leave').textContent=info.direct_role==='host'?'Cerrar sala':'Salir de la sala';
      el('companion-title').textContent='Sala Soul Link · '+room.capacity+' jugadores';
      el('companion-joined-text').textContent=`Sala de ${room.capacity} · ${room.members.length} plazas ocupadas`;
      el('companion-status').textContent=info.error||(!info.configured?'Última sala guardada · sin conexión':`Sala activa · ${room.members.filter(m=>m.online).length}/${room.capacity} conectados`);
      el('room-summary').textContent=`${info.configured?'Sala actual':'Historial de solo lectura'} · faltan ${room.capacity-room.members.length} jugadores`;
      el('room-host-actions').hidden=!info.configured||info.direct_role!=='host'||(room.members.length>=room.capacity&&!info.invite_link);
      el('room-invite').roomBlocked=room.members.length>=room.capacity;
      el('room-invite').disabled=busy||el('room-invite').roomBlocked;
      const roster=el('room-roster');roster.replaceChildren();
      for(const m of room.members){
        const card=node('article',undefined,'room-player');
        card.append(node('strong',m.name+(m.player_id===room.host_id?' · Host':'')+(m.player_id===info.player_id?' · Tú':'')));
        card.append(node('small',m.game));
        card.append(node('p',m.left?'Salió de la sala':!m.online?'Desconectado · última lectura':!m.source_live?'Conectado · lectura no actual':'Conectado · lectura actual','room-presence'));
        const team=node('ul',undefined,'room-team');
        for(const p of m.state?.party||[])if(p)team.append(node('li',`${p.nickname||p.species||'Pokémon'} · Nv. ${p.level??'?'} · PS ${p.hp??'?'}/${p.max_hp??'?'}`));
        if(!team.children.length)team.append(node('li','Esperando equipo'));
        card.append(team);
        if(m.player_id!==info.player_id&&m.state)card.append(button('Ver partida · solo lectura',()=>{selected=m.player_id;showMember(m,true);}));
        if(info.configured&&info.direct_role==='host'&&m.player_id!==info.player_id){
          card.append(button('Invitar a reconectar',()=>action('room_invite',{player_id:m.player_id})));
          card.append(button('Eliminar plaza',()=>{if(confirm('¿Eliminar la plaza de '+m.name+' y revocar su conexión?'))action('room_remove',{player_id:m.player_id});}));
        }
        roster.append(card);
      }
      const list=groups(room,catalog),table=el('room-groups');table.replaceChildren();
      const head=node('tr');head.append(node('th','Ruta / grupo'));
      for(const m of room.members)head.append(node('th',m.name));
      const thead=node('thead');thead.append(head);table.append(thead);const tbody=node('tbody');
      for(const group of list){
        const tr=node('tr');tr.append(node('th',group.name));
        for(const {member,row,selected:choice,compatible} of group.members){
          const td=node('td'),chosen=row?.candidates.get(choice);
          let text=!compatible?'Otro mapa · sin enlace':row?.missed?'Miss':choice?chosen?`${chosen.mon.nickname||chosen.mon.species} · ${chosen.status}`:'Captura enlazada · fuera de la lectura':'Esperando captura elegida';
          if(!member.online)text+=' · desconectado';
          td.append(node('span',text));
          if(compatible&&member.player_id===info.player_id&&info.configured){
            const select=node('select');select.setAttribute('aria-label','Tu captura en '+group.name);
            const empty=node('option','Sin enlace');empty.value='';select.append(empty);
            for(const c of row?.candidates.values()||[]){const option=node('option',`${c.mon.nickname||c.mon.species} · ${c.status}`);option.value=c.key;select.append(option);}
            if(choice&&!chosen){const option=node('option','Captura anterior · no sustituir');option.value=choice;select.append(option);}
            select.value=choice;select.roomBlocked=!own?.online||!own?.source_live;select.disabled=busy||select.roomBlocked;
            select.onchange=()=>action('room_link',{route:group.id,pokemon_key:select.value||null});td.append(select);
          }
          tr.append(td);
        }
        tbody.append(tr);
      }
      table.append(tbody);el('room-no-groups').hidden=list.length>0;
      const log=el('room-events');log.replaceChildren();
      const labels={joined:'Entró',left:'Salió',reconnected:'Reconectó',death:'Muerte registrada',revived:'Reanimación registrada',missed:'Ruta Miss',linked:'Captura enlazada',unlinked:'Enlace retirado'};
      for(const e of [...room.events].reverse().slice(0,30)){
        const m=room.members.find(m=>m.player_id===e.player_id&&m.run_id===e.run_id);
        log.append(node('li',`${m?.name||'Jugador anterior'} · ${labels[e.kind]||'Evento'}${e.route?' · '+(list.find(g=>g.id===e.route)?.name||catalog(m?.game).find(r=>String(r.id)===e.route)?.name||'Ruta registrada'):''}${e.pokemon_key?' · '+(m?.state?.progress?.deaths?.[e.pokemon_key]?.pokemon?.nickname||'Captura'):''}${e.response?' · respuesta Soul Link':''}`));
      }
      const viewed=room.members.find(m=>m.player_id===selected);
      if(viewed?.state)showMember(viewed,false);else if(selected){selected='';backToLocal();}
      observe();
      const scopes=new Set(room.members.map(m=>m.player_id+'|'+m.run_id));
      for(const key of seen.keys())if(!scopes.has(key))seen.delete(key);
      setBusy(busy);
    }
    el('room-invite').onclick=()=>action('room_invite');
    el('room-revoke').onclick=()=>action('room_revoke');
    el('room-new-run').onclick=()=>{if(confirm('¿Separar este reto del anterior para Soul Link? Tu progreso local no se borra y los enlaces de la sala anterior no se reutilizarán.'))action('room_new_run',{game:el('companion-game').value});};
    return {update,clear,reset,valid,setBusy,commandContext};
  }
  return {create,groups,index};
})();
