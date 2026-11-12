'use strict';
// The tracker UI ships as classic scripts that share one global scope. Check
// their load order, load them all together in a fake DOM and exercise the item
// icons and the update notice.
const assert = require('node:assert/strict');
const vm = require('node:vm');
const {APP_SCRIPTS, read, scripts, slice} = require('./ui_shared.js');

const html = read('index.html');
const HOSTILE = '<img src=x onerror=alert(1)>';

// --- Load order and CSP: only external scripts, analysis.js before the tracker, app.js last.
assert.deepEqual(APP_SCRIPTS, ['app/helpers.js', 'app/profiles.js', 'app/team.js', 'app/detail.js', 'app/boxes.js',
  'app/dead.js', 'app/routes.js', 'app/progress.js', 'app/analysis-view.js', 'app/connection.js', 'app/shell.js',
  'app/companion-loader.js', 'app/update-notice.js', 'app.js']);
const tags = html.match(/<script\b[^>]*>/g);
assert.ok(tags.every(tag => /\ssrc="\/[\w/.-]+\.js"/.test(tag)), 'Sin scripts en línea (CSP script-src self)');
assert.ok(!/<script\b[^>]*>[^<]+<\/script>/.test(html), 'Ningún script con contenido en línea');
assert.ok(!/\son[a-z]+=/i.test(html), 'Sin manejadores de eventos en línea');
assert.ok(html.indexOf('src="/analysis.js"') < html.indexOf('src="/app/helpers.js"'));
for (const [file, code] of Object.entries(scripts)) {
  new vm.Script(code, {filename: 'web/' + file});
  assert.ok(code.startsWith("'use strict';"), file + ' en modo estricto');
  assert.ok(!/^\s*(import|export)\s/m.test(code), file + ' es un script clásico, no un módulo');
}
// Top-level names must be unique across files: a repeated let/const breaks the whole script.
const declared = new Map();
for (const [file, code] of Object.entries(scripts)) {
  for (const match of code.matchAll(/^(?:async function|function|const|let)\s+([\w$]+)/gm)) {
    assert.ok(!declared.has(match[1]), match[1] + ' declarado en ' + declared.get(match[1]) + ' y en ' + file);
    declared.set(match[1], file);
  }
}

// --- Whole UI in one shared scope, as the browser runs it.
class El {
  constructor(tag, id) {
    Object.assign(this, {tagName: String(tag).toUpperCase(), id, children: [], options: [], dataset: {}, style: {}, attributes: {},
      innerHTML: '', textContent: '', value: '', hidden: false, disabled: false, checked: false, open: false, listeners: []});
    const names = new Set();
    this.classList = {toggle: (n, on) => (on ?? !names.has(n)) ? names.add(n) : names.delete(n), add: n => names.add(n),
      remove: n => names.delete(n), contains: n => names.has(n)};
  }
  setAttribute(k, v) { this.attributes[k] = String(v); }
  getAttribute(k) { return this.attributes[k] ?? null; }
  removeAttribute(k) { delete this.attributes[k]; }
  append(...items) { this.children.push(...items); }
  replaceChildren(...items) { this.children = items; }
  add(option) { this.options.push(option); }
  addEventListener(type, fn) { this.listeners.push([type, fn]); }
  contains() { return false; }
  querySelector() { return null; }
  showModal() { this.open = true; }
  close() { this.open = false; }
  scrollBy() {}
}
function loadAll({storage = {}, update = {current: '1.0.0', latest: null, update_available: false}} = {}) {
  const nodes = {}, docListeners = [], requests = [], intervals = [];
  const $ = id => nodes[id] ??= new El(/^(box|game|mode|theme|analysis-\w+)$/.test(id) ? 'select' : 'div', id);
  const ctx = {
    console, Option: function (text, value) { this.text = text; this.value = String(value); },
    setTimeout: () => 0, clearTimeout() {}, setInterval: (fn, ms) => intervals.push([fn, ms]), confirm: () => false,
    localStorage: storage === null ? {getItem() { throw Error('Bloqueado'); }, setItem() { throw Error('Bloqueado'); }}
      : {getItem: k => storage[k] ?? null, setItem: (k, v) => { storage[k] = String(v); }},
    location: {host: 'localhost', origin: 'http://localhost', reload() {}},
    WebSocket: function () { ctx.socket = this; this.close = () => {}; },
    fetch: async (url, options) => {
      requests.push(url);
      const replies = {'/api/session': {token: 't', version: '1.0.0'}, '/api/profiles': {profiles: [], active: 'principal'},
        '/api/analysis': {types: [], chart: {}}, '/api/state': {game: 'Ultra Moon 1.0', party: Array(6).fill(null), boxes: {}, progress: {},
          connection: {status: 'disconnected', message: 'Sin conexión'}, scan: {active: false, completed: 0}}, '/api/templates': {counts: {}}, '/api/update': update};
      if (update instanceof Error && url === '/api/update') throw update;
      const known = Object.prototype.hasOwnProperty.call(replies, url) && !(url === '/api/update' && update === 404);
      return {ok: known, status: known ? 200 : 404, json: async () => known ? replies[url] : {}};
    },
    document: {getElementById: $, readyState: 'loading', title: '', activeElement: null, body: new El('body'),
      documentElement: {dataset: {}}, createElement: tag => new El(tag),
      addEventListener: (type, fn) => docListeners.push([type, fn]),
      querySelectorAll: () => [], querySelector: () => null},
  };
  vm.createContext(ctx);
  ctx.window = vm.runInContext('globalThis', ctx);
  ctx.addEventListener = () => {};
  ctx.TypeAnalysis = require('../web/analysis.js');
  for (const file of APP_SCRIPTS) vm.runInContext(scripts[file], ctx, {filename: 'web/' + file});
  return {ctx, $, nodes, docListeners, requests, intervals, storage};
}
const settle = async () => { for (let i = 0; i < 10; i++) await new Promise(resolve => setImmediate(resolve)); };

(async () => {
  const ui = loadAll();
  // Globals that companion.js and the tests rely on stay global.
  for (const name of ['routeCatalog', 'localState', 'token', 'renderScreen', 'setCompanionView', 'spriteFallback',
    'card', 'detail', 'esc', 'num', 'list', 'spriteId', 'getJSON', 'setText', 'command', 'switchTab', 'itemIcon'])
    assert.notEqual(vm.runInContext('typeof ' + name, ui.ctx), 'undefined', name + ' debe ser global');
  assert.equal(ui.ctx.window.setCompanionView, vm.runInContext('setCompanionView', ui.ctx));
  assert.equal(ui.$('party').children.length, 6, 'Seis tarjetas de equipo');
  assert.equal(ui.$('box').options.length, 32);
  await settle();
  assert.deepEqual(ui.requests.slice(0, 2), ['/api/templates', '/api/session']);
  assert.ok(ui.requests.includes('/api/update'), 'La comprobación de versión arranca con la sesión');

  // --- Item icons in team cards and the detail dialog.
  const {ctx} = ui;
  const mon = extra => ({species_id: 448, species: 'Lucario', nickname: 'Goty', level: 50, hp: 10, max_hp: 20,
    ability: 'Impasible', item: 'Restos', nature: 'Firme', move_names: [], ...extra});
  const iconOf = text => text.match(/<img class="item-icon"[^>]*>/)?.[0];
  const icon = iconOf(ctx.card(mon({item_id: 234}), 0));
  assert.equal(icon, '<img class="item-icon" src="/overlay/item/234.png" data-item-icon="" alt="" width="24" height="24" loading="lazy">');
  assert.match(ctx.card(mon({item_id: 234}), 0), /<span>Objeto<\/span><img class="item-icon"[^>]*>Restos<\/div>/, 'Icono junto al nombre');
  for (const item_id of [0, -3, 1.5, '234', HOSTILE, null, undefined, true, NaN])
    assert.equal(iconOf(ctx.card(mon({item_id}), 0)), undefined, 'Sin icono para item_id ' + String(item_id));
  const detailHtml = () => ui.$('detail-content').innerHTML;
  vm.runInContext('detailSignature=""', ctx);
  ctx.detail(mon({item_id: 50}));
  assert.match(detailHtml(), /Impasible · <img class="item-icon" src="\/overlay\/item\/50.png"[^>]*>Restos<\/p>/);
  vm.runInContext('detailSignature=""', ctx);
  ctx.detail(mon({item_id: 0, item: HOSTILE}));
  assert.ok(!detailHtml().includes('item-icon') && detailHtml().includes('&lt;img src=x'), 'Sin objeto: sin icono y texto escapado');
  // The partner's snapshot never asks the local server for icons.
  vm.runInContext('companionView=true;detailSignature=""', ctx);
  assert.equal(iconOf(ctx.card(mon({item_id: 234}), 0)), undefined);
  ctx.detail(mon({item_id: 234}));
  assert.ok(!detailHtml().includes('item-icon'));
  vm.runInContext('companionView=false', ctx);
  // The delegated error handler hides a missing icon without touching its source.
  const missing = {tagName: 'IMG', dataset: {itemIcon: ''}, src: '/overlay/item/9999.png', hidden: false,
    classList: {add() { throw Error('No aplica'); }}, nextElementSibling: {hidden: true}};
  ctx.spriteFallback({target: missing});
  assert.equal(missing.hidden, true);
  assert.equal(missing.src, '/overlay/item/9999.png', 'Sin reintentos remotos para objetos');
  assert.equal(missing.nextElementSibling.hidden, true);

  // --- Update notice.
  const banner = html.match(/<div id="update-notice"[^>]*>[\s\S]*?<\/div>/)?.[0];
  assert.ok(banner, 'Aviso de actualización en index.html');
  assert.match(banner, /role="status"/);
  assert.match(banner, / hidden>/, 'Oculto hasta confirmar una versión nueva');
  assert.match(banner, /Hay una nueva versión: <strong id="update-notice-version"><\/strong>/);
  assert.match(banner, /<a id="update-notice-link" href="https:\/\/github.com\/joanjuz\/NuzlockeTracker\/releases" target="_blank" rel="noopener noreferrer">Descargar<\/a>/);
  assert.match(banner, /<button id="update-notice-dismiss" type="button">Ocultar<\/button>/);
  assert.ok(html.indexOf('id="update-notice"') < html.indexOf('class="status-line"'), 'Junto a la cabecera');

  const release = 'https://github.com/joanjuz/NuzlockeTracker/releases/tag/v1.1.0';
  const fresh = loadAll({update: {current: '1.0.0', latest: '1.1.0', update_available: true, url: release, checked_at: null}});
  await settle();
  assert.equal(fresh.$('update-notice').hidden, false);
  assert.equal(fresh.$('update-notice-version').textContent, 'v1.1.0');
  assert.equal(fresh.$('update-notice-link').href, release);
  assert.equal(fresh.$('update-notice-link').attributes['aria-label'], 'Descargar la versión 1.1.0 desde GitHub');
  assert.equal(fresh.intervals.length, 1);
  assert.equal(fresh.intervals[0][1], 6 * 60 * 60 * 1000, 'Nueva consulta cada 6 h');
  fresh.ctx.scheduleUpdateCheck();
  assert.equal(fresh.intervals.length, 1, 'Reconectar no duplica el temporizador');
  fresh.$('update-notice-dismiss').onclick();
  assert.equal(fresh.$('update-notice').hidden, true);
  assert.equal(fresh.storage['progressive-update-dismissed'], '1.1.0');
  await fresh.intervals[0][0]();
  assert.equal(fresh.$('update-notice').hidden, true, 'La versión ocultada no reaparece');
  // A newer release than the dismissed one shows the notice again.
  fresh.ctx.showUpdateNotice({latest: 'v1.2.0', update_available: true, url: release});
  assert.equal(fresh.$('update-notice').hidden, false);
  assert.equal(fresh.$('update-notice-version').textContent, 'v1.2.0');

  const show = info => { fresh.ctx.showUpdateNotice(info); return fresh.$('update-notice').hidden; };
  for (const url of ['javascript:alert(1)', 'http://github.com/joanjuz/NuzlockeTracker/releases',
    'https://github.com/otro/NuzlockeTracker/releases', 'https://github.com/joanjuz/NuzlockeTracker/../../otro/x',
    'https://github.com/joanjuz/NuzlockeTracker/%2e%2e/otro', 'https://github.com.evil.example/joanjuz/NuzlockeTracker/',
    'https://github.com/joanjuz/NuzlockeTrackerX/releases', 'https://github.com/joanjuz/NuzlockeTracker/"><script>', 42, null])
    assert.equal(show({latest: '1.3.0', update_available: true, url}), true, 'URL rechazada: ' + url);
  for (const latest of [HOSTILE, '1.3', '', null, 130])
    assert.equal(show({latest, update_available: true, url: release}), true, 'Versión rechazada: ' + latest);
  assert.equal(show({latest: '1.3.0', update_available: false, url: release}), true);
  assert.equal(show({latest: '1.3.0', update_available: 'true', url: release}), true);
  assert.equal(show(null), true);

  // Silent failures: 404 (older server), network error, blocked storage.
  for (const update of [404, Error('sin red')]) {
    const quiet = loadAll({update});
    await settle();
    assert.equal(quiet.$('update-notice-version').textContent, '', 'Sin aviso si /api/update falla');
    assert.equal(quiet.$('status').textContent, 'Sin conexión', 'El fallo no afecta al arranque');
  }
  const blocked = loadAll({storage: null, update: {latest: '1.1.0', update_available: true, url: release}});
  await settle();
  assert.equal(blocked.$('update-notice').hidden, false);
  assert.doesNotThrow(() => blocked.$('update-notice-dismiss').onclick());
  assert.equal(blocked.$('update-notice').hidden, true);

  console.log('Scripts del tracker: orden, ámbito compartido, iconos de objeto y aviso de actualización OK');
})().catch(error => { console.error(error); process.exit(1); });
