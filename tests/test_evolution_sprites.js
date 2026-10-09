'use strict';
// Exercise the actual evolution-card renderer, including its two-step image fallback.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../web/app.js'), 'utf8');

const start = source.indexOf('function detail(p)');
const end = source.indexOf('\nfunction normalize(', start);
assert.ok(start >= 0 && end > start, 'Pokemon detail renderer must be found');
const elements = {};
const $ = id => elements[id] ||= {innerHTML: ''};
const context = {
  $, esc: value => String(value ?? ''), portrait: () => '<div class="portrait"></div>',
  detailPokemon: null, detailSignature: '',
};
vm.createContext(context);
vm.runInContext(source.slice(start, end), context);

const p = {
  species_id: 37, species: 'Vulpix', nickname: 'Vulpix', level: 25,
  nature: 'Firme', ability: 'Absorbe Fuego', item: '—',
  move_names: [], moves: [], iv: [0, 0, 0, 0, 0, 0], ev: [0, 0, 0, 0, 0, 0],
  met_location: 'Ruta 1', met_level: 4, met_date: '2026-10-08',
  evolutions: [{target: 38, target_name: 'Ninetales', method: 'Usar Piedra Fuego',
                source: 'pk3DS Progressive'}]
};
context.detail(p);
const html = $('detail-content').innerHTML;
assert.match(html, /<img src="\/sprites\/38.png"/);
assert.match(html, /alt="Ninetales"/);
assert.match(html, /<span class="sprite-fallback" hidden>#38<\/span>/);
const handler = html.match(/class="evolution-option"><img[^>]+onerror="([^"]+)"/)?.[1];
assert.ok(handler, 'Evolution image must use a fallback handler');
const fallback = {hidden: true};
const image = {src: '/sprites/38.png', dataset: {}, hidden: false, nextElementSibling: fallback};
const onerror = vm.runInNewContext('(function(){' + handler + '})');
onerror.call(image);
assert.equal(image.src, 'https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/38.png');
assert.equal(image.dataset.remote, '1');
assert.equal(image.hidden, false);
assert.equal(fallback.hidden, true);
onerror.call(image);
assert.equal(image.hidden, true);
assert.equal(fallback.hidden, false);
const alolan = {...p, evolutions:[{target:38,sprite_id:10104,target_name:'Ninetales de Alola',method:'Usar piedra hielo',source:'PokéAPI'}]};
context.detail(alolan);
const alolaHtml = $('detail-content').innerHTML;
assert.match(alolaHtml, /src="\/sprites\/10104.png"/);
assert.match(alolaHtml, /sprites\/pokemon\/10104.png/);
assert.match(alolaHtml, /Ninetales de Alola/);
const none = {...p, evolutions:[]};
context.detail(none);
assert.doesNotMatch($('detail-content').innerHTML, /Cómo evoluciona/);
console.log('Evoluciones: sprite local -> PokeAPI -> número, forma Alola y sección condicional OK');
