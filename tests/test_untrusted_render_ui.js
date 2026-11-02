'use strict';
// Partner (Soul Link) snapshots reach the same renderers as local data:
// run the real card/detail/sprite/box renderers with hostile values.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {loadShared, source} = require('./ui_shared.js');
const read = file => fs.readFileSync(path.join(__dirname, '..', file), 'utf8');
const slice = (from, to) => {
  const start = source.indexOf(from), end = source.indexOf(to, start + 1);
  assert.ok(start >= 0 && end > start, 'No se encontró ' + from);
  return source.slice(start, end);
};
const HOSTILE = '<img src=x onerror=alert(1)>';
const assertInert = (html, label) => {
  assert.ok(!html.includes('<img src=x'), label + ': HTML crudo insertado');
  assert.ok(!/<script/i.test(html), label + ': script insertado');
  assert.ok(!/\son\w+=/i.test(html.replace(/&lt;[^]*?&gt;/g, '')), label + ': atributo de evento insertado');
};

// --- card(), portrait(), detail() ---
const elements = {};
const $ = id => elements[id] ||= {innerHTML: '', contains: () => false, querySelector: () => null, open: false};
const ctx = {$, document: {activeElement: null}, detailPokemon: null, detailSignature: '', selected: null};
vm.createContext(ctx);
loadShared(ctx);
vm.runInContext(source.split(/\r?\n/).find(line => line.startsWith('const labels=')), ctx);
vm.runInContext(slice('function portrait(', '\nfunction normalize('), ctx);

const hostile = {
  species_id: HOSTILE, species: HOSTILE, nickname: HOSTILE, level: HOSTILE,
  hp: HOSTILE, max_hp: HOSTILE, ability: HOSTILE, item: HOSTILE, nature: HOSTILE,
  stats: {ATQ: HOSTILE, DEF: HOSTILE, ATE: HOSTILE, DEE: HOSTILE, VEL: HOSTILE},
  move_names: [HOSTILE], moves: [HOSTILE], iv: [HOSTILE, 1, 2, 3, 4, 5], ev: Array(6).fill(HOSTILE),
  met_location: HOSTILE, met_level: HOSTILE, met_date: HOSTILE, egg_location_id: 1, egg_location: HOSTILE,
  base_stats: {[HOSTILE]: HOSTILE},
  evolutions: [{target: HOSTILE, sprite_id: HOSTILE, target_name: HOSTILE, method: HOSTILE, source: HOSTILE}, null, 'x'],
};
const cardHtml = ctx.card(hostile, 0);
assertInert(cardHtml, 'card');
assert.match(cardHtml, /&lt;img src=x/, 'Los textos hostiles se muestran escapados');
assert.match(cardHtml, /<span>— \/ —<\/span>/, 'PS no numéricos se muestran como —');
assert.match(cardHtml, /width:0%/, 'La barra de PS no recibe texto');
assert.match(cardHtml, /src="\/sprites\/0.png" data-fallback="0"/);
ctx.detail(hostile);
const detailHtml = $('detail-content').innerHTML;
assertInert(detailHtml, 'detail');
assert.match(detailHtml, /Nivel de encuentro: —/);
assert.match(detailHtml, /<td>PS<\/td><td>—<\/td><td>—<\/td>/, 'IV/EV hostiles no se interpolan');
assert.match(detailHtml, /<td>Ataque<\/td><td>1<\/td>/, 'IV válidos se conservan');
assert.equal((detailHtml.match(/class="evolution-option"/g) || []).length, 1, 'Evoluciones inválidas se omiten');

// Legitimate values render unchanged, including numeric strings.
const normal = ctx.card({species_id: 25, species: 'Pikachu', nickname: 'Chispa', level: 30, hp: 40, max_hp: 80,
  stats: {ATQ: 55, DEF: '40', ATE: 50, DEE: 50, VEL: 90}, ability: 'Electricidad Estática', item: 'Baya Aranja',
  met_location: 'Ruta 1', move_names: ['Impactrueno', 'Ataque Rápido']}, 2);
assert.match(normal, /NIVEL 30/);
assert.match(normal, /<span>40 \/ 80<\/span>/);
assert.match(normal, /width:50%/);
assert.match(normal, /<strong>40<\/strong>/);
assert.match(normal, /Impactrueno/);
assert.match(ctx.card({species_id: 25, species: 'Pikachu', hp: 0, max_hp: 80, move_names: []}, 0), /DEBILITADO/);

// move_names / moves / iv / ev may be missing or of the wrong type.
for (const broken of [{move_names: 'Placaje'}, {move_names: null}, {move_names: 7, moves: 'x', iv: 'x', ev: {}}, {evolutions: 'Raichu'}]) {
  const p = {species_id: 25, species: 'Pikachu', ...broken};
  assert.doesNotThrow(() => ctx.card(p, 0), JSON.stringify(broken));
  ctx.detailSignature = '';
  assert.doesNotThrow(() => ctx.detail(p), JSON.stringify(broken));
}

// --- sprite() used by boxes, routes and Muertos ---
const spriteCtx = {state: {progress: {deaths: {}}}};
vm.createContext(spriteCtx);
loadShared(spriteCtx);
for (const name of ['pokemonKey', 'isDead', 'sprite']) vm.runInContext(slice('function ' + name + '(', '\nfunction '), spriteCtx);
const spriteHtml = spriteCtx.sprite(hostile);
assertInert(spriteHtml, 'sprite');
assert.match(spriteHtml, /#—<\/span>/);

// --- renderBoxes(): box keys come from the partner snapshot too ---
class Node {
  constructor() { this.children = []; this.innerHTML = ''; this.textContent = ''; this.checked = false; this.value = ''; this.hidden = false; }
  replaceChildren() { this.children = []; }
  append(item) { this.children.push(item); }
}
const nodes = {};
const boxCtx = {$: id => nodes[id] ??= new Node(), state: null, boxSignature: '', companionView: true,
  sprite: () => '<span class="sprite"></span>', openDetail: () => {}, document: {createElement: () => new Node()}};
vm.createContext(boxCtx);
loadShared(boxCtx);
vm.runInContext(slice('function normalize(', '\nfunction render(next)'), boxCtx);
boxCtx.$('global').checked = true;
boxCtx.state = {game: 'Ultra Moon 1.0', stale: true, connection: {status: 'disconnected'}, progress: {deaths: {}},
  boxes: {[HOSTILE]: [{species_id: 25, species: 'Pikachu', nickname: HOSTILE, move_names: HOSTILE}], 2: 'no es una caja'}};
assert.doesNotThrow(() => boxCtx.renderBoxes());
const boxHtml = boxCtx.$('boxes').children.map(child => child.innerHTML || '').join('');
assertInert(boxHtml, 'renderBoxes');
assert.match(boxHtml, /Caja &lt;img src=x/);

// --- moveSheet(): move dialog body (server data plus partner PP values) ---
const moveCtx = {};
vm.createContext(moveCtx);
loadShared(moveCtx);
vm.runInContext(slice('function normalize(', '\nfunction '), moveCtx);
vm.runInContext(slice('function moveSheet(', "\n$('close-move')"), moveCtx);
const moveHtml = moveCtx.moveSheet({name: HOSTILE, type: HOSTILE, category: HOSTILE, power: HOSTILE, accuracy: HOSTILE,
  pp: 10, priority: HOSTILE, description: HOSTILE, source: HOSTILE, template_notes: HOSTILE, wikidex_url: HOSTILE}, HOSTILE, HOSTILE, 1);
assertInert(moveHtml, 'moveSheet');
assert.match(moveHtml, /MOVIMIENTO \/ —/);
assert.match(moveHtml, /class="type-tag type-imgsrcxonerroralert"/, 'La clase de tipo solo admite letras');
assert.match(moveHtml, /PP actuales: <strong>—<\/strong> · Máximo: 12/);

// --- defenseTable() / coverageReport(): names and moves come from the partner ---
const analysisCtx = {TypeAnalysis: require('../web/analysis.js')};
vm.createContext(analysisCtx);
loadShared(analysisCtx);
vm.runInContext(slice('function multiplier(', "\nfor(const id of ['analysis-defense'"), analysisCtx);
const analysisChart = JSON.parse(read('data/Analysis_USUM.json'));
const hostileTeam = [{slot: 0, nickname: HOSTILE, species: HOSTILE, ability: HOSTILE, types: [HOSTILE],
  analysis_moves: [{name: HOSTILE, type: 'Fuego', category: 'Físico'}]}];
for (const simple of [false, true]) {
  assertInert(analysisCtx.defenseTable(hostileTeam, analysisChart.types, analysisChart.chart, true, simple), 'defenseTable');
}
const coverageHtml = analysisCtx.coverageReport(hostileTeam, analysisChart.types, analysisChart.chart, true, false);
assertInert(coverageHtml, 'coverageReport');
assert.match(coverageHtml, /&lt;img src=x/);

// --- TypeAnalysis tolerates hostile type lists ---
const A = require('../web/analysis.js');
const chart = JSON.parse(read('data/Analysis_USUM.json')).chart;
assert.equal(A.basic(chart, 'Fuego', 'Agua'), 1, 'Una cadena no se trata como lista de tipos');
assert.equal(A.basic(chart, 'Fuego', ['__proto__', 'constructor']), 1);
assert.equal(A.defensive(chart, 'Fuego', {types: 5}), 1);
assert.equal(A.coverage(chart, [{analysis_moves: 'Rayo'}], ['Agua']), null);

console.log('Datos no confiables: card, detail, movimiento, sprite, cajas y análisis escapados OK');
