// PaginaPrincipal.js
import React from 'react';
import Header from '../Header/Header';
import TabAgregar from './TabAgregar';
import TabEquipo from './TabEquipo';
import TabValoracion from './TabValoracion';
import TabBitacora from './TabBitacora';
import ImportarGenerar from '../Showdown/ImportarGenerar';
import useSesionManager from './useSesionManager';
import Caja from '../Team/Caja.js'; // Ajusta el path si está en otra carpeta

import '../Pages/Apps.css';

const PaginaPrincipal = () => {
  const {
    activeTab,
    setActiveTab,
    miEquipo,
    setMiEquipo,
    rivalTeam,
    agregarPokemonAlTeam,
    eliminarPokemonDelTeam,
    addMoveToPokemon,
    cambiarEstadoPokemon,
    handleImportPokemons,
    borrarSavefile,
    exportarSesion,
    importarSesionDesdeArchivo,
  } = useSesionManager();

  return (
    <div style={{ padding: '20px' }}>
      <h1 className="titulo-nuztracker">NuzTracker</h1>
      <Header activeTab={activeTab} setActiveTab={setActiveTab} />

      {activeTab === 'agregar' && (
        <TabAgregar
          agregarPokemonAlTeam={agregarPokemonAlTeam}
          borrarSavefile={borrarSavefile}
          exportarSesion={exportarSesion}
          importarSesionDesdeArchivo={importarSesionDesdeArchivo}
        />
      )}

      {activeTab === 'bitacora' && <TabBitacora />}

      {activeTab === 'equipo' && (
        <TabEquipo
          miEquipo={miEquipo}
          eliminarPokemonDelTeam={eliminarPokemonDelTeam}
          addMoveToPokemon={addMoveToPokemon}
          cambiarEstadoPokemon={cambiarEstadoPokemon}
        />
      )}

      {activeTab === 'valoracion' && <TabValoracion miEquipo={miEquipo} />}

      {activeTab === 'archivo' && (
        <ImportarGenerar team={miEquipo} onImportPokemons={handleImportPokemons} />
      )}
      {activeTab === 'caja' && (
        <Caja
          team={miEquipo}
          setTeam={setMiEquipo}
          onChangeEstado={cambiarEstadoPokemon}
          onRemovePokemon={eliminarPokemonDelTeam}
        />

      )}


    </div>
  );
};

export default PaginaPrincipal;
