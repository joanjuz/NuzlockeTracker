'use strict';
// Live regions, input border contrast and storage that may be unavailable in WebView2.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const read = file => fs.readFileSync(path.join(__dirname, '../web', file), 'utf8');
const html = read('index.html'), css = read('style.css'), app = require('./ui_shared.js').source;

// Status texts are polite live regions; the alert stays reserved for real failures.
for (const id of ['status', 'badge', 'notice']) {
  const tag = html.match(new RegExp('<[^>]+id="' + id + '"[^>]*>'))?.[0];
  assert.ok(tag, 'Falta #' + id);
  assert.match(tag, /role="status"/, '#' + id + ' necesita role=status');
  assert.match(tag, /aria-live="polite"/, '#' + id + ' debe ser polite');
}
assert.doesNotMatch(html, /aria-live="assertive"/);
// Frames that repeat the same text must not re-announce it.
assert.match(app, /function setText\(node,text\)\{if\(node\.textContent!==text\)node\.textContent=text\}/);
assert.match(app, /setText\(\$\('status'\)/);
assert.match(app, /setText\(\$\('badge'\)/);
assert.match(app, /setText\(\$\('notice'\)/);

// Input/select borders reach 3:1 against surface and page in both themes.
const luminance = hex => {
  const [r, g, b] = [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16) / 255)
    .map(v => v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4);
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
};
const ratio = (a, b) => { const [x, y] = [luminance(a), luminance(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };
const themeVar = (theme, name) => {
  const values = [...css.matchAll(new RegExp((theme === 'dark' ? ':root,\\[data-theme="dark"\\]' : '\\[data-theme="light"\\]') + '\\{[^}]*--' + name + ':#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\\b', 'g'))];
  assert.ok(values.length, theme + ' --' + name);
  const hex = values.at(-1)[1];
  return '#' + (hex.length === 3 ? [...hex].map(c => c + c).join('') : hex);
};
for (const theme of ['dark', 'light']) {
  const border = themeVar(theme, 'control-border');
  for (const bg of ['surface', 'page']) {
    const background = themeVar(theme, bg);
    const value = ratio(border, background);
    assert.ok(value >= 3, `${theme}: borde de campos ${border} sobre --${bg} ${background} = ${value.toFixed(2)}:1`);
  }
}
assert.match(css, /input:not\(\[type="checkbox"\]\):not\(\[type="radio"\]\):not\(\[type="file"\]\),select\{border-color:var\(--control-border\)\}/);

// Compact view preference survives a storage that throws.
const line = require('./ui_shared.js').slice('app/shell.js', 'let compact=', "\ndocument.addEventListener('pointerdown'");
assert.match(line, /\$\('density'\)\.onclick=/, 'El bloque de densidad incluye el manejador del botón');
const classes = new Set();
const density = {textContent: '', onclick: null};
const ctx = {
  localStorage: {getItem() { throw Error('Bloqueado'); }, setItem() { throw Error('Bloqueado'); }},
  document: {body: {classList: {toggle: (name, on) => on ? classes.add(name) : classes.delete(name)}}},
  $: id => id === 'density' ? density : null,
};
vm.createContext(ctx);
assert.doesNotThrow(() => vm.runInContext(line, ctx));
assert.equal(density.textContent, 'Vista compacta');
assert.doesNotThrow(() => density.onclick());
assert.ok(classes.has('compact'));
assert.equal(density.textContent, 'Vista amplia');

console.log('Accesibilidad: regiones vivas educadas, contraste de campos y almacenamiento opcional OK');
