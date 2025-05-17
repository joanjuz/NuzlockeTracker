// TeamTracker.js
import React from 'react';
import useTeamTrackerLogic from './useTeamTrackerLogic';
import SpriteYTipos from '../UI/SpriteYTipos';
import DetallesPokemon from './DetallesPokemon';
import ResumenDebilidades from './ResumenDebilidades';
import './TeamTracker.css';

const TeamTracker = ({ team, onAddMove }) => {
  const {
    selectedTeamPokemon,
    setSelectedTeamPokemon,
    moveOptions,
    showMoveSelector,
    setShowMoveSelector,
    showMovesDetails,
    setShowMovesDetails,
    getX2Weaknesses,
    handleMoveSelect,
    handleRemoveMoveFromTeam,
  } = useTeamTrackerLogic(team, onAddMove);

  const activos = team.filter(p => p.estado === 'activo');

  return (
    <div className="team-wrapper">
      <div className="team-tracker">
        <h2 className="titulo bold">Mi Equipo</h2>
        <div className="grid-activos" style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px' }}>
          {activos.map((pokemon, index) => (
            <div
              key={index}
              className="card-activo"
              onClick={() => setSelectedTeamPokemon(pokemon)}
              style={{ cursor: 'pointer', padding: '10px', border: '1px solid #ccc', borderRadius: '8px', textAlign: 'center' }}
            >
              <SpriteYTipos sprite={pokemon.sprite} types={pokemon.types} />
              <p><strong>{pokemon.nickname || pokemon.name}</strong></p>
            </div>
          ))}
        </div>

        <ResumenDebilidades
          activos={activos}
          getX2Weaknesses={getX2Weaknesses}
          onSeleccionar={setSelectedTeamPokemon}
        />

        {selectedTeamPokemon && (
          <DetallesPokemon
            pokemon={selectedTeamPokemon}
            getX2Weaknesses={getX2Weaknesses}
            showMovesDetails={showMovesDetails}
            setShowMovesDetails={setShowMovesDetails}
            showMoveSelector={showMoveSelector}
            setShowMoveSelector={setShowMoveSelector}
            moveOptions={moveOptions}
            handleMoveSelect={handleMoveSelect}
            handleRemoveMove={(i) =>
              handleRemoveMoveFromTeam(team.indexOf(selectedTeamPokemon), i)
            }
          />
        )}
      </div>
    </div>
  );
};

export default TeamTracker;