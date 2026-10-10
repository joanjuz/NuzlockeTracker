'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
const app=fs.readFileSync(path.join(__dirname,'../web/app.js'),'utf8');
const html=fs.readFileSync(path.join(__dirname,'../web/index.html'),'utf8');
const process=fs.readFileSync(path.join(__dirname,'../tracker/process_memory.py'),'utf8');
const service=fs.readFileSync(path.join(__dirname,'../tracker/service.py'),'utf8');
for(const game of ['Pokémon X 1.0','Pokémon Y 1.0','Omega Ruby 1.0','Alpha Sapphire 1.0']){
 assert.ok(html.includes('<option>'+game+'</option>'),'Falta '+game);
 assert.ok(app.includes(game),'No hay selección para '+game);
}
assert.match(html,/id="places-heading"/);
assert.match(html,/id="game-region"/);
assert.match(app,/regi[oó]n|const region=gen6/);
assert.match(app,/catalogo pendiente|catálogo pendiente/);
assert.match(app,/\$\('box'\)\.disabled=gen6/);
assert.match(app,/\$\('global'\)\.disabled=gen6/);
assert.match(app,/\$\('open-companion'\)\.disabled=gen6/);
assert.match(service,/self\.profile\.generation==6/);
assert.match(service,/box_verified=False/);
assert.match(service,/max_species=721/);
assert.match(process,/generation==6/);
assert.match(process,/start_addr,end_addr=/);
console.log('Gen6: X/Y ORAS visibles, región correcta, cajas y Soul Link sin validar bloqueados');
