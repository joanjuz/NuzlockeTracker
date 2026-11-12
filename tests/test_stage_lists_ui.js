'use strict';
// Reusable stage lists (web/app/stage-lists.js) in a fake DOM: format, validation, preview,
// explicit replacement, cancellation, unsaved drafts and failures. Nothing changes until «Importar».
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
  const nodes = {}, commands = [], posts = [], downloads = [];
  const $ = id => nodes[id] ??= new El(id);
  for (const id of ['caps-current', 'caps-editor', 'caps-editor-state', 'caps-editor-status', 'level-cap-chip', 'progress-unsaved',
    'caps-export', 'caps-import', 'caps-import-file', 'caps-lists-hint', 'caps-lists-status', 'caps-lists-error',
    'level-caps-import-dialog', 'level-caps-import-body', 'level-caps-import-cancel', 'level-caps-import-apply',
    'level-caps-leave-dialog', 'level-caps-leave-keep', 'level-caps-leave-discard']) $(id);
  const ctx = {
    $, companionView: false, state: null, token: 't', console,
    setText: (node, text) => { if (node.textContent !== text) node.textContent = text; },
    command: async cmd => commands.push(cmd), switchTab: () => {},
    setTimeout: fn => fn,
    fetch: async (url, options) => { posts.push({url, body: JSON.parse(options.body)}); return {ok: ctx.reply.ok, json: async () => ctx.reply.body}; },
    reply: {ok: true, body: {ok: true}},
    window: {addEventListener() {}},
    Blob: class { constructor(parts, options) { this.parts = parts; this.options = options; } },
    URL: {createObjectURL: blob => { downloads.push(blob); return 'blob:x'; }, revokeObjectURL() {}},
    document: {createElement: () => ({click() { downloads[downloads.length - 1].link = this; }, remove() {}}), body: {appendChild() {}}},
  };
  vm.createContext(ctx);
  loadShared(ctx, ['esc', 'num', 'list']);
  vm.runInContext(scripts['app/progress.js'], ctx, {filename: 'web/app/progress.js'});
  vm.runInContext(scripts['app/stage-lists.js'], ctx, {filename: 'web/app/stage-lists.js'});
  return {ctx, $, nodes, commands, posts, downloads, run: code => vm.runInContext(code, ctx)};
}

const stage = (id, name, cap) => ({id, name, cap});
const plain = value => JSON.parse(JSON.stringify(value));
function caps({stages = [stage('a', 'Gimnasio 1', 14), stage('b', 'Gimnasio 2', 20)], current = 'b', show = false, status = 'ok'} = {}) {
  const index = stages.findIndex(s => s.id === current);
  return {status, configured: stages.length > 0, show, stages, current: index >= 0 ? current : null,
    current_index: index >= 0 ? index : null, current_cap: index >= 0 ? stages[index].cap : null,
    current_name: index >= 0 ? stages[index].name : null, total: stages.length, decreasing: [], removed_current: null, rejected_kept: false};
}
const snapshot = levelCaps => ({level_caps: levelCaps, party: []});
const fileOf = (text, name = 'etapas.json', size = text.length) => ({name, size, text: async () => text});
const valid = (stages = [{name: 'Liga', cap: 50}]) => JSON.stringify({format: 'progressive-tracker-stage-list', version: 1, stages});
const click = (act, key) => { const row = key ? {dataset: {key}} : null; const t = {dataset: {act}, disabled: false, closest: s => s === '[data-act]' ? t : row}; return {target: t}; };

(async () => {
  // --- Format: only names, caps and order; roundtrip; no ids, current stage or options.
  {
    const {ctx} = load();
    const doc = plain(ctx.stageListDocument([stage('abc', 'Gimnasio 1', 14), {id: 'zzz', name: 'Liga', cap: 50, current: true, show: true}]));
    assert.deepEqual(doc, {format: 'progressive-tracker-stage-list', version: 1,
      stages: [{name: 'Gimnasio 1', cap: 14}, {name: 'Liga', cap: 50}]});
    const text = ctx.stageListText([stage('abc', 'Gimnasio 1', 14), stage('def', 'Liga', 50)]);
    for (const secret of ['abc', 'def', 'current', 'show', 'token', 'path', 'death']) assert.ok(!text.includes(secret), secret);
    assert.ok(text.endsWith('\n'));
    const parsed = ctx.parseStageList(text);
    assert.equal(parsed.ok, true);
    assert.deepEqual(plain(parsed.stages), [{name: 'Gimnasio 1', cap: 14}, {name: 'Liga', cap: 50}], 'Roundtrip');
    assert.deepEqual(plain(parsed.warnings), []);
    assert.equal(ctx.parseStageList('\uFEFF' + valid()).ok, true, 'BOM tolerado');
    assert.deepEqual(plain(ctx.parseStageList(valid([{name: '  Liga  ', cap: 50}])).stages), [{name: 'Liga', cap: 50}], 'Nombres recortados');
    // Decreasing caps: allowed, reported.
    const down = ctx.parseStageList(valid([{name: 'A', cap: 30}, {name: 'B', cap: 20}, {name: 'C', cap: 25}]));
    assert.equal(down.ok, true);
    assert.equal(down.warnings.length, 1);
    assert.match(down.warnings[0], /etapa 2 «B» \(Nv\. 20\).*inferior.*\(Nv\. 30\).*solo un aviso/);
    // Boundaries accepted.
    const many = Array.from({length: 64}, (_, i) => ({name: 'x'.repeat(i === 0 ? 60 : 1), cap: i === 1 ? 1 : 100}));
    assert.equal(ctx.parseStageList(valid(many)).ok, true, '64 etapas, nombre de 60 y límites 1 y 100');
  }

  // --- Errors: clear messages, never a partial list.
  {
    const {ctx} = load();
    const err = (text, pattern, label) => {
      const result = ctx.parseStageList(text);
      assert.equal(result.ok, false, label);
      assert.match(result.errors.join(' '), pattern, label);
      assert.equal(result.stages, undefined, label + ': sin lista parcial');
    };
    err('{ no es json', /no es un JSON válido/, 'JSON dañado');
    err('', /no es un JSON válido/, 'vacío');
    for (const wrong of ['[]', 'null', '7', '"x"', '{}', '{"format":"otra","version":1,"stages":[]}'])
      err(wrong, /no es una lista de etapas de Progressive Tracker/, wrong);
    const doc = patch => JSON.stringify({format: 'progressive-tracker-stage-list', version: 1, stages: [{name: 'A', cap: 5}], ...patch});
    err(doc({version: 2}), /versión 2 .* solo entiende la 1\. Actualiza el tracker/, 'versión futura');
    err(doc({version: 99}), /versión 99/, 'versión futura lejana');
    for (const v of [0, -1, 1.5, '1', null, true]) err(doc({version: v}), /versión del archivo no es válida/, 'versión ' + JSON.stringify(v));
    err(doc({id: 'x'}), /campos que este formato no admite: «id»/, 'campo de más');
    err(doc({exported_at: 'hoy', path: 'C:\\Users\\x'}), /«exported_at», «path»/, 'campos de más');
    err(doc({stages: 'x'}), /no contiene una lista de etapas/, 'stages no es lista');
    err(doc({stages: []}), /no tiene ninguna etapa/, 'lista vacía');
    err(doc({stages: Array.from({length: 65}, () => ({name: 'A', cap: 5}))}), /65 etapas; el máximo es 64/, '65 etapas');
    err(doc({stages: [{name: 'A', cap: 5, id: 'x'}]}), /Etapa 1: campos no admitidos \(«id»\)/, 'ids internos rechazados');
    err(doc({stages: [{name: 'A', cap: 5, current: true}]}), /campos no admitidos/, 'etapa vigente rechazada');
    err(doc({stages: [null]}), /Etapa 1: formato no válido/, 'etapa nula');
    err(doc({stages: [['A', 5]]}), /Etapa 1: formato no válido/, 'etapa como array');
    err(doc({stages: [{cap: 5}]}), /Etapa 1: falta el nombre/, 'sin nombre');
    err(doc({stages: [{name: '   ', cap: 5}]}), /falta el nombre/, 'nombre en blanco');
    err(doc({stages: [{name: 5, cap: 5}]}), /falta el nombre/, 'nombre numérico');
    err(doc({stages: [{name: 'x'.repeat(61), cap: 5}]}), /supera 60 caracteres/, 'nombre largo');
    err(doc({stages: [{name: 'a\nb', cap: 5}]}), /caracteres no válidos/, 'caracteres de control');
    for (const cap of [0, 101, -1, 20.5, '20', true, null, undefined, 1e9])
      err(doc({stages: [{name: 'A', cap}]}), /límite debe ser un número entero entre 1 y 100/, 'límite ' + JSON.stringify(cap));
    err(doc({stages: [{name: 'A', cap: 5}, {name: '', cap: 5}, {name: 'C', cap: 500}]}), /Etapa 2: falta el nombre\. Etapa 3: el límite/, 'varios problemas, todos indicados');
    const bad = ctx.parseStageList(doc({stages: Array.from({length: 20}, () => ({name: '', cap: 5}))}));
    assert.equal(bad.errors.length, 7, 'Se limita la lista de problemas');
    assert.match(bad.errors.at(-1), /y 14 problemas más/);
    err('x'.repeat(33 * 1024), /demasiado grande .* 32 KB/, 'tamaño');
    err(undefined, /No se pudo leer/, 'sin texto');
  }

  // --- Toolbar rules.
  {
    const {ctx, $, run} = load();
    ctx.state = snapshot(caps());
    run('renderLevelCapIndicators(state)');
    assert.equal($('caps-export').disabled, false);
    assert.equal($('caps-import').disabled, false);
    assert.equal($('caps-lists-hint').textContent, '');
    ctx.state = snapshot(caps({stages: []}));
    run('renderLevelCapIndicators(state)');
    assert.equal($('caps-export').disabled, true, 'Sin etapas no hay nada que exportar');
    assert.equal($('caps-import').disabled, false, 'Sin etapas se puede importar');
    assert.match($('caps-lists-hint').textContent, /aún no tiene etapas/);
    ctx.state = snapshot({status: 'unsupported'});
    run('renderLevelCapIndicators(state)');
    assert.deepEqual([$('caps-export').disabled, $('caps-import').disabled], [true, true]);
    assert.match($('caps-lists-hint').textContent, /versión más nueva/);
    ctx.state = snapshot(caps());
    run('renderProgress()');
    ctx.capsClick(click('add'));
    run('renderLevelCapIndicators(state)');
    assert.equal($('caps-import').disabled, true, 'Con borrador sin guardar no se puede importar');
    assert.equal($('caps-export').disabled, false, 'Se exporta la lista guardada');
    assert.match($('caps-lists-hint').textContent, /cambios sin guardar/);
  }

  // --- Export: native dialog in the desktop window; normal download in a browser. The saved list only.
  {
    const {ctx, $, run, downloads} = load();
    ctx.state = snapshot(caps());
    run('renderProgress()');
    ctx.capsInput({target: {value: 'Borrador', dataset: {field: 'name'}, closest: () => ({dataset: {key: 'a'}})}});
    await ctx.exportStageList();
    assert.equal(downloads.length, 1);
    assert.equal(downloads[0].options.type, 'application/json');
    assert.equal(downloads[0].link.download, 'limites-de-nivel.json');
    const text = downloads[0].parts[0];
    assert.deepEqual(plain(JSON.parse(text).stages), [{name: 'Gimnasio 1', cap: 14}, {name: 'Gimnasio 2', cap: 20}], 'El borrador no se exporta');
    assert.match($('caps-lists-status').textContent, /Lista exportada \(2 etapas\) como limites-de-nivel\.json/);
    ctx.window.pywebview = {api: {save_export: async kind => { ctx.kind = kind; return {saved: true, name: 'mis-etapas.json'}; }}};
    await ctx.exportStageList();
    assert.equal(ctx.kind, 'level_caps', 'El escritorio usa el diálogo nativo');
    assert.equal(downloads.length, 1);
    assert.match($('caps-lists-status').textContent, /Lista exportada: mis-etapas\.json/);
    ctx.window.pywebview = {api: {save_export: async () => ({error: 'Disco lleno'})}};
    await ctx.exportStageList();
    assert.match($('caps-lists-error').textContent, /No se pudo exportar: Disco lleno/);
    ctx.window.pywebview = {api: {save_export: async () => ({cancelled: true})}};
    await ctx.exportStageList();
    assert.match($('caps-lists-status').textContent, /cancelada/);
    ctx.state = snapshot(caps({stages: []}));
    await ctx.exportStageList();
    assert.match($('caps-lists-error').textContent, /No hay etapas guardadas/);
  }

  // --- Import with an existing list: preview first, explicit confirmation, atomic command, new ids.
  {
    const {ctx, $, run, posts} = load();
    ctx.state = snapshot(caps({show: false}));
    run('renderLevelCapIndicators(state)');
    ctx.chooseStageList();
    assert.equal($('caps-import-file').clicks, 1, 'Importar abre el selector de archivos');
    $('caps-import-file').files = [fileOf(valid([{name: '<img src=x onerror=alert(1)>', cap: 30}, {name: 'Liga', cap: 25}]))];
    await ctx.stageListFileChosen();
    const dialog = $('level-caps-import-dialog'), body = $('level-caps-import-body').innerHTML;
    assert.equal(dialog.open, true);
    assert.equal(posts.length, 0, 'La vista previa no cambia nada');
    assert.ok(!body.includes('<img'), 'Nombres escapados');
    assert.match(body, /&lt;img src=x onerror=alert\(1\)&gt;/);
    assert.match(body, /Nv\. 30/);
    assert.match(body, /Nv\. 25/);
    assert.match(body, /inferior al de la anterior/, 'Advertencia de límite decreciente');
    assert.match(body, /Ninguna etapa quedará vigente/);
    assert.match(body, /Esta partida ya tiene 2 etapas.*la vigente es «Gimnasio 2»/);
    assert.match(body, /se reemplazan por completo/);
    assert.match(body, /level-caps-import-confirm/);
    assert.equal($('level-caps-import-apply').disabled, true, 'Reemplazar exige confirmación explícita');
    assert.equal($('level-caps-import-apply').textContent, 'Reemplazar la lista');
    assert.equal($('caps-import').disabled, true, 'No se abren dos importaciones a la vez');
    await ctx.applyStageImport();
    assert.equal(posts.length, 0, 'Sin confirmar no se aplica aunque se fuerce');
    assert.match($('level-caps-import-error').textContent, /Confirma que quieres reemplazar/);
    $('level-caps-import-confirm').checked = true;
    $('level-caps-import-body').fire('change', {target: $('level-caps-import-confirm')});
    assert.equal($('level-caps-import-apply').disabled, false);
    await ctx.applyStageImport();
    assert.equal(posts.length, 1, 'Una sola orden atómica con la lista completa');
    assert.equal(posts[0].url, '/api/command');
    assert.deepEqual(plain(posts[0].body), {action: 'level_caps_set',
      stages: [{name: '<img src=x onerror=alert(1)>', cap: 30}, {name: 'Liga', cap: 25}]},
    'Sin ids, sin etapa vigente y sin la opción de mostrar');
    assert.equal(dialog.open, false);
    assert.match($('caps-lists-status').textContent, /Lista importada: 2 etapas\. Elige la etapa vigente/);
    assert.equal(run('stageImport'), null);
  }

  // --- Import into an empty run: no replacement confirmation; cancelling changes nothing.
  {
    const {ctx, $, run, posts} = load();
    ctx.state = snapshot(caps({stages: []}));
    run('renderLevelCapIndicators(state)');
    $('caps-import-file').files = [fileOf(valid())];
    await ctx.stageListFileChosen();
    assert.ok(!$('level-caps-import-body').innerHTML.includes('level-caps-import-confirm'));
    assert.equal($('level-caps-import-apply').disabled, false);
    assert.equal($('level-caps-import-apply').textContent, 'Importar lista');
    $('level-caps-import-cancel').fire('click');
    assert.equal($('level-caps-import-dialog').open, false);
    assert.equal(posts.length, 0, 'Cancelar no envía nada');
    assert.match($('caps-lists-status').textContent, /Importación cancelada: no se cambió nada/);
    assert.equal(run('stageImport'), null);
    // Escape behaves like Cancel.
    await ctx.stageListFileChosen();
    assert.equal($('level-caps-import-dialog').open, true);
    let prevented = false;
    $('level-caps-import-dialog').fire('cancel', {preventDefault() { prevented = true; }});
    assert.equal(prevented, true);
    assert.equal($('level-caps-import-dialog').open, false);
    assert.equal(posts.length, 0);
    await ctx.stageListFileChosen();
    await ctx.applyStageImport();
    assert.equal(posts.length, 1);
    assert.deepEqual(plain(posts[0].body.stages), [{name: 'Liga', cap: 50}]);
  }

  // --- Unsaved draft: importing never discards it silently.
  {
    const {ctx, $, run, posts} = load();
    ctx.state = snapshot(caps());
    run('renderProgress()');
    ctx.capsInput({target: {value: '99', dataset: {field: 'cap'}, closest: () => ({dataset: {key: 'a'}})}});
    assert.equal(run('levelCapsDirty()'), true);
    ctx.chooseStageList();
    assert.equal($('caps-import-file').clicks, 0, 'No se abre el selector con un borrador sin guardar');
    assert.match($('caps-lists-error').textContent, /Guarda o descarta los cambios/);
    $('caps-import-file').files = [fileOf(valid())];
    await ctx.stageListFileChosen();
    assert.equal($('level-caps-import-dialog').open, false, 'Tampoco se abre la vista previa');
    assert.equal(run('capsDraft[0].cap'), '99', 'El borrador sigue intacto');
    // A draft started while a preview is open (another window) blocks the apply.
    ctx.discardLevelCaps();
    await ctx.stageListFileChosen();
    assert.equal($('level-caps-import-dialog').open, true);
    ctx.capsInput({target: {value: '77', dataset: {field: 'cap'}, closest: () => ({dataset: {key: 'a'}})}});
    $('level-caps-import-confirm').checked = true;
    await ctx.applyStageImport();
    assert.equal(posts.length, 0);
    assert.match($('level-caps-import-error').textContent, /cambios sin guardar/);
    assert.equal(run('capsDraft[0].cap'), '77');
    assert.equal($('level-caps-import-dialog').open, true);
  }

  // --- The saved list changing during the preview refuses a stale import.
  {
    const {ctx, $, run, posts} = load();
    ctx.state = snapshot(caps());
    run('renderLevelCapIndicators(state)');
    $('caps-import-file').files = [fileOf(valid())];
    await ctx.stageListFileChosen();
    $('level-caps-import-confirm').checked = true;
    ctx.state = snapshot(caps({stages: [stage('z', 'Otra', 5)], current: 'z'}));
    await ctx.applyStageImport();
    assert.equal(posts.length, 0);
    assert.match($('level-caps-import-error').textContent, /cambiaron mientras revisabas/);
  }

  // --- Failure: previous configuration stays, the preview stays open to retry or cancel.
  {
    const {ctx, $, run, posts} = load();
    ctx.state = snapshot(caps());
    run('renderLevelCapIndicators(state)');
    $('caps-import-file').files = [fileOf(valid())];
    await ctx.stageListFileChosen();
    $('level-caps-import-confirm').checked = true;
    ctx.reply = {ok: false, body: {error: 'Como máximo 64 etapas por partida y juego.'}};
    await ctx.applyStageImport();
    assert.equal(posts.length, 1);
    assert.match($('level-caps-import-error').textContent, /No se importó y la lista anterior se conserva: Como máximo 64/);
    assert.equal($('level-caps-import-dialog').open, true);
    assert.equal($('level-caps-import-apply').disabled, false, 'Se puede reintentar');
    assert.deepEqual(plain(run('savedStages(state)')), [{id: 'a', name: 'Gimnasio 1', cap: 14}, {id: 'b', name: 'Gimnasio 2', cap: 20}]);
    ctx.reply = {ok: true, body: {ok: true}};
    $('level-caps-import-cancel').fire('click');
    assert.equal($('level-caps-import-dialog').open, false);
  }

  // --- Rejected files: clear message with the file name, no preview, nothing sent.
  {
    const {ctx, $, run, posts} = load();
    ctx.state = snapshot(caps());
    run('renderLevelCapIndicators(state)');
    $('caps-import-file').files = [fileOf('{ roto', 'roto.json')];
    await ctx.stageListFileChosen();
    assert.match($('caps-lists-error').textContent, /No se importó «roto\.json»: El archivo no es un JSON válido/);
    $('caps-import-file').files = [fileOf(valid(), 'grande.json', 33 * 1024)];
    await ctx.stageListFileChosen();
    assert.match($('caps-lists-error').textContent, /demasiado grande .* 32 KB/);
    $('caps-import-file').files = [fileOf(JSON.stringify({format: 'progressive-tracker-stage-list', version: 3, stages: []}), 'futuro.json')];
    await ctx.stageListFileChosen();
    assert.match($('caps-lists-error').textContent, /versión 3/);
    $('caps-import-file').files = [{name: 'x.json', size: 10, text: async () => { throw Error('denegado'); }}];
    await ctx.stageListFileChosen();
    assert.match($('caps-lists-error').textContent, /no se pudo leer el archivo/);
    assert.equal($('level-caps-import-dialog').open, false);
    assert.equal(posts.length, 0);
    assert.equal($('caps-lists-status').textContent, '', 'El error sustituye al mensaje de éxito');
  }

  // --- The page wiring: markup, accessibility and the existing level-caps UI left alone.
  {
    const html = require('node:fs').readFileSync(require('node:path').join(__dirname, '../web/index.html'), 'utf8');
    for (const id of ['caps-lists', 'caps-export', 'caps-import', 'caps-import-file', 'caps-lists-hint', 'caps-lists-status', 'caps-lists-error',
      'level-caps-import-dialog', 'level-caps-import-body', 'level-caps-import-cancel', 'level-caps-import-apply'])
      assert.ok(html.includes('id="' + id + '"'), id);
    assert.match(html, /id="caps-lists-error"[^>]*role="alert"/);
    assert.match(html, /id="caps-lists-status"[^>]*role="status"/);
    assert.match(html, /<dialog id="level-caps-import-dialog" aria-labelledby="level-caps-import-title">/);
    assert.match(html, /<input type="file" id="caps-import-file" accept="\.json,application\/json" hidden/);
  }

  console.log('Listas de etapas: formato, validación, vista previa, reemplazo explícito, cancelación, borradores y errores OK');
})().catch(error => { console.error(error); process.exitCode = 1; });
