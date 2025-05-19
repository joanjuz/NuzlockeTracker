// TeamTracker.js
import React, { useEffect, useState } from 'react';
import useTeamTrackerLogic from './useTeamTrackerLogic';
import SpriteYTipos from '../UI/SpriteYTipos';
import DetallesPokemon from './DetallesPokemon';
import ResumenDebilidades from './ResumenDebilidades';
import { getNextEvolution } from '../../Services/API';
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
    evolucionarPokemon
  } = useTeamTrackerLogic(team, onAddMove);

  const activos = team.filter(p => p.estado === 'activo');
  const [evolucionesDisponibles, setEvolucionesDisponibles] = useState({});

  useEffect(() => {
    const cargarEvoluciones = async () => {
      const result = {};
      for (let pokemon of activos) {
        const evo = await getNextEvolution(pokemon.name);
        if (evo) result[pokemon.name] = evo;
      }
      setEvolucionesDisponibles(result);
    };
    cargarEvoluciones();
  }, [team]);

  const mostrarRequisitos = (evo) => {
    if (!evo) return null;
    const detalles = [];
    if (evo.min_level) detalles.push(`Nivel ${evo.min_level}`);
    if (evo.item) detalles.push(`Usar ${evo.item}`);
    if (!evo.min_level && !evo.item && evo.trigger) detalles.push(`Por ${evo.trigger}`);
    return detalles.join(' / ');
  };

  return (
    <div className="team-wrapper">
      <div className="team-tracker">
        <h2 className="titulo bold">Mi Equipo</h2>
        <div className="grid-activos" style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px' }}>
          {activos.map((pokemon, index) => {
            const evo = evolucionesDisponibles[pokemon.name];
            return (
              <div
                key={index}
                className="card"
                onClick={() => setSelectedTeamPokemon(pokemon)}
                style={{ cursor: 'pointer' }}
              >

                <SpriteYTipos sprite={pokemon.sprite} types={pokemon.types} />
                <p><strong>{pokemon.nickname || pokemon.name}</strong></p>
                {Array.isArray(evo) && evo.length > 0 ? (
                  <>
                    <p className="texto-evolucion">Puede evolucionar a:</p>
                    <ul style={{ paddingLeft: '1rem', marginBottom: '0.5rem' }}>
                      {evo.map((opcion, i) => (
                        <li key={i}>
                          <strong>{opcion.name}</strong> - {mostrarRequisitos(opcion)}
                          <button
                            className="btn evolucionar"
                            style={{ marginLeft: '8px' }}
                            onClick={(e) => {
                              e.stopPropagation();
                              evolucionarPokemon(team.indexOf(pokemon), opcion.name);
                            }}
                          >
                            Elegir
                          </button>
                        </li>
                      ))}
                    </ul>
                  </>
                ) : evo && typeof evo === 'object' && evo.name ? (
                  <>
                    <p className="texto-evolucion">
                      Evoluciona a <strong>{evo.name}</strong>
                      <br /><span style={{ color: '#888' }}>{mostrarRequisitos(evo)}</span>
                    </p>
                    <button
                      className="btn evolucionar"
                      onClick={(e) => {
                        e.stopPropagation();
                        evolucionarPokemon(team.indexOf(pokemon), evo.name);
                      }}
                    >
                      Evolucionar
                    </button>
                  </>
                ) : null}


              </div>
            );
          })}
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