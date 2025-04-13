// PaginaPrincipal.js
import React, { useState } from 'react';
import Header from './Header.js';
import SeleccionarPokemon from './SeleccionarPokemon';
import TeamTracker from './TeamTracker';

const PaginaPrincipal = () => {
  const [activeTab, setActiveTab] = useState("agregar");

  // Estados para cada equipo
  const [miEquipo, setMiEquipo] = useState([]);
  const [rivalTeam, setRivalTeam] = useState([]);

  // Función para agregar un Pokémon a uno de los dos equipos
  const agregarPokemonAlTeam = (pokemon, teamType) => {
    if (teamType === "miEquipo") {
      setMiEquipo((prevTeam) => [...prevTeam, pokemon]);
    } else if (teamType === "rivalTeam") {
      setRivalTeam((prevTeam) => [...prevTeam, pokemon]);
    }
  };

  // Función para eliminar un Pokémon de uno de los equipos (usando el índice)
  const eliminarPokemonDelTeam = (index, teamType) => {
    if (teamType === "miEquipo") {
      setMiEquipo((prevTeam) => prevTeam.filter((_, idx) => idx !== index));
    } else if (teamType === "rivalTeam") {
      setRivalTeam((prevTeam) => prevTeam.filter((_, idx) => idx !== index));
    }
  };

  const addMoveToPokemon = (pokemon, move) => {
    // Actualiza el estado de forma inmutable o forzada
    setMiEquipo([...miEquipo]);
    setRivalTeam([...rivalTeam]);
  };

  return (
    <div style={{ padding: '20px' }}>
      <Header activeTab={activeTab} setActiveTab={setActiveTab} />

      {activeTab === "agregar" ? (
        <div style={{ display: 'flex', fontSize: '1.2em', padding: '10px', gap: '10px' }}>
          <div style={{ flex: 1 }}>
            <h2 className="titulo bold" style={{ fontSize: '1.4em', margin: '5px 0' }}>
              Agregar a Mi Equipo
            </h2>
            <SeleccionarPokemon
              onAddPokemon={(pokemon) => agregarPokemonAlTeam(pokemon, "miEquipo")}
            />
          </div>
          <div style={{ flex: 1 }}>
            <h2 className="titulo bold" style={{ fontSize: '1.4em', margin: '5px 0' }}>
              Agregar al Equipo Rival
            </h2>
            <SeleccionarPokemon
              onAddPokemon={(pokemon) => agregarPokemonAlTeam(pokemon, "rivalTeam")}
            />
          </div>
        </div>
      ) : (
        <div style={{ display: 'flex' }}>
          <div style={{ marginTop: '20px', flex: 1, marginRight: '30px' }}>
            <h2 className='titulo bold'>Mi Equipo:</h2>
            <TeamTracker 
              team={miEquipo} 
              onRemovePokemon={(index) => eliminarPokemonDelTeam(index, "miEquipo")}
              onAddMove={addMoveToPokemon}
            />
          </div>
          <div style={{ marginTop: '20px', flex: 1, marginRight:'20px' }}>
            <h2 className='titulo bold'>Equipo Rival:</h2>
            <TeamTracker 
              team={rivalTeam} 
              onRemovePokemon={(index) => eliminarPokemonDelTeam(index, "rivalTeam")}
              onAddMove={addMoveToPokemon}
            />
          </div>
        </div>
      )}
    </div>
  );
};

export default PaginaPrincipal;
