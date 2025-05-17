// ResumenDebilidades.js
import React from 'react';

const ResumenDebilidades = ({ activos, getX2Weaknesses, onSeleccionar }) => {
  return (
    <div className="team-summary">
      <h3 className="titulo bold">Resumen de debilidades (x2) por Pokémon:</h3>
      <div className="summary-columns" style={{ display: 'flex' }}>
        {activos.map((pokemon, index) => (
          <div
            key={index}
            onClick={() => onSeleccionar(pokemon)}
            style={{
              flex: 1,
              border: '1px solid #ccc',
              margin: '4px',
              padding: '4px',
              textAlign: 'center',
            }}
          >
            <h4>{pokemon.name}</h4>
            <ul style={{ listStyle: 'none', padding: 0 }}>
              {getX2Weaknesses(pokemon).length > 0 ? (
                getX2Weaknesses(pokemon).map((weakness, i) => (
                  <li key={i} className={`tipo ${weakness}`}>
                    {weakness}
                  </li>
                ))
              ) : (
                <li>No x2 Weakness</li>
              )}
            </ul>
            <div style={{ marginTop: '10px' }}>
              <h5>Movimientos:</h5>
              {pokemon.moves && pokemon.moves.length > 0 ? (
                <ul style={{ listStyle: 'none', padding: 0 }}>
                  {pokemon.moves.map((move, idx) => (
                    <li
                      key={idx}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        marginBottom: '4px',
                      }}
                    >
                      <span
                        className={`tipo ${move.type.toLowerCase()}`}
                        style={{
                          width: '100px',
                          display: 'block',
                          textAlign: 'center',
                        }}
                      >
                        {move.name}
                      </span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p>No hay movimientos asignados.</p>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default ResumenDebilidades;