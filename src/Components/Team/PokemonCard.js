// PokemonCard.js
import React from 'react';

const PokemonCard = ({ pokemon, realIndex, estadoActual, onChangeEstado, onRemovePokemon, onClick }) => {
  return (
    <li style={{ display: 'flex', alignItems: 'center', marginBottom: '8px' }}>
      <img src={pokemon.sprite} alt={pokemon.name} style={{ width: '48px', marginRight: '10px' }} />
      <div style={{ flexGrow: 1 }} onClick={onClick}>
        <strong>{pokemon.nickname || pokemon.name}</strong>
        <ul className="boxTipo" style={{ display: 'inline-block', marginLeft: '6px' }}>
          {pokemon.types.map((type) => (
            <li key={type} className={`tipo ${type.toLowerCase()}`}>{type}</li>
          ))}
        </ul>
      </div>
      <div className="botones-estado">
        {estadoActual !== "activo" && (
          <button className="btn" onClick={() => onChangeEstado(realIndex, "miEquipo", "activo")}>🟢 Activo</button>
        )}
        {estadoActual !== "caja" && (
          <button className="btn" onClick={() => onChangeEstado(realIndex, "miEquipo", "caja")}>📦 Caja</button>
        )}
        {estadoActual !== "cementerio" && (
          <button className="btn" onClick={() => onChangeEstado(realIndex, "miEquipo", "cementerio")}>☠ Cementerio</button>
        )}
        <button className="btn" onClick={() => onRemovePokemon(realIndex)}>❌</button>
      </div>
    </li>
  );
};

export default PokemonCard;