// TabEquipo.js
import React from 'react';
import TeamTracker from '../Team/TeamTracker';

const TabEquipo = ({ miEquipo, eliminarPokemonDelTeam, addMoveToPokemon, cambiarEstadoPokemon }) => {
  return (
    <div style={{ display: 'flex' }}>
      <div style={{ marginTop: '20px', flex: 1, marginRight: '30px' }}>
        <TeamTracker
          team={miEquipo}
          onRemovePokemon={(index) => eliminarPokemonDelTeam(index, 'miEquipo')}
          onAddMove={addMoveToPokemon}
          onChangeEstado={(index, teamType, nuevoEstado) =>
            cambiarEstadoPokemon(index, teamType, nuevoEstado)
          }
        />
      </div>
    </div>
  );
};

export default TabEquipo;
