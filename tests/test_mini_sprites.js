// Regression test: minicards use the same local -> remote -> numeric fallback
// as the large party cards, and do not repaint on ordinary HP changes.
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const {slice} = require('./ui_shared.js');
// renderMini and its button helper close web/app/team.js.
const code = slice('app/team.js', 'function renderMini(){');

class Element {
  constructor(tag) { this.tag = tag; this.children = []; this.innerHTML = ''; this.attributes = {}; }
  setAttribute(name, value) { this.attributes[name] = value; }
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
require('./ui_shared.js').loadShared(ctx, ['spriteId']);
vm.runInContext(code, ctx);
vm.runInContext(slice('app/helpers.js', 'const SPRITE_REMOTE=', "document.addEventListener('error',spriteFallback,true);"), ctx);
ctx.renderMini();
assert.equal($('mini-team').children.length, 6);
assert.equal($('party-count').textContent, 2);

// The first missing local sprite retries PokeAPI, then reveals the slot number.
const first = $('mini-team').children[0];
const fallbackId = first.innerHTML.match(/data-fallback="(\d+)"/)?.[1];
assert.equal(fallbackId, '448', 'el minisprite usa el fallback delegado');
assert.doesNotMatch(first.innerHTML, /onerror=/);
const img = { tagName: 'IMG', src: '/sprites/448.png', dataset: { fallback: fallbackId }, hidden: false,
  nextElementSibling: { hidden: true } };
const errorCallback = () => ctx.spriteFallback({ target: img });
errorCallback();
assert.equal(img.src, 'https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/448.png');
assert.equal(img.hidden, false);
errorCallback();
assert.equal(img.hidden, true);
assert.equal(img.nextElementSibling.hidden, false);

// Empty slots are announced as such, not as a lone dot.
const empty = $('mini-team').children[2];
assert.equal(empty.attributes['aria-label'], 'Espacio vacío');
assert.match(empty.innerHTML, /aria-hidden="true"/);
assert.equal(first.attributes['aria-label'], undefined);

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
