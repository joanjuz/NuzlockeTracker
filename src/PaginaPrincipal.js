// PaginaPrincipal.js
import React, { useState } from 'react';
import SeleccionarAtaque from './SeleccionarAtaque';
import SeleccionarPokemon from './SeleccionarPokemon';
import TeamTracker from './TeamTracker';

const PaginaPrincipal = () => {
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

  return (
    <div style={{ padding: '20px'}}>
      <h1 className='titulo bold'>Tracker Pokémon</h1>
      <div style={{ display: 'flex' }}>
        {/* Sección para selección de ataques (se mantiene igual) */}
        <div style={{ flex: 1 }}>
          <SeleccionarAtaque />
        </div>
        {/* Sección para selección de Pokémon */}
        <div style={{ flex: 1 }}>
          {/* Puedes incluir un selector extra para elegir a qué equipo agregar o dos instancias separadas */}
          {/* Aquí se muestran dos instancias del componente SeleccionarPokemon, cada una asociada a un equipo */}
          <h2 className='titulo bold'>Agregar a Mi Equipo</h2>
          <SeleccionarPokemon
            onAddPokemon={(pokemon) => agregarPokemonAlTeam(pokemon, "miEquipo")}
          />
        </div>
        <div style={{ flex: 1 }}>
          <h2 className='titulo bold'>Agregar al Equipo Rival</h2>
          <SeleccionarPokemon
            onAddPokemon={(pokemon) => agregarPokemonAlTeam(pokemon, "rivalTeam")}
          />
        </div>
      </div>
      <div style={{ display: 'flex' }}>
        {/* Visualización de los equipos */}
        <div style={{ marginTop: '20px', flex: 1 }}>
          <h2>Mi Equipo:</h2>
          <TeamTracker team={miEquipo} onRemovePokemon={(index) => eliminarPokemonDelTeam(index, "miEquipo")} />
        </div>
        <div style={{ marginTop: '20px', flex: 1 }}>
          <h2>Equipo Rival:</h2>
          <TeamTracker team={rivalTeam} onRemovePokemon={(index) => eliminarPokemonDelTeam(index, "rivalTeam")} />
        </div>
      </div>
    </div>
  );
};

export default PaginaPrincipal;
