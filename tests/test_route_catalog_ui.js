'use strict';
// Route catalogs are fetched once per game, the partner's game asks for its own
// catalog, failures fall back to [] and Soul Link compares routes with that catalog.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {loadShared, source} = require('./ui_shared.js');
const companion = fs.readFileSync(path.join(__dirname, '../web/companion.js'), 'utf8');
const settle = () => new Promise(resolve => setImmediate(resolve));
const slice = (from, to) => {
  const start = source.indexOf(from), end = source.indexOf(to, start + 1);
  assert.ok(start >= 0 && end > start, 'No se encontró ' + from);
  return source.slice(start, end);
};

// Startup asks for /api/routes only through the per-game cache (no double fetch).
const startFn = source.split(/\r?\n/).find(line => line.startsWith('async function start(){'));
assert.ok(startFn, 'start() debe existir');
assert.doesNotMatch(startFn, /api\/routes/, 'start() no descarga rutas por su cuenta');
assert.match(startFn, /getJSON\('\/api\/session'\)/);
assert.match(startFn, /getJSON\('\/api\/state'\)/);
assert.equal((source.match(/\/api\/routes/g) || []).length, 2, 'Una ruta local y una con ?game=');

function harness(responses) {
  const requests = [], rendered = [];
  const nodes = {'places-view': {hidden: false}};
  const ctx = {
    $: id => nodes[id] ??= {hidden: true},
    localState: {game: 'Ultra Moon 1.0'}, state: {game: 'Ultra Moon 1.0'},
    routeCatalog: [], placeSignature: 'previa', renderPlaces: () => rendered.push(ctx.routeCatalog),
    fetch: async url => {
      requests.push(url);
      const reply = responses[url];
      if (reply instanceof Error) throw reply;
      return {ok: reply?.ok !== false, status: reply?.ok === false ? 500 : 200, json: async () => reply?.data};
    },
  };
  vm.createContext(ctx);
  loadShared(ctx, ['list']);
  vm.runInContext(slice('async function getJSON(', '\n// One delegated fallback'), ctx);
  vm.runInContext(slice('// Route catalogs are cached per game', 'async function exportWithDialog('), ctx);
  return {ctx, requests, rendered};
}

(async () => {
  const usum = [{id: 8, name: 'Ruta 1', ids: [8]}], xy = [{id: 8, name: 'Ruta 2', ids: [8, 9]}];
  const xyUrl = '/api/routes?game=' + encodeURIComponent('Pokémon X 1.0');
  const h = harness({'/api/routes': {data: {routes: usum}}, [xyUrl]: {data: {routes: xy}}});

  // getJSON rejects non-2xx responses instead of parsing error bodies as data.
  const bad = harness({'/api/x': {ok: false, data: {error: 'no'}}});
  await assert.rejects(bad.ctx.getJSON('/api/x'), /500/);

  // Local game: plain endpoint, one request even if asked twice while loading.
  assert.deepEqual([...h.ctx.routeCatalogFor('Ultra Moon 1.0')], []);
  h.ctx.routeCatalogFor('Ultra Moon 1.0');
  await settle();
  assert.deepEqual(h.requests, ['/api/routes']);
  assert.equal(h.ctx.routeCatalogFor('Ultra Moon 1.0')[0].name, 'Ruta 1');
  assert.equal(h.ctx.routeCatalog[0].name, 'Ruta 1', 'La vista visible recibe su catálogo');
  assert.equal(h.ctx.placeSignature, '', 'Rutas se redibujan al llegar el catálogo');
  assert.equal(h.rendered.length, 1);

  // Partner on another game: explicit ?game=, cached separately, visible view untouched.
  h.ctx.routeCatalogFor('Pokémon X 1.0');
  await settle();
  assert.equal(h.requests.at(-1), xyUrl);
  assert.equal(h.ctx.routeCatalogFor('Pokémon X 1.0')[0].name, 'Ruta 2');
  assert.equal(h.ctx.routeCatalog[0].name, 'Ruta 1', 'El catálogo del compañero no pisa la vista local');
  assert.equal(h.requests.length, 2, 'Cada juego se descarga una sola vez');

  // Failures leave an empty catalog and do not retry on every websocket frame.
  const failing = harness({'/api/routes': {ok: false}});
  assert.deepEqual([...failing.ctx.routeCatalogFor('Ultra Moon 1.0')], []);
  await settle();
  assert.deepEqual([...failing.ctx.routeCatalogFor('Ultra Moon 1.0')], []);
  assert.deepEqual([...failing.ctx.routeCatalog], []);
  assert.equal(failing.requests.length, 1);
  const malformed = harness({'/api/routes': {data: {routes: 'no es lista'}}});
  malformed.ctx.routeCatalogFor('Ultra Moon 1.0');await settle();
  assert.deepEqual([...malformed.ctx.routeCatalogFor('Ultra Moon 1.0')], []);

  // Soul Link: sameRoute groups IDs with the partner game's catalog.
  const pokemon = (id, route) => ({species_id: 25, species: 'Pikachu', nickname: 'P' + id, origin_version: 24,
    encryption_constant: id, met_location_id: route, checksum_valid: true, egg: false});
  const els = {};
  const node = id => els[id] ??= {id, hidden: true, checked: false, value: '', textContent: '', disabled: false, options: [],
    replaceChildren() { this.options = []; }, append(o) { this.options.push(o); }, removeAttribute() {},
    showModal() {}, close() {}, closest() { return null; }};
  const partnerState = {schema_version: 1, game: 'Pokémon Y 1.0', party: [], boxes: {}, progress: {deaths: {}}};
  const status = {configured: true, my_name: 'Local', partner: {name: 'Amiga', game: 'Pokémon Y 1.0', updated_at: 1, state: partnerState}};
  const asked = [];
  let poll;
  const cctx = {
    console, token: 't', routeCatalog: [{id: 99, ids: [99]}],
    routeCatalogFor: game => { asked.push(game); return game === 'Pokémon Y 1.0' ? xy : []; },
    localState: {game: 'Pokémon X 1.0', party: [pokemon(1, 9)], boxes: {}, progress: {deaths: {}}, connection: {status: 'connected'}, stale: false},
    localStorage: {getItem: () => { throw Error('Storage bloqueado'); }, setItem: () => { throw Error('Storage bloqueado'); }},
    document: {getElementById: node, createElement: () => ({}), querySelectorAll: () => []},
    window: {setCompanionView() {}}, setInterval: fn => { poll = fn; return 1; }, confirm: () => true,
    navigator: {}, fetch: async () => ({ok: true, json: async () => status}),
  };
  vm.createContext(cctx);
  loadShared(cctx);
  assert.doesNotThrow(() => vm.runInContext(companion, cctx), 'localStorage bloqueado no rompe Companion');
  await settle();
  assert.equal(node('soullink-enabled').checked, false);
  node('soullink-enabled').checked = true;
  assert.doesNotThrow(() => node('soullink-enabled').onchange(), 'Guardar la preferencia sin storage no falla');
  await poll(); await settle();
  assert.ok(asked.includes('Pokémon Y 1.0'), 'Se precarga el catálogo del juego del compañero');
  partnerState.progress.deaths.r1 = {pokemon: pokemon(50, 8), recorded_at: '2026-11-01'};
  await poll(); await settle();
  assert.equal(node('soullink-notification').hidden, false, 'Ruta 8/9 agrupada con el catálogo X/Y del compañero');
  assert.match(node('soullink-description').textContent, /P1/);

  console.log('Rutas por juego: caché, ?game= del compañero, fallos a [] y Soul Link con catálogo correcto OK');
})().catch(error => { console.error(error); process.exitCode = 1; });
