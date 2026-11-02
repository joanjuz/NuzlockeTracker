'use strict';
// Exercise the actual evolution-card renderer, including its two-step image fallback.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../web/app.js'), 'utf8');

const start = source.indexOf('function wikidexUrl(');
const end = source.indexOf('\nfunction normalize(', start);
assert.ok(start >= 0 && end > start, 'Pokemon detail renderer must be found');
const elements = {};
const $ = id => elements[id] ||= {innerHTML: '',contains:()=>false,querySelector:()=>null};
const context = {
  $, esc: value => String(value ?? ''), portrait: () => '<div class="portrait"></div>',
  detailPokemon: null, detailSignature: '', document:{activeElement:null},
};
vm.createContext(context);
require('./ui_shared.js').loadShared(context, ['num', 'list', 'spriteId']);
vm.runInContext(source.slice(start, end), context);
// The production delegated listener, extracted as-is.
const fbStart = source.indexOf('const SPRITE_REMOTE=');
const fbEnd = source.indexOf("document.addEventListener('error',spriteFallback,true);", fbStart);
assert.ok(fbStart >= 0 && fbEnd > fbStart, 'Delegated sprite fallback must exist');
vm.runInContext(source.slice(fbStart, fbEnd), context);
assert.match(source, /document\.addEventListener\('error',spriteFallback,true\)/);

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
assert.match(html, /href="https:\/\/www.wikidex.net\/wiki\/Vulpix"/);
assert.match(html, /href="https:\/\/www.wikidex.net\/wiki\/Ninetales"/);
assert.equal((html.match(/WikiDex ↗/g)||[]).length,2);
assert.match(html, /<span class="sprite-fallback" hidden>#38<\/span>/);
const fallbackId = html.match(/class="evolution-option"><img[^>]+data-fallback="(\d+)"/)?.[1];
assert.equal(fallbackId, '38', 'Evolution image must opt into the delegated fallback');
assert.doesNotMatch(html, /onerror=/, 'No inline handlers');
const fallback = {hidden: true};
const image = {tagName: 'IMG', src: '/sprites/38.png', dataset: {fallback: fallbackId}, hidden: false, nextElementSibling: fallback};
const onerror = () => context.spriteFallback({target: image});
onerror();
assert.equal(image.src, 'https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/38.png');
assert.equal(image.dataset.remote, '1');
assert.equal(image.hidden, false);
assert.equal(fallback.hidden, true);
onerror();
assert.equal(image.hidden, true);
assert.equal(fallback.hidden, false);
// A third error (e.g. the browser retries) must not loop or touch the source again.
const settledSrc = image.src;
onerror();
assert.equal(image.src, settledSrc);
// Images without data-fallback (Poké Ball, empty route) are ignored.
const plain = {tagName: 'IMG', src: '/app-icon.png', dataset: {}, hidden: false};
context.spriteFallback({target: plain});
assert.equal(plain.src, '/app-icon.png');
// Living Dex silhouettes end in the Poké Ball instead of a number.
const classes = new Set();
const ball = {tagName: 'IMG', src: '/sprites/1.png', dataset: {fallback: '1', fallbackFinal: 'ball'},
  classList: {add: name => classes.add(name)}};
context.spriteFallback({target: ball});
assert.match(ball.src, /sprites\/pokemon\/1.png$/);
context.spriteFallback({target: ball});
assert.equal(ball.src, '/app-icon.png');
assert.ok(classes.has('living-dex-ball'));
context.spriteFallback({target: ball});
assert.equal(ball.src, '/app-icon.png', 'A broken Poké Ball does not retry forever');
const alolan = {...p, evolutions:[{target:38,sprite_id:10104,target_name:'Ninetales de Alola',method:'Usar piedra hielo',source:'PokéAPI'}]};
context.detail(alolan);
const alolaHtml = $('detail-content').innerHTML;
assert.match(alolaHtml, /src="\/sprites\/10104.png"/);
assert.match(alolaHtml, /data-fallback="10104"/);
assert.match(alolaHtml, /Ninetales de Alola/);
assert.match(alolaHtml, /href="https:\/\/www.wikidex.net\/wiki\/Ninetales_de_Alola"/);
const none = {...p, evolutions:[]};
context.detail(none);
assert.doesNotMatch($('detail-content').innerHTML, /Cómo evoluciona/);
assert.doesNotMatch($('detail-content').innerHTML, /WikiDex ↗/);
const diglett = {...p,species:'Diglett',species_id:50,form:1,evolutions:[{
 target:51, target_name:'Dugtrio de Alola',sprite_id:10106,method:'Subir de nivel (nivel 26)',source:'PokéAPI'}]};
context.detail(diglett);
const dugtrio = $('detail-content').innerHTML;
assert.match(dugtrio, /href="https:\/\/www.wikidex.net\/wiki\/Diglett_de_Alola"/);
assert.match(dugtrio, /href="https:\/\/www.wikidex.net\/wiki\/Dugtrio_de_Alola"/);
assert.match(dugtrio, /src="\/sprites\/10106.png"/);
console.log('Evoluciones: sprite local -> PokeAPI -> número, forma Alola y sección condicional OK');
