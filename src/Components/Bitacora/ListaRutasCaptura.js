// ListaRutasCaptura.js
import React from 'react';

const ListaRutasCaptura = ({ juegoSeleccionado, rutasDisponibles, rutasCapturadas, toggleRuta, categorizarRutas }) => {
  if (!juegoSeleccionado || rutasDisponibles.length === 0) return null;

  const rutasPorCategoria = categorizarRutas(rutasDisponibles);

  return (
    <div className="bitacora-seccion">
      <h3 className="bitacora-subtitulo">📍 Rutas de Captura</h3>
      {Object.entries(rutasPorCategoria).map(([grupo, nombres]) => (
        <div key={grupo} style={{ marginBottom: '20px' }}>
          <h4 style={{ color: '#2c3e50', borderBottom: '1px solid #ccc' }}>{grupo}</h4>
          <div className="bitacora-grid">
            {nombres.map((nombre) => (
              <label key={nombre} className={`bitacora-card ruta ${rutasCapturadas[nombre] ? 'activa' : ''}`}>
                <input
                  type="checkbox"
                  checked={!!rutasCapturadas[nombre]}
                  onChange={() => toggleRuta(nombre)}
                />
                {nombre}
              </label>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
};

export default ListaRutasCaptura;
