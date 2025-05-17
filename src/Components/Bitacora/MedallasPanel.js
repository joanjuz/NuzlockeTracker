// MedallasPanel.js
import React from 'react';

const MedallasPanel = ({ medallas, toggleMedalla }) => (
  <div className="bitacora-seccion">
    <h3 className="bitacora-subtitulo">🏅 Medallas obtenidas</h3>
    <div className="bitacora-grid">
      {medallas.map((m, i) => (
        <label key={i} className={`bitacora-card ${m ? 'activa' : ''}`}>
          <input type="checkbox" checked={m} onChange={() => toggleMedalla(i)} />
          Medalla {i + 1}
        </label>
      ))}
    </div>
  </div>
);

export default MedallasPanel;
