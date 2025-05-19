// ResumenDebilidades.js
import React from 'react';
import './ResumenDebilidades.css'; // Asegurate de tener este archivo o incluir en otro como TeamTracker.css

const ResumenDebilidades = ({ activos, getX2Weaknesses, onSeleccionar }) => {
  return (
    <div className="team-summary">
      <h3 className="titulo bold">Resumen de debilidades (x2) por Pokémon:</h3>
      <div className="summary-columns">
        {activos.map((pokemon, index) => (
          <div
            key={index}
            className="resumen-card"
            onClick={() => onSeleccionar(pokemon)}
          >
            <h4>{pokemon.name}</h4>
            <ul className="boxTipo">
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
            <div className="move-summary">
              <h5 className="titulo-movimiento">Movimientos:</h5>
              {pokemon.moves && pokemon.moves.length > 0 ? (
                <ul>
                  {pokemon.moves.map((move, idx) => (
                    <li key={idx}>
                      <span className={`tipo ${move.type.toLowerCase()}`}>
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
