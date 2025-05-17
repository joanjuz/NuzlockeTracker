// SelectorJuego.js
import React from 'react';

const SelectorJuego = ({ juegosDisponibles, juegoSeleccionado, setJuegoSeleccionado }) => (
  <div className="bitacora-seccion">
    <h3 className="bitacora-subtitulo">🎮 Seleccionar Juego</h3>
    <select
      className="bitacora-select"
      value={juegoSeleccionado}
      onChange={(e) => setJuegoSeleccionado(e.target.value)}
    >
      <option value="">-- Selecciona un juego --</option>
      {juegosDisponibles.map(j => (
        <option key={j} value={j}>{j}</option>
      ))}
    </select>
  </div>
);

export default SelectorJuego;
