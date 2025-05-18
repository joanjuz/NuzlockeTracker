import React from 'react';
import { useDrag } from 'react-dnd';
import './DraggablePokemon.css';

const DraggablePokemon = ({ pokemon, onDelete }) => {
  const [{ isDragging }, drag] = useDrag(() => ({
    type: 'POKEMON',
    item: { ...pokemon },
    collect: (monitor) => ({
      isDragging: !!monitor.isDragging(),
    }),
  }));

  const statLabels = {
    hp: "HP",
    attack: "Atk",
    defense: "Def",
    "special-attack": "SpA",
    "special-defense": "SpD",
    speed: "Spe"
  };

  return (
    <div
      ref={drag}
      className={`draggable-card ${isDragging ? 'dragging' : ''}`}
    >
      <div className="sprite-stats">
        <div className="header">
          <div className="types">
            {pokemon.types.map((type) => (
              <span key={type} className={`tipo-tag ${type}`}>
                {type}
              </span>
            ))}
          </div>
          <button className="close-btn" onClick={() => onDelete(pokemon)}>
            ×
          </button>
        </div>
        <img className="sprite-img" src={pokemon.sprite} alt={pokemon.name} />
        <h4>{pokemon.nickname || pokemon.name}</h4>
        {pokemon.baseStats ? (
          <div className="stats-list">
            {Object.entries(pokemon.baseStats).map(([stat, value]) => (
              <div className="stat-row" key={stat}>
                <span className="stat-label">{statLabels[stat] || stat}</span>
                <div className="stat-bar-container">
                  <div className="stat-bar" style={{ width: `${value / 2}%` }} />
                </div>
                <span className="stat-value">{value}</span>
              </div>
            ))}
          </div>
        ) : (
          <p className="stats-placeholder">Cargando stats...</p>
        )}
      </div>
    </div>
  );
};

export default DraggablePokemon;
