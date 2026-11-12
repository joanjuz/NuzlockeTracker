'use strict';
// Level caps proposed by Definitive Randomizer (web/app/caps-proposal.js) in a fake DOM: the Progreso
// card, the review with its comparison, explicit acceptance and replacement, the optional final stage,
// keeping or dismissing, stale reviews and unsaved drafts. Nothing is sent until the player accepts.
const assert = require('node:assert/strict');
const vm = require('node:vm');
const {loadShared, scripts} = require('./ui_shared.js');

class El {
  constructor(id) {
    Object.assign(this, {id, innerHTML: '', textContent: '', hidden: false, disabled: false, open: false, dataset: {},
      attributes: {}, listeners: {}, value: '', checked: false, files: [], clicks: 0, focused: 0});
  }
  setAttribute(k, v) { this.attributes[k] = String(v); }
  addEventListener(type, fn) { (this.listeners[type] ??= []).push(fn); }
  querySelector() { return null; }
  showModal() { this.open = true; }
  close() { this.open = false; }
  click() { this.clicks += 1; }
  focus() { this.focused += 1; }
  fire(type, event = {}) { for (const fn of this.listeners[type] ?? []) fn({target: this, preventDefault() {}, ...event}); }
}

function load() {
  const nodes = {}, posts = [];
  const $ = id => nodes[id] ??= new El(id);
  const ctx = {
    $, companionView: false, state: null, token: 't', console,
    setText: (node, text) => { if (node.textContent !== text) node.textContent = text; },
    command: async () => {}, switchTab: () => {}, setTimeout: fn => fn,
    fetch: async (url, options) => { posts.push({url, body: JSON.parse(options.body)}); return {ok: ctx.reply.ok, json: async () => ctx.reply.body}; },
    reply: {ok: true, body: {ok: true}},
    window: {addEventListener() {}},
  };
  vm.createContext(ctx);
  loadShared(ctx, ['esc', 'num', 'list']);
  for (const file of ['app/progress.js', 'app/stage-lists.js', 'app/caps-proposal.js'])
    vm.runInContext(scripts[file], ctx, {filename: 'web/' + file});
  return {ctx, $, nodes, posts, run: code => vm.runInContext(code, ctx)};
}

const plain = value => JSON.parse(JSON.stringify(value));
const stage = (id, name, cap) => ({id, name, cap});
function caps({stages = [], current = null, show = true, status = 'ok', revision = 'rev-' + stages.map(s => s.id).join('')} = {}) {
  const index = stages.findIndex(s => s.id === current);
  return {status, configured: stages.length > 0, show, stages, current: index >= 0 ? current : null,
    current_index: index >= 0 ? index : null, current_cap: index >= 0 ? stages[index].cap : null,
    current_name: index >= 0 ? stages[index].name : null, total: stages.length, decreasing: [], removed_current: null,
    rejected_kept: false, revision};
}
const flag = (byte, mask) => ({kind: 'event-flag-set', byte, mask});
function proposal(points = [['Clear Normal Trial - Ilima (1dom)', 15, 'Event Flag · byte 0x0010, máscara 0x08'],
  [null, 50, 'Event Flag · byte 0x0150, máscara 0x04'], ['Defeat Champion Hau (Tilo)', 70, 'Event Work 68 ≥ 2000']]) {
  const checkpoints = points.map(([label, cap, text], i) => ({order: i + 1, cap, condition: flag(i, 1), label,
    name: label || text, conditionText: text}));
  return {state: 'proposal', status: 'installed', reason: null, detail: null, hooks: {battleCro: 'applied', codeBin: 'applied'},
    fingerprint: 'B'.repeat(64), tableSha256: 'C'.repeat(64), ceiling: 100, count: checkpoints.length, maxStages: 64,
    checkpoints, stages: checkpoints.map(p => ({name: p.name, cap: p.cap}))};
}
const source = (extra = {}) => ({accepted: null, dismissed: null, error: null, matchesCurrent: false, ...extra});
function snapshot({levelCaps = caps(), block = proposal(), levelCapsSource = source(), game = 'Ultra Moon 1.0', fingerprint = 'A'.repeat(64)} = {}) {
  return {game, party: [], level_caps: levelCaps, level_caps_source: levelCapsSource,
    game_data: {loaded: block !== null, active: block !== null, game, fingerprint,
      producer: {id: 'DefinitiveRandomizer', version: '1.2.3'}, levelCaps: block}};
}
const click = act => { const t = {dataset: {act}, disabled: false, closest: s => s === '[data-act]' ? t : null}; return {target: t}; };
const accepted = (extra = {}) => ({source: 'definitive-game-data', blockVersion: 1, producer: {id: 'DefinitiveRandomizer', version: '1.2.3'},
  game: 'Ultra Moon 1.0', dataFingerprint: 'A'.repeat(64), capsFingerprint: 'B'.repeat(64), tableSha256: 'C'.repeat(64), checkpoints: 3,
  finalStage: false, listRevision: 'rev', acceptedAt: '2026-11-12T05:00:00+00:00', ...extra});

(async () => {
  // --- Pure model: when a card is shown and what it offers.
  {
    const {ctx, run} = load();
    const model = (snap, partner = false) => { ctx.snap = snap; ctx.partner = partner; return plain(run('capsProposalModel(snap,partner)')); };
    assert.equal(model(snapshot({block: null})).kind, 'hidden', 'Sin datos importados no hay tarjeta');
    assert.equal(model(snapshot({block: {...proposal(), state: 'absent'}})).kind, 'hidden', 'Un DGD sin bloque no muestra nada');
    assert.equal(model(snapshot(), true).kind, 'hidden', 'La vista del compañero no muestra la propuesta');
    assert.equal(model(snapshot({levelCaps: caps({status: 'unsupported'})})).kind, 'hidden');
    const offered = model(snapshot());
    assert.deepEqual([offered.kind, offered.review, offered.dismiss, offered.restore ?? false], ['proposal', true, true, false]);
    assert.match(offered.text, /3 puntos de Player Level Caps, de Nv\. 15 a Nv\. 70/);
    assert.match(offered.text, /no etapas de tu desafío/);
    assert.match(offered.text, /No se ha cambiado nada/);
    for (const [state, reason] of [['unavailable', 'El proyecto exportado no tiene instalado el parche'], ['ignored', 'formato más nuevo'], ['rejected', 'No se recorta']]) {
      const notice = model(snapshot({block: {...proposal(), state, stages: [], reason, detail: state === 'unavailable' ? 'detalle técnico' : null}}));
      assert.deepEqual([notice.kind, notice.text, notice.review ?? false], ['notice', reason, false], state + ' informa sin ofrecer lista');
    }
    const inUse = model(snapshot({levelCaps: caps({stages: [stage('a', 'Clear Normal Trial - Ilima (1dom)', 15)]}), levelCapsSource: source({accepted: accepted(), matchesCurrent: true})}));
    assert.deepEqual([inUse.kind, inUse.dismiss ?? false], ['accepted', false]);
    assert.match(inUse.text, /2026-11-12/);
    assert.match(inUse.text, /No se han editado/);
    const edited = model(snapshot({levelCaps: caps({stages: [stage('a', 'Editada', 16)]}), levelCapsSource: source({accepted: accepted(), matchesCurrent: false})}));
    assert.equal(edited.kind, 'proposal', 'Tras editar la lista, la propuesta se puede revisar de nuevo');
    assert.match(edited.origin, /se editaron a mano/);
    const otherTable = model(snapshot({levelCapsSource: source({accepted: accepted({tableSha256: 'D'.repeat(64)}), matchesCurrent: true})}));
    assert.equal(otherTable.kind, 'proposal', 'Otra tabla del parche es otra propuesta');
    const set_aside = model(snapshot({levelCapsSource: source({dismissed: {capsFingerprint: 'B'.repeat(64), tableSha256: 'C'.repeat(64), dismissedAt: '2026-11-12T06:00:00+00:00'}})}));
    assert.deepEqual([set_aside.kind, set_aside.restore, set_aside.dismiss ?? false], ['dismissed', true, false]);
    const kept = caps({stages: [stage('a', 'Clear Normal Trial - Ilima (1dom)', 15)]});
    const withdrawn = model(snapshot({block: null, levelCaps: kept, levelCapsSource: source({accepted: accepted({finalStage: true}), matchesCurrent: true})}));
    assert.equal(withdrawn.kind, 'origin');
    assert.match(withdrawn.text, /etapa final de Nv\. 100/);
    assert.match(withdrawn.text, /las etapas se conservan/);
    assert.equal(model(snapshot({block: null, levelCapsSource: source({error: 'No se pudo leer la procedencia'})})).kind, 'notice');
    assert.equal(model(snapshot({block: null, levelCapsSource: source({accepted: accepted()})})).kind, 'hidden', 'Sin etapas no hay origen que contar');

    // Comparison and the optional final stage.
    ctx.block = proposal(); ctx.saved = [{name: 'Clear Normal Trial - Ilima (1dom)', cap: 15}, {name: 'Mi etapa', cap: 30}];
    const rows = plain(run('proposalComparison(block,saved,false)'));
    assert.equal(rows.length, 3);
    assert.deepEqual([rows[0].same, rows[1].same, rows[2].now], [true, false, null]);
    assert.deepEqual([rows[0].labelled, rows[1].labelled], [true, false], 'Una condición fuera del catálogo no tiene nombre de catálogo');
    assert.equal(rows[1].next.name, 'Event Flag · byte 0x0150, máscara 0x04');
    const withFinal = plain(run('proposalComparison(block,saved,true)'));
    assert.deepEqual([withFinal.length, withFinal[3].next.cap, withFinal[3].derived], [4, 100, true]);
    assert.equal(plain(run('proposalStages(block,false)')).length, 3, 'La etapa final no se añade sola');
    ctx.full = proposal(Array.from({length: 64}, (_, i) => ['P' + i, 10, 'c' + i]));
    assert.equal(run('finalStageAllowed(full)'), false, 'Con 64 puntos no cabe la etapa final');
    assert.equal(run('finalStageAllowed(block)'), true);
  }

  // --- Card: review, keep and accept into a run without stages.
  {
    const {ctx, $, posts, run} = load();
    ctx.state = snapshot();
    run('renderProgress()');
    const card = $('caps-proposal'), dialog = $('level-caps-proposal-dialog'), body = $('level-caps-proposal-body'), apply = $('level-caps-proposal-apply');
    assert.equal(card.hidden, false);
    assert.equal(card.dataset.kind, 'proposal');
    assert.match(card.innerHTML, /data-act="review"[^>]*>Revisar propuesta…/);
    assert.match(card.innerHTML, /Descartar propuesta/);
    card.fire('click', click('review'));
    assert.equal(dialog.open, true);
    assert.match(body.innerHTML, /restricciones mecánicas del juego/);
    assert.match(body.innerHTML, /Comparación con las etapas actuales/);
    assert.match(body.innerHTML, /Sin nombre en el catálogo · Event Flag · byte 0x0150, máscara 0x04/);
    assert.match(body.innerHTML, /Ninguna etapa quedará vigente/);
    assert.match(body.innerHTML, /Hash de la tabla del parche/);
    assert.match(body.innerHTML, /no comprueban la ROM que ejecuta el emulador/);
    assert.ok(!/id="level-caps-proposal-final" checked/.test(body.innerHTML), 'La etapa final empieza desmarcada');
    assert.ok(!body.innerHTML.includes('level-caps-proposal-confirm'), 'Sin etapas no se pide confirmar un reemplazo');
    assert.equal(apply.disabled, false);
    assert.equal(apply.textContent, 'Aceptar la propuesta');
    assert.equal(posts.length, 0, 'Revisar no envía nada');
    $('level-caps-proposal-keep').fire('click');
    assert.equal(dialog.open, false);
    assert.equal(posts.length, 0, 'Conservar no envía nada');
    assert.match(card.innerHTML, /Se conservan los límites actuales: no se cambió nada/);
    $('level-caps-proposal-dialog').open = false;
    card.fire('click', click('review'));
    dialog.fire('cancel');
    assert.equal(dialog.open, false, 'Esc conserva los límites actuales');
    assert.equal(posts.length, 0);

    card.fire('click', click('review'));
    await run('acceptCapsProposal()');
    assert.equal(posts.length, 1);
    assert.deepEqual(plain(posts[0].body), {action: 'level_caps_accept_proposal', game: 'Ultra Moon 1.0', dataFingerprint: 'A'.repeat(64),
      capsFingerprint: 'B'.repeat(64), tableSha256: 'C'.repeat(64), finalStage: false, replace: false, listRevision: 'rev-'});
    assert.ok(!('stages' in posts[0].body) && !('current' in posts[0].body), 'El servidor construye las etapas; nunca se elige vigente');
    assert.equal(dialog.open, false);
    assert.match(card.innerHTML, /Propuesta aceptada: 3 etapas\. Ninguna quedó vigente/);
  }

  // --- Replacement needs an explicit confirmation; the final stage is opt-in.
  {
    const {ctx, $, posts, run} = load();
    ctx.state = snapshot({levelCaps: caps({stages: [stage('a', 'Gimnasio 1', 14), stage('b', 'Gimnasio 2', 20)], current: 'b'})});
    run('renderProgress()');
    const body = $('level-caps-proposal-body'), apply = $('level-caps-proposal-apply'), confirm = $('level-caps-proposal-confirm'), final = $('level-caps-proposal-final');
    $('caps-proposal').fire('click', click('review'));
    assert.match(body.innerHTML, /ya tiene 2 etapas/);
    assert.match(body.innerHTML, /la vigente es «Gimnasio 2»/);
    assert.match(body.innerHTML, /Gimnasio 1/);
    assert.equal(apply.disabled, true, 'Sin confirmar no se puede reemplazar');
    assert.equal(apply.textContent, 'Aceptar y reemplazar las etapas');
    await run('acceptCapsProposal()');
    assert.equal(posts.length, 0);
    assert.equal($('level-caps-proposal-error').textContent, 'Confirma que quieres reemplazar las etapas actuales.');
    final.checked = true;
    body.fire('change', {target: final});
    assert.match(body.innerHTML, /Después del último punto \(techo del parche\)<\/span><strong>Nv\. 100/);
    assert.match(body.innerHTML, /id="level-caps-proposal-final" checked/);
    confirm.checked = true;
    body.fire('change', {target: confirm});
    assert.equal(apply.disabled, false);
    await run('acceptCapsProposal()');
    assert.deepEqual([posts[0].body.finalStage, posts[0].body.replace, posts[0].body.listRevision], [true, true, 'rev-ab']);
    assert.match($('caps-proposal').innerHTML, /Propuesta aceptada: 4 etapas/);
    // A new review never inherits the option.
    final.checked = false; confirm.checked = false;
    $('caps-proposal').fire('click', click('review'));
    assert.ok(!/id="level-caps-proposal-final" checked/.test(body.innerHTML));
  }

  // --- A full list leaves no room for the final stage.
  {
    const {ctx, $, run} = load();
    ctx.state = snapshot({block: proposal(Array.from({length: 64}, (_, i) => ['P' + i, 10, 'c' + i]))});
    run('renderProgress()');
    $('caps-proposal').fire('click', click('review'));
    assert.match($('level-caps-proposal-body').innerHTML, /id="level-caps-proposal-final" disabled/);
    assert.match($('level-caps-proposal-body').innerHTML, /ya tiene el máximo de 64 etapas/);
  }

  // --- Unsaved drafts are protected and a stale review cannot be accepted.
  {
    const {ctx, $, posts, run} = load();
    ctx.state = snapshot({levelCaps: caps({stages: [stage('a', 'Gimnasio 1', 14)]})});
    run('renderProgress()');
    const card = $('caps-proposal'), dialog = $('level-caps-proposal-dialog'), apply = $('level-caps-proposal-apply'), error = $('level-caps-proposal-error');
    run("capsDraft=[{key:'a',id:'a',name:'Editada',cap:'14'}];renderProgress()");
    assert.match(card.innerHTML, /data-act="review"[^>]* disabled/);
    assert.match(card.innerHTML, /cambios sin guardar en las etapas/);
    run('openCapsProposal()');
    assert.equal(dialog.open, false, 'Con borrador no se abre la revisión');
    run('capsDraft=null;renderProgress()');
    card.fire('click', click('review'));
    assert.equal(dialog.open, true);
    $('level-caps-proposal-confirm').checked = true;
    run('updateCapsProposalApply()');
    assert.equal(apply.disabled, false);

    const stale = async (change, message) => {
      const before = ctx.state;
      ctx.state = change(plain(before));
      run('renderLevelCapIndicators(state)');
      assert.equal(apply.disabled, true, message);
      assert.match(error.textContent, new RegExp(message));
      await run('acceptCapsProposal()');
      assert.equal(posts.length, 0, 'Una revisión obsoleta no envía nada: ' + message);
      ctx.state = before;
      run('renderLevelCapIndicators(state)');
      assert.equal(error.textContent, '');
      assert.equal(apply.disabled, false, 'Vuelve a ser válida al coincidir de nuevo');
    };
    await stale(s => { s.game_data.fingerprint = 'F'.repeat(64); return s; }, 'datos importados cambiaron');
    await stale(s => { s.game_data.levelCaps.tableSha256 = 'F'.repeat(64); return s; }, 'datos importados cambiaron');
    await stale(s => { s.game = 'Ultra Sun 1.0'; return s; }, 'datos importados cambiaron');
    await stale(s => { s.game_data.active = false; return s; }, 'datos importados cambiaron');
    await stale(s => { s.level_caps = caps({stages: [stage('a', 'Gimnasio 1', 15)], revision: 'rev-a'}); return s; }, 'etapas de la partida cambiaron');
    await stale(s => { s.level_caps.revision = 'otra'; return s; }, 'etapas de la partida cambiaron');
    run("capsDraft=[{key:'a',id:'a',name:'Otra',cap:'14'}];renderLevelCapIndicators(state)");
    assert.equal(apply.disabled, true);
    assert.match(error.textContent, /cambios sin guardar/);
    await run('acceptCapsProposal()');
    assert.equal(posts.length, 0);
    run('capsDraft=null;renderLevelCapIndicators(state)');

    // A backend refusal keeps the review open and the previous list intact.
    ctx.reply = {ok: false, body: {error: 'La propuesta que revisaste ya no es la vigente'}};
    await run('acceptCapsProposal()');
    assert.equal(posts.length, 1);
    assert.equal(dialog.open, true);
    assert.match(error.textContent, /No se aceptó y las etapas anteriores se conservan: La propuesta que revisaste/);
    assert.equal(apply.disabled, false);
  }

  // --- Dismiss and bring back; hostile text is escaped.
  {
    const {ctx, $, posts, run} = load();
    ctx.state = snapshot({block: proposal([['<img src=x onerror=alert(1)>', 20, '<b>cond</b>']])});
    run('renderProgress()');
    const card = $('caps-proposal');
    card.fire('click', click('dismiss'));
    await Promise.resolve(); await Promise.resolve(); await Promise.resolve();
    assert.deepEqual(plain(posts[0].body), {action: 'level_caps_dismiss_proposal', game: 'Ultra Moon 1.0', dataFingerprint: 'A'.repeat(64),
      capsFingerprint: 'B'.repeat(64), tableSha256: 'C'.repeat(64), dismissed: true});
    ctx.state = snapshot({block: ctx.state.game_data.levelCaps,
      levelCapsSource: source({dismissed: {capsFingerprint: 'B'.repeat(64), tableSha256: 'C'.repeat(64), dismissedAt: '2026-11-12T06:00:00+00:00'}})});
    run('renderProgress()');
    assert.equal(card.dataset.kind, 'dismissed');
    assert.match(card.innerHTML, /Volver a mostrarla/);
    await run('dismissCapsProposal(false)');
    assert.equal(posts[1].body.dismissed, false);
    card.fire('click', click('review'));
    const body = $('level-caps-proposal-body').innerHTML;
    assert.ok(!body.includes('<img src=x') && !body.includes('<b>cond</b>'), 'Los nombres del archivo se escapan');
    assert.ok(body.includes('&lt;img src=x onerror=alert(1)&gt;'));
    await run('dismissFromReview()');
    assert.equal($('level-caps-proposal-dialog').open, false);
    assert.equal(posts[2].body.dismissed, true);
    ctx.reply = {ok: false, body: {error: 'fallo'}};
    await run('dismissCapsProposal(true)');
    assert.match(card.innerHTML, /No se pudo guardar la decisión: fallo/);
  }

  // --- Diagnostics and partner view.
  {
    const {ctx, $, run} = load();
    ctx.state = snapshot({block: {...proposal(), state: 'unavailable', status: 'inconsistent', stages: [], checkpoints: [],
      reason: 'Las dos copias del parche no coinciden.', detail: 'Battle.cro tiene el parche y code.bin no.'}});
    run('renderProgress()');
    const card = $('caps-proposal');
    assert.equal(card.dataset.kind, 'notice');
    assert.match(card.innerHTML, /Las dos copias del parche no coinciden/);
    assert.match(card.innerHTML, /Detalle del Randomizer: Battle\.cro tiene el parche/);
    assert.ok(!card.innerHTML.includes('data-act='), 'Un estado no instalado no ofrece acciones');
    run('openCapsProposal()');
    assert.equal($('level-caps-proposal-dialog').open, false);
    ctx.companionView = true;
    ctx.state = snapshot();
    run('renderProgress()');
    assert.equal(card.hidden, true);
  }
  console.log('Propuesta de límites de Definitive Randomizer: tarjeta, revisión, aceptación, reemplazo, descarte y revisiones obsoletas OK');
})().catch(error => { console.error(error); process.exit(1); });
