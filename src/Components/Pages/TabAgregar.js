import React from 'react';
import SeleccionarPokemon from '../UI/SeleccionarPokemon';
import './TabAgregar.css';

const TabAgregar = ({ agregarPokemonAlTeam, borrarSavefile, exportarSesion, importarSesionDesdeArchivo }) => {
  return (
    <div className="tab-agregar">
      <div className="agregar-contenido">
        <h2 className="titulo-seccion">Agregar a Mi Equipo</h2>

        <div className="botonera-sesion">
          <button className="btn-sesion" onClick={borrarSavefile}>Borrar</button>
          <button className="btn-sesion" onClick={exportarSesion}>Exportar</button>
          <label className="btn-sesion importar">
            Importar
            <input type="file" accept="application/json" onChange={importarSesionDesdeArchivo} hidden />
          </label>
        </div>

        <div className="selector-centrado">
          <SeleccionarPokemon onAddPokemon={(pokemon) => agregarPokemonAlTeam(pokemon, 'miEquipo')} />
        </div>
      </div>
    </div>
  );
};

export default TabAgregar;
