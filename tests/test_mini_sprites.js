// Regression test: minicards use the same local -> remote -> numeric fallback
// as the large party cards, and do not repaint on ordinary HP changes.
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../web/app.js'), 'utf8');
const code = source.split('\n').find(line => line.startsWith('function renderMini(){'));
assert.ok(code, 'renderMini debe existir en web/app.js');

class Element {
  constructor(tag) { this.tag = tag; this.children = []; this.innerHTML = ''; }
  replaceChildren() { this.children = []; }
  append(child) { this.children.push(child); }
}
const nodes = {}, calls = [];
const $ = id => nodes[id] ||= new Element('div');
const party = [
  { species_id: 448, species: 'Lucario', nickname: 'Goty', hp: 217 },
  { species_id: 637, species: 'Volcarona', nickname: 'Jim', hp: 241 },
  null, null, null, null
];
const ctx = {
  state: { party, boxes: {} }, miniSignature: '',
  $,
  document: { createElement: tag => new Element(tag) },
  esc: s => String(s),
  switchTab: tab => calls.push(tab),
  openDetail: (...args) => calls.push(args),
};
vm.createContext(ctx);
vm.runInContext(code, ctx);
ctx.renderMini();
assert.equal($('mini-team').children.length, 6);
assert.equal($('party-count').textContent, 2);

// The first missing local sprite retries PokeAPI, then reveals the slot number.
const first = $('mini-team').children[0];
const handler = first.innerHTML.match(/onerror="([^"]+)"/)?.[1];
assert.ok(handler, 'el minisprite debe tener una funcion onerror');
const img = { src: '/sprites/448.png', dataset: {}, hidden: false,
  nextElementSibling: { hidden: true } };
const errorCallback = vm.runInNewContext(`(function(){${handler}})`);
errorCallback.call(img);
assert.equal(img.src, 'https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/448.png');
assert.equal(img.hidden, false);
errorCallback.call(img);
assert.equal(img.hidden, true);
assert.equal(img.nextElementSibling.hidden, false);

// HP falls in battle: keep the same buttons and don't reload their images.
party[0].hp = 205;
ctx.renderMini();
assert.equal($('mini-team').children[0], first);
// Fainting is relevant and must be reflected in the bar.
party[0].hp = 0;
ctx.renderMini();
assert.notEqual($('mini-team').children[0], first);
assert.equal($('mini-team').children[0].className, 'fainted');
// The top icons still navigate to the Pokémon detail.
$('mini-team').children[1].onclick();
assert.equal(calls[0], 'party');
assert.equal(calls[1][0], party[1]);
console.log('Minisprites: fallback local/remoto/número, PS y botones OK');
