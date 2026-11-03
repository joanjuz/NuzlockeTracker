'use strict';
// The tracker UI is split into classic scripts (web/app/*.js + web/app.js) that
// share one global scope in the browser. This module reads them in the order
// index.html loads them and loads the real shared helpers into vm contexts, so
// sliced renderers run with production helpers.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const WEB = path.join(__dirname, '../web');
const read = file => fs.readFileSync(path.join(WEB, file), 'utf8');
const html = read('index.html');
const APP_SCRIPTS = [...html.matchAll(/<script src="\/(app\/[\w-]+\.js|app\.js)"><\/script>/g)].map(m => m[1]);
if (!APP_SCRIPTS.length || APP_SCRIPTS[0] !== 'app/helpers.js' || APP_SCRIPTS.at(-1) !== 'app.js')
  throw Error('index.html debe cargar app/helpers.js primero y app.js al final');
const scripts = Object.fromEntries(APP_SCRIPTS.map(file => [file, read(file)]));
// Whole UI in load order, for assertions that do not depend on a single file.
const source = APP_SCRIPTS.map(file => scripts[file]).join('\n');

// Text of `file` from `from` up to (not including) `to`; without `to`, to the end of the file.
function slice(file, from, to) {
  const text = Object.prototype.hasOwnProperty.call(scripts, file) ? scripts[file] : read(file);
  const start = text.indexOf(from);
  if (start < 0) throw Error('No se encontró «' + from + '» en web/' + file);
  if (to === undefined) return text.slice(start);
  const end = text.indexOf(to, start + 1);
  if (end < 0) throw Error('No se encontró «' + to + '» después de «' + from + '» en web/' + file);
  return text.slice(start, end);
}

const helpers = slice('app/helpers.js', '// Shared helpers', '// End shared helpers.');
const lines = helpers.split(/\r?\n/).filter(line => line.startsWith('const '));
const nameOf = line => line.match(/^const ([\w$]+)=/)[1];

// `$` is never loaded: every harness supplies its own fake DOM lookup.
function loadShared(context, names = ['esc', 'num', 'list', 'GAME_FAMILIES', 'GEN6_GAMES', 'gameFamily', 'spriteId']) {
  for (const name of names) {
    const line = lines.find(item => nameOf(item) === name);
    if (!line) throw Error('Utilidad compartida ausente: ' + name);
    if (Object.prototype.hasOwnProperty.call(context, name)) delete context[name];
    vm.runInContext(line, context);
  }
  return context;
}

module.exports = { APP_SCRIPTS, loadShared, read, scripts, slice, source };
