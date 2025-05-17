// AltoMandoPanel.js
import React from 'react';

const AltoMandoPanel = ({ altoMando, toggleAltoMando }) => (
  <div className="bitacora-seccion">
    <h3 className="bitacora-subtitulo">👑 Alto Mando derrotado</h3>
    <div className="bitacora-grid">
      {altoMando.map((e, i) => (
        <label key={i} className={`bitacora-card alto ${e ? 'activa' : ''}`}>
          <input type="checkbox" checked={e} onChange={() => toggleAltoMando(i)} />
          Alto Mando {i + 1}
        </label>
      ))}
    </div>
  </div>
);

export default AltoMandoPanel;
