// DetallesPokemon.js
import React from 'react';
import Select from 'react-select';

const DetallesPokemon = ({
  pokemon,
  getX2Weaknesses,
  showMovesDetails,
  setShowMovesDetails,
  showMoveSelector,
  setShowMoveSelector,
  moveOptions,
  handleMoveSelect,
  handleRemoveMove,
}) => {
  return (
    <div className="pokemon-details" style={{ marginTop: '20px' }}>
      <h3>Detalles de {pokemon.name}</h3>
      <img src={pokemon.sprite} alt={pokemon.name} width="96" />

      <p><strong>Tipos:</strong></p>
      <ul className="boxTipo">
        {pokemon.types.map((type) => (
          <li key={type} className={`tipo ${type.toLowerCase()}`}>{type}</li>
        ))}
      </ul>

      <p><strong>Debilidades (x2):</strong></p>
      <ul style={{ listStyle: 'none', padding: 0 }}>
        {getX2Weaknesses(pokemon).length > 0 ? (
          getX2Weaknesses(pokemon).map((w, i) => (
            <li key={i} className={`tipo ${w}`}>{w}</li>
          ))
        ) : (
          <li>No x2 Weakness</li>
        )}
      </ul>

      <button
        className="btn"
        onClick={() => setShowMovesDetails(!showMovesDetails)}
        style={{ marginTop: '10px' }}
      >
        {showMovesDetails ? 'Ocultar Movimientos' : 'Mostrar Movimientos'}
      </button>

      {showMovesDetails && (
        <div style={{ marginTop: '20px' }}>
          <h4>Movimientos Asignados:</h4>
          {pokemon.moves?.length > 0 ? (
            <ul>
              {pokemon.moves.map((move, i) => (
                <li key={i} style={{ border: '1px solid #aaa', margin: '4px', padding: '4px' }}>
                  <strong>{move.name}</strong><br />
                  Tipo: <span className={`tipo ${move.type.toLowerCase()}`}>{move.type}</span> |
                  Clase: <span className={`tipo ${move.damageClass.toLowerCase()}`}>{move.damageClass}</span><br />
                  Daño: {move.power ?? 'N/A'} | Precisión: {move.accuracy ?? 'N/A'}<br />
                  Descripción: {move.description ?? 'N/A'}<br />
                  <button
                    className="btn tin"
                    onClick={() => handleRemoveMove(i)}
                    style={{ marginTop: '4px' }}
                  >
                    Eliminar
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p>No hay movimientos asignados.</p>
          )}

          {showMoveSelector ? (
            <Select options={moveOptions} onChange={handleMoveSelect} placeholder="Buscar movimiento..." />
          ) : (
            <button className="btn" onClick={() => setShowMoveSelector(true)}>
              Agregar Movimiento
            </button>
          )}
        </div>
      )}
    </div>
  );
};

export default DetallesPokemon;