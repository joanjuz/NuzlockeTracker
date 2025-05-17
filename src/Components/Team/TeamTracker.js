// TeamTracker.js
import React from 'react';
import useTeamTrackerLogic from './useTeamTrackerLogic';
import PokemonCard from './PokemonCard';
import ResumenDebilidades from './ResumenDebilidades';
import DetallesPokemon from './DetallesPokemon';
import './TeamTracker.css';

const TeamTracker = ({ team, onRemovePokemon, onAddMove, onChangeEstado }) => {
  const {
    selectedTeamPokemon,
    setSelectedTeamPokemon,
    moveOptions,
    showMoveSelector,
    setShowMoveSelector,
    showMovesDetails,
    setShowMovesDetails,
    mostrarLista,
    setMostrarLista,
    getX2Weaknesses,
    dividirPorEstado,
    handleMoveSelect,
    handleRemoveMoveFromTeam,
  } = useTeamTrackerLogic(team, onAddMove);

  const renderListado = (lista, estadoActual) => (
    <ul>
      {lista.map((pokemon) => {
        const realIndex = team.findIndex(p => p.nickname === pokemon.nickname && p.name === pokemon.name);
        return (
          <PokemonCard
            key={realIndex}
            pokemon={pokemon}
            realIndex={realIndex}
            estadoActual={estadoActual}
            onChangeEstado={onChangeEstado}
            onRemovePokemon={onRemovePokemon}
            onClick={() => setSelectedTeamPokemon(pokemon)}
          />
        );
      })}
    </ul>
  );

  return (
    <div className="team-wrapper">
      <div className="team-tracker">
        <h2 className="titulo bold">Team Tracker</h2>
        <button
          className="btn"
          onClick={() => setMostrarLista(prev => !prev)}
          style={{ marginBottom: '10px' }}
        >
          {mostrarLista ? 'Ocultar Lista' : 'Mostrar Lista'}
        </button>

        {mostrarLista && (
          <div className="leyenda-estado" style={{ marginBottom: '10px', fontWeight: 'bold' }}>
            <span style={{ color: '#2ecc71' }}>🟢 Activo</span> |{' '}
            <span style={{ color: '#3498db' }}>📦 Caja</span> |{' '}
            <span style={{ color: '#e74c3c' }}>☠ Cementerio</span>
          </div>
        )}

        {mostrarLista && (
          <>
            <h3>Equipo Activo</h3>
            {renderListado(dividirPorEstado('activo'), 'activo')}

            <h3>Caja</h3>
            {renderListado(dividirPorEstado('caja'), 'caja')}

            <h3>Cementerio</h3>
            {renderListado(dividirPorEstado('cementerio'), 'cementerio')}
          </>
        )}

        <ResumenDebilidades
          activos={dividirPorEstado('activo')}
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
            handleRemoveMove={(index) =>
              handleRemoveMoveFromTeam(team.indexOf(selectedTeamPokemon), index)
            }
          />
        )}
      </div>
    </div>
  );
};

export default TeamTracker;