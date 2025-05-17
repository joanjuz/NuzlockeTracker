// TabAgregar.js
import React from 'react';
import SeleccionarPokemon from '../UI/SeleccionarPokemon';

const TabAgregar = ({ agregarPokemonAlTeam, borrarSavefile, exportarSesion, importarSesionDesdeArchivo }) => {
  return (
    <div style={{ display: 'flex', fontSize: '1.2em', padding: '10px', gap: '10px' }}>
      <div style={{ flex: 1 }}>
        <h2 className="titulo bold" style={{ fontSize: '1.4em', margin: '5px 0' }}>
          Agregar a Mi Equipo
        </h2>

        <div className="botonera-sesion-minimal">
          <button className="btn-min" onClick={borrarSavefile}>
            Borrar
          </button>

          <button className="btn-min" onClick={exportarSesion}>
            Exportar
          </button>

          <label className="btn-min importar">
            Importar
            <input
              type="file"
              accept="application/json"
              onChange={importarSesionDesdeArchivo}
              style={{ display: 'none' }}
            />
          </label>
        </div>

        <div className="centrado">
          <SeleccionarPokemon onAddPokemon={(pokemon) => agregarPokemonAlTeam(pokemon, 'miEquipo')} />
        </div>
      </div>
    </div>
  );
};

export default TabAgregar;
