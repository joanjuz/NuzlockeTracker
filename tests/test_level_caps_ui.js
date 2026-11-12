'use strict';
// Level caps UI (web/app/progress.js) in a fake DOM: chip, card labels, Progreso view, editor and leave guard.
const assert = require('node:assert/strict');
const vm = require('node:vm');
const {loadShared, scripts} = require('./ui_shared.js');

class El {
  constructor(id) {
    Object.assign(this, {id, innerHTML: '', textContent: '', hidden: false, disabled: false, open: false, dataset: {},
      attributes: {}, listeners: {}, value: '', checked: false});
  }
  setAttribute(k, v) { this.attributes[k] = String(v); }
  getAttribute(k) { return this.attributes[k] ?? null; }
  addEventListener(type, fn) { (this.listeners[type] ??= []).push(fn); }
  querySelector() { return null; }
  showModal() { this.open = true; }
  close() { this.open = false; }
}

function load({companion = false} = {}) {
  const nodes = {}, commands = [], posts = [], tabs = [], timers = [];
  const $ = id => nodes[id] ??= new El(id);
  for (const id of ['level-cap-chip', 'progress-unsaved', 'caps-current', 'caps-editor', 'caps-editor-state',
    'caps-editor-status', 'level-caps-leave-dialog', 'level-caps-leave-keep', 'level-caps-leave-discard']) $(id);
  const windowListeners = {};
  const ctx = {
    $, companionView: companion, state: null, token: 't', console,
    setText: (node, text) => { if (node.textContent !== text) node.textContent = text; },
    command: async cmd => commands.push(cmd), switchTab: tab => tabs.push(tab),
    setTimeout: fn => timers.push(fn),
    fetch: async (url, options) => { posts.push({url, body: JSON.parse(options.body)}); return {ok: ctx.reply.ok, json: async () => ctx.reply.body}; },
    reply: {ok: true, body: {ok: true}},
    window: {addEventListener: (type, fn) => { windowListeners[type] = fn; }},
  };
  vm.createContext(ctx);
  loadShared(ctx, ['esc', 'num', 'list']);
  vm.runInContext(scripts['app/progress.js'], ctx, {filename: 'web/app/progress.js'});
  return {ctx, $, nodes, commands, posts, tabs, timers, windowListeners,
    run: code => vm.runInContext(code, ctx)};
}

const stage = (id, name, cap) => ({id, name, cap});
// Objects created inside the vm belong to another realm: compare their JSON form.
const plain = value => JSON.parse(JSON.stringify(value));
function caps({stages = [stage('a', 'Gimnasio 1', 14), stage('b', 'Gimnasio 2', 20), stage('c', 'Liga', 50)],
  current = 'b', show = true, removed = null, status = 'ok'} = {}) {
  const index = stages.findIndex(s => s.id === current);
  return {status, configured: stages.length > 0, show, stages, current: index >= 0 ? current : null,
    current_index: index >= 0 ? index : null, current_cap: index >= 0 ? stages[index].cap : null,
    current_name: index >= 0 ? stages[index].name : null, total: stages.length, decreasing: [],
    removed_current: removed, rejected_kept: false};
}
const mon = (nickname, level, extra = {}) => ({species: 'Especie', nickname, level, ...extra});
const snapshot = (levelCaps, party = [mon('Brote', 22), mon('Chispa', 20), mon('Huevo', 30, {egg: true}), null, null, null]) =>
  ({level_caps: levelCaps, party});
// Fake click/input events with the shape capsClick/capsInput read (closest, dataset).
function click(act, key) {
  const row = key ? {dataset: {key}} : null;
  const target = {dataset: {act}, disabled: false, closest: sel => sel === '[data-act]' ? target : row};
  return {target};
}
function input(key, field, value) {
  return {target: {value, dataset: {field}, closest: () => ({dataset: {key}})}};
}

(async () => {
  // --- Header chip rules.
  {
    const {ctx} = load();
    const chip = s => ctx.levelCapChip(s, false);
    assert.equal(chip(snapshot(undefined)), null, 'Sin datos: sin chip');
    assert.equal(chip(snapshot({...caps(), status: 'none', total: 0})), null);
    assert.equal(chip(snapshot(caps({stages: []}))), null, 'Sin etapas: chip oculto');
    assert.equal(chip(snapshot(caps({show: false}))), null, 'show=false oculta el chip');
    assert.equal(chip(snapshot({...caps(), status: 'unsupported'})), null);
    const neutral = chip(snapshot(caps({current: null})));
    assert.deepEqual([neutral.kind, neutral.text], ['neutral', 'Sin etapa vigente']);
    const warn = chip(snapshot(caps()));
    assert.equal(warn.kind, 'warn');
    assert.equal(warn.text, 'Límite Nv. 20 · Gimnasio 2 · 1 por encima', 'El huevo y quien está en el límite no cuentan');
    assert.match(warn.label, /1 Pokémon del equipo lo supera/);
    const ok = chip(snapshot(caps(), [mon('Brote', 20), null, null, null, null, null]));
    assert.deepEqual([ok.kind, ok.text], ['ok', 'Límite Nv. 20 · Gimnasio 2']);
    assert.equal(ctx.levelCapChip(snapshot(caps()), true), null, 'Vista del compañero: sin chip');
  }

  // --- Chip rendering, card labels and signature.
  {
    const {ctx, $, run} = load();
    ctx.state = snapshot(caps({stages: [stage('a', '<img src=x onerror=alert(1)>', 10)], current: 'a'}));
    run('renderLevelCapIndicators(state)');
    assert.equal($('level-cap-chip').hidden, false);
    assert.equal($('level-cap-chip').innerHTML, '', 'El nombre se escribe como texto, nunca como HTML');
    assert.equal($('level-cap-chip').dataset.kind, 'warn');
    assert.match($('level-cap-chip').attributes['aria-label'], /Abrir Progreso/);
    assert.equal(ctx.overCapLabel(mon('Brote', 22)), '<span class="over-cap" title="Aviso informativo: el límite vigente es 10">+12 sobre el límite</span>');
    assert.equal(ctx.overCapLabel(mon('Brote', 10)), '');
    assert.equal(ctx.overCapLabel(mon('Huevo', 50, {egg: true})), '');
    assert.equal(ctx.overCapLabel(null), '');
    assert.equal(ctx.levelCapSignature(), '10');
    ctx.state = snapshot(caps({show: false}));
    run('renderLevelCapIndicators(state)');
    assert.equal($('level-cap-chip').hidden, true);
    assert.equal(ctx.overCapLabel(mon('Brote', 99)), '', 'show=false: sin etiquetas en las fichas');
    assert.equal(ctx.levelCapSignature(), '-');
    ctx.state = snapshot(caps({current: null}));
    assert.equal(ctx.overCapLabel(mon('Brote', 99)), '', 'Sin etapa vigente: sin etiquetas');
    $('level-cap-chip').listeners.click[0]();
  }
  {
    const {ctx, tabs} = load({companion: true});
    ctx.state = snapshot(caps());
    assert.equal(ctx.overCapLabel(mon('Brote', 99)), '');
    assert.deepEqual(tabs, []);
  }

  // --- Row validation, warnings and payload (same rules as the backend).
  {
    const {ctx} = load();
    const problem = (name, cap) => ctx.stageProblem({name, cap});
    assert.match(problem('', '10'), /Escribe un nombre/);
    assert.match(problem('   ', '10'), /Escribe un nombre/);
    assert.match(problem('x'.repeat(61), '10'), /Máximo 60/);
    assert.equal(problem('x'.repeat(60), '10'), '');
    assert.match(problem('a\nb', '10'), /no válidos/);
    assert.match(problem('a b', '10'), /no válidos/);
    for (const cap of ['', '0', '101', '1.5', 'abc', ' ', '-3'])
      assert.match(problem('Liga', cap), /entre 1 y 100/, 'Límite inválido: ' + JSON.stringify(cap));
    assert.equal(problem('  Liga  ', ' 50 '), '');
    assert.equal(problem('Liga', 100), '');
    const rows = [{key: 'a', id: 'a', name: 'A', cap: '20'}, {key: 'b', id: 'b', name: 'B', cap: '15'},
      {key: 'nueva-1', id: null, name: ' C ', cap: '30'}, {key: 'nueva-2', id: null, name: 'D', cap: '5'}];
    assert.deepEqual([...ctx.decreasingKeys(rows)], ['b', 'nueva-2'], 'Los límites decrecientes solo se avisan');
    assert.deepEqual(JSON.parse(JSON.stringify(ctx.stagesPayload(rows))), [{id: 'a', name: 'A', cap: 20}, {id: 'b', name: 'B', cap: 15},
      {name: 'C', cap: 30}, {name: 'D', cap: 5}]);
    assert.equal(ctx.draftDiffers([{id: 'a', name: ' A ', cap: '20'}], [stage('a', 'A', 20)]), false);
    assert.equal(ctx.draftDiffers([{id: 'a', name: 'A', cap: '21'}], [stage('a', 'A', 20)]), true);
  }

  // --- Progreso view: current stage, position, progress bar, navigation and explicit selection.
  {
    const {ctx, $, run, commands} = load();
    ctx.state = snapshot(caps());
    run('renderProgress()');
    const html = $('caps-current').innerHTML;
    assert.match(html, /Nv\. 20/);
    assert.match(html, /Etapa 2 de 3/);
    assert.match(html, /role="progressbar"[^>]*aria-valuenow="2"/);
    assert.match(html, /width:67%/);
    assert.match(html, /data-act="previous">Etapa anterior/);
    assert.match(html, /data-act="next">Siguiente etapa/);
    assert.match(html, /<option value="b" selected>2\. Gimnasio 2 · Nv\. 20<\/option>/);
    assert.match(html, /Brote<\/span><span>Nv\. 22<\/span><strong>\+2 sobre el límite/);
    assert.match(html, /Dentro del límite/);
    assert.match(html, /id="caps-show" checked/);
    ctx.capsClick(click('next'));
    ctx.capsClick(click('previous'));
    assert.deepEqual(plain(commands), [{action: 'level_caps_current', stage: 'c'}, {action: 'level_caps_current', stage: 'a'}],
      'Navegación reversible por ID estable');
    ctx.capsChange({target: {id: 'caps-select', value: ''}});
    ctx.capsChange({target: {id: 'caps-show', checked: false}});
    assert.deepEqual(plain(commands.slice(2)), [{action: 'level_caps_current', stage: null}, {action: 'level_caps_show', show: false}]);
    assert.equal($('caps-editor').hidden, false);
    assert.match($('caps-editor').innerHTML, /aria-label="Nombre de la etapa 2"/);
    assert.match($('caps-editor').innerHTML, /data-act="save" disabled/, 'Sin cambios no se puede guardar');

    // No current stage after removing it: explicit notice and no neighbour selected.
    ctx.state = snapshot(caps({current: null, removed: stage('b', 'Gimnasio 2', 20)}));
    run('renderProgress()');
    const none = $('caps-current').innerHTML;
    assert.match(none, /Sin etapa vigente/);
    assert.match(none, /Se eliminó la etapa vigente «Gimnasio 2» \(Nv\. 20\)/);
    assert.match(none, /data-act="previous" disabled/);
    assert.match(none, /data-act="next" disabled/);
    assert.match(none, /<option value="">Sin etapa vigente<\/option><option value="a">/);
    assert.doesNotMatch(none, /Equipo frente al límite/);

    // Hostile names are escaped everywhere.
    ctx.state = snapshot(caps({stages: [stage('a', '<b onclick=x>"', 10)], current: 'a'}));
    run('renderProgress()');
    assert.doesNotMatch($('caps-current').innerHTML + $('caps-editor').innerHTML, /<b onclick/);
    assert.match($('caps-editor').innerHTML, /value="&lt;b onclick=x&gt;&quot;"/);

    // Data from a newer tracker: kept, not editable.
    ctx.state = snapshot({...caps(), status: 'unsupported'});
    run('renderProgress()');
    assert.match($('caps-current').innerHTML, /versión más nueva/);
    assert.equal($('caps-editor').hidden, true);
  }

  // --- Empty state, first stage, validation next to the row and atomic save.
  {
    const {ctx, $, run, posts, timers} = load();
    ctx.state = snapshot({...caps({stages: []}), status: 'none'});
    run('renderProgress()');
    assert.match($('caps-current').innerHTML, /Añadir la primera etapa/);
    assert.equal($('caps-editor').hidden, true);
    ctx.capsClick(click('add-first'));
    assert.equal(run('capsDraft.length'), 1);
    assert.equal($('caps-editor').hidden, false);
    assert.doesNotMatch($('caps-current').innerHTML, /data-act="add-first"/, 'Sin botón duplicado mientras hay borrador');
    await ctx.saveLevelCaps();
    assert.equal(posts.length, 0, 'Una fila inválida no se envía');
    assert.match($('caps-editor').innerHTML, /aria-invalid="true" aria-describedby="caps-error-nueva-1"/);
    assert.match($('caps-editor').innerHTML, /id="caps-error-nueva-1">Escribe un nombre\./);
    assert.match($('caps-editor-status').textContent, /una etapa con errores/);
    ctx.capsInput(input('nueva-1', 'name', 'Primer gimnasio'));
    ctx.capsInput(input('nueva-1', 'cap', '14'));
    assert.equal(run('Object.keys(capsErrors).length'), 0, 'Corregir la fila retira su error');
    assert.equal(ctx.levelCapsDirty(), true);
    await ctx.saveLevelCaps();
    assert.deepEqual(posts.at(-1).body, {action: 'level_caps_set', stages: [{name: 'Primer gimnasio', cap: 14}]},
      'Guardar envía la lista completa en una sola orden, sin elegir etapa vigente');
    assert.equal($('caps-editor-status').textContent, 'Etapas guardadas.');
    // The draft ends when the new list arrives.
    ctx.state = snapshot(caps({stages: [stage('id1', 'Primer gimnasio', 14)], current: null}));
    run('renderLevelCapIndicators(state)');
    assert.equal(run('capsDraft'), null);
    assert.equal(timers.length, 1);
  }

  // --- Reorder keeps ids, removing the current stage explains the outcome, discard restores.
  {
    const {ctx, $, run, posts} = load();
    ctx.state = snapshot(caps());
    run('renderProgress()');
    ctx.capsClick(click('down', 'a'));
    assert.deepEqual(JSON.parse(JSON.stringify(run('capsDraft.map(r=>r.id)'))), ['b', 'a', 'c']);
    assert.match($('caps-editor-status').textContent, /posición 2/);
    assert.equal($('progress-unsaved').hidden, false, 'La pestaña marca cambios sin guardar');
    ctx.capsClick(click('remove', 'b'));
    assert.match($('caps-editor-status').textContent, /quedará sin etapa vigente/);
    ctx.capsInput(input('c', 'cap', '12'));
    assert.match($('caps-editor').innerHTML, /data-note="c"/);
    await ctx.saveLevelCaps();
    assert.deepEqual(posts.at(-1).body.stages, [{id: 'a', name: 'Gimnasio 1', cap: 14}, {id: 'c', name: 'Liga', cap: 12}],
      'Las etapas existentes conservan su ID; los límites decrecientes se guardan');
    ctx.reply = {ok: false, body: {error: 'El límite de nivel debe ser un entero entre 1 y 100.'}};
    run('capsSaving=null');
    await ctx.saveLevelCaps();
    assert.match($('caps-editor-status').textContent, /No se guardó: El límite de nivel/);
    assert.equal(ctx.levelCapsDirty(), true, 'Un error del servidor conserva el borrador');
    ctx.capsClick(click('discard'));
    assert.equal(run('capsDraft'), null);
    assert.equal(ctx.levelCapsDirty(), false);
    // Editing a value without moving rows does not rebuild the table; discarding must rebuild it.
    ctx.capsInput(input('a', 'name', 'Renombrada'));
    ctx.capsClick(click('discard'));
    assert.match($('caps-editor').innerHTML, /value="Gimnasio 1"/);
    assert.doesNotMatch($('caps-editor').innerHTML, /Renombrada/);
  }

  // --- Limit of 64 stages in the editor.
  {
    const {ctx, $, run} = load();
    const many = Array.from({length: 64}, (_, i) => stage('s' + i, 'Etapa ' + i, i + 1));
    ctx.state = snapshot(caps({stages: many, current: 's0'}));
    run('renderProgress()');
    assert.match($('caps-editor').innerHTML, /data-act="add" disabled/);
    assert.match($('caps-editor').innerHTML, /64 de 64 etapas/);
    ctx.capsClick(click('add'));
    assert.equal(run('capsDraft.length'), 64);
  }

  // --- Leaving with unsaved stages asks first; tab changes never discard.
  {
    const {ctx, $, run, windowListeners} = load();
    ctx.state = snapshot(caps());
    assert.equal(await ctx.confirmLevelCapsLeave(), true, 'Sin cambios no pregunta');
    run('renderProgress()');
    ctx.capsInput(input('a', 'name', 'Renombrada'));
    const event = {preventDefault() { this.prevented = true; }};
    windowListeners.beforeunload(event);
    assert.equal(event.prevented, true, 'Cerrar o recargar con cambios pide confirmación');
    const kept = ctx.confirmLevelCapsLeave();
    assert.equal($('level-caps-leave-dialog').open, true);
    $('level-caps-leave-keep').listeners.click[0]();
    assert.equal(await kept, false);
    assert.equal(run('capsDraft[0].name'), 'Renombrada', 'Volver al editor conserva el borrador');
    const discarded = ctx.confirmLevelCapsLeave();
    $('level-caps-leave-discard').listeners.click[0]();
    assert.equal(await discarded, true);
    assert.equal(run('capsDraft'), null);
    const after = {preventDefault() { this.prevented = true; }};
    windowListeners.beforeunload(after);
    assert.equal(after.prevented, undefined);
  }

  // --- Switching or creating a run with unsaved stages asks first (profiles.js uses the same guard).
  {
    const {ctx, $, run, posts} = load();
    for (const id of ['run-profile', 'new-run-profile', 'run-profile-controls', 'delete-run-profile', 'run-profile-dialog',
      'run-profile-feedback', 'run-profile-name', 'run-profile-close', 'run-profile-form', 'status']) $(id);
    $('run-profile').replaceChildren = () => {};
    ctx.Option = function (text, value) { this.text = text; this.value = value; };
    ctx.location = {reload() { ctx.reloaded = true; }};
    vm.runInContext(scripts['app/profiles.js'], ctx, {filename: 'web/app/profiles.js'});
    await ctx.loadRunProfiles({profiles: [{id: 'principal', name: 'Principal'}, {id: 'otra', name: 'Otra'}], active: 'principal'});
    ctx.state = snapshot(caps());
    run('renderProgress()');
    ctx.capsInput(input('a', 'cap', '15'));
    $('run-profile').value = 'otra';
    const switching = $('run-profile').onchange();
    assert.equal($('level-caps-leave-dialog').open, true, 'Cambiar de partida con cambios pregunta antes');
    $('level-caps-leave-keep').listeners.click[0]();
    await switching;
    assert.equal($('run-profile').value, 'principal', 'Cancelar deja la partida actual seleccionada');
    assert.equal(posts.length, 0, 'No se pidió el cambio de partida');
    const creating = $('new-run-profile').onclick();
    assert.equal($('level-caps-leave-dialog').open, true);
    $('level-caps-leave-keep').listeners.click[0]();
    await creating;
    assert.equal($('run-profile-dialog').open, false, 'Crear una partida también espera la confirmación');
    assert.equal(run('capsDraft[0].cap'), '15');
  }

  console.log('Límites de nivel: chip, fichas, vista Progreso, editor, validación y protección de cambios OK');
})().catch(error => { console.error(error); process.exitCode = 1; });
