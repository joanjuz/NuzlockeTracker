'use strict';
/** Optional companion view: the existing views render either your state or the last saved partner snapshot. */
(() => {
  const el = id => document.getElementById(id);
  const toggle = el('companion-toggle');
  const dialog = el('companion-dialog');
  const indicator = el('companion-status');
  let remote = null;
  let viewingPartner = false;
  let lastUpdate = -1;
  let working = false;
  let snoozedEvent = null;
  let currentEvent = null;

  function asView(p) {
    if (!p?.state || p.state.schema_version !== 1) return null;
    const source = p.state;
    if (!['Ultra Sun 1.0', 'Ultra Moon 1.0'].includes(source.game) || !Array.isArray(source.party) || !source.boxes || !source.progress)
      return null;
    return {
      ...source, stale: true, demo: false, selected_box: 1, battle_hp: false,
      connection: {status:'disconnected', message: 'Última sesión de ' + p.name},
      scan: {active:false, completed:0}, box_verified: true,
    };
  }
  const stamp = ms => ms ? new Date(ms).toLocaleString('es-CR') : 'Aún no ha compartido una sesión';
  function updatePage(info) {
    const p = info.partner;
    if (info.default_worker_url && !el('companion-url').value) el('companion-url').value = info.default_worker_url;
    const hasPartner = Boolean(p);
    el('soul-link-enabled').checked = info.soul_link_enabled === true;
    const pending = info.soul_link_enabled ? info.pending_deaths || [] : [];
    currentEvent = pending[0] || null;
    el('soul-link-show').hidden = !currentEvent;
    const notice = el('soul-link-notice');
    notice.hidden = !currentEvent || snoozedEvent === currentEvent.id;
    if (currentEvent && !notice.hidden) {
      const source = currentEvent.pokemon || {};
      el('soul-link-death-name').textContent = (source.nickname || source.species || 'Pokémon') + ' de tu compañero';
      el('soul-link-death-route').textContent = 'Ruta: ' + (source.met_location || 'Sin lugar registrado');
      const options = (currentEvent.choices || []).filter(c => !c.already_dead);
      const select = el('soul-link-match');
      const previous = select.value;
      select.replaceChildren();
      for (const option of options) select.add(new Option(option.name + ' · ' + option.route, option.key));
      if (options.some(option=>option.key===previous)) select.value=previous;
      el('soul-link-match-label').hidden = options.length===0;
      el('soul-link-no-match').hidden = options.length!==0;
      el('soul-link-mark').disabled = options.length===0;
    }
    const snapshot = asView(p);
    const hasView = hasPartner && Boolean(snapshot);
    toggle.hidden = !hasPartner;
    toggle.textContent = viewingPartner ? '← Mi partida' : 'Compañero';
    el('companion-setup').hidden = Boolean(info.configured);
    el('companion-linked').hidden = !info.configured;
    if (info.configured) {
      const status = hasPartner ? `Sincronizado con ${p.name} · ${p.game}` : 'Esperando a tu compañero';
      el('companion-joined-text').textContent = status + (p?.updated_at ? ` · ${stamp(p.updated_at)}` : '');
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
    try {
      const response = await fetch('/api/companion', {cache:'no-store'});
      if (!response.ok) throw Error('No se pudo consultar la sincronización local');
      updatePage(await response.json());
    } catch (error) {
      indicator.textContent = error.message;
    }
  }
  async function action(actionName, extra = {}) {
    if (working) return;
    working = true;
    for(const id of ['companion-create','companion-join','companion-refresh','companion-leave','soul-link-ignore','soul-link-mark']) el(id).disabled = true;
    indicator.textContent = 'Procesando…';
    try {
      if (!token) throw Error('Espera a que conecte el servidor local.');
      const response = await fetch('/api/companion', {
        method:'POST',headers:{'Content-Type':'application/json','X-Tracker-Token':token},
        body:JSON.stringify({action:actionName,...extra}),
      });
      const body = await response.json();
      if (!response.ok) throw Error(body.error || 'No se completó la operación');
      if (actionName === 'leave') {viewingPartner = false;remote = null;window.setCompanionView(false);snoozedEvent=null;}
      if (actionName === 'death_decision') snoozedEvent=null;
      updatePage(body);
    } catch(error) {
      indicator.textContent = error.message;
    } finally {
      el('companion-setup-key').value = '';
      working = false;
      for(const id of ['companion-create','companion-join','companion-refresh','companion-leave','soul-link-ignore','soul-link-mark']) el(id).disabled = false;
    }
  }
  el('soul-link-enabled').onchange = () => action('soul_link',{enabled:el('soul-link-enabled').checked});
  el('soul-link-dismiss').onclick = () => {if(currentEvent){snoozedEvent=currentEvent.id;el('soul-link-notice').hidden=true}};
  el('soul-link-show').onclick = () => {snoozedEvent=null;el('soul-link-notice').hidden=!currentEvent;dialog.close();getStatus()};
  el('soul-link-ignore').onclick = () => {if(currentEvent)action('death_decision',{event_id:currentEvent.id,decision:'ignore'})};
  el('soul-link-mark').onclick = () => {if(currentEvent)action('death_decision',{event_id:currentEvent.id,decision:'mark',pokemon_key:el('soul-link-match').value})};
  const fields = () => ({
    worker_url:el('companion-url').value.trim(),
    name:el('companion-name').value.trim(),
    game:el('companion-game').value,
  });
  el('open-companion').onclick = () => {
    document.querySelectorAll('details[open]').forEach(d => d.open = false);
    dialog.showModal();getStatus();
  };
  el('companion-close').onclick = () => dialog.close();
  el('companion-create').onclick = () => action('create', {...fields(),setup_key:el('companion-setup-key').value});
  el('companion-join').onclick = () => action('join', {...fields(),invite_code:el('companion-invite').value.trim()});
  el('companion-refresh').onclick = () => action('refresh');
  el('companion-leave').onclick = () => {
    if (confirm('¿Desvincular la pareja y eliminar todas las sesiones compartidas de Cloudflare?')) action('leave');
  };
  el('companion-copy').onclick = async () => {
    const code = el('companion-share').value;
    if (code && navigator.clipboard) {
      try {await navigator.clipboard.writeText(code);indicator.textContent = 'Código copiado. Envíalo de forma privada.';}
      catch(error) {indicator.textContent = 'Selecciona el texto y cópialo manualmente.';}
    }
  };
  toggle.onclick = () => {
    if (viewingPartner) {viewingPartner = false;window.setCompanionView(false);}
    else if (remote) {viewingPartner = true;window.setCompanionView(true,remote);}
    else {indicator.textContent='Esperando la primera sesión del compañero.';dialog.showModal();}
    toggle.textContent = viewingPartner?'← Mi partida':'Compañero';
  };
  getStatus();
  setInterval(getStatus, 5000);
})();
