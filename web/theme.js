'use strict';
/* Tema guardado (claro/oscuro), cargado antes de los estilos para evitar parpadeos.
   Archivo externo para permitir una CSP sin scripts en línea. */
(() => {
  const syncTheme = () => {
    try {
      const saved = localStorage.getItem('progressive-theme');
      document.documentElement.dataset.theme = saved === 'light' || saved === 'dark'
        ? saved : (matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark');
    } catch (_) {
      document.documentElement.dataset.theme = 'dark';
    }
  };
  syncTheme();
  window.addEventListener('storage', event => {
    if (event.key === 'progressive-theme' || event.key === null) syncTheme();
  });
})();
