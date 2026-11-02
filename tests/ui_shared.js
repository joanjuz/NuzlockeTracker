'use strict';
// Loads the real shared helpers of web/app.js (escaping, numbers, game lists)
// into a vm context, so sliced renderers run with production helpers.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../web/app.js'), 'utf8');
const start = source.indexOf('// Shared helpers');
const end = source.indexOf('// End shared helpers.');
if (start < 0 || end < start) throw Error('Bloque de utilidades compartidas no encontrado en web/app.js');
const lines = source.slice(start, end).split(/\r?\n/).filter(line => line.startsWith('const '));
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

module.exports = { loadShared, source };
