// DraggablePokemon.js
import React from 'react';
import { useDrag } from 'react-dnd';
import SpriteYTipos from '../UI/SpriteYTipos';
import './DraggablePokemon.css';

const DraggablePokemon = ({ pokemon, index, onDelete }) => {
  const [{ isDragging }, drag] = useDrag({
    type: 'POKEMON',
    item: { ...pokemon, index },
    collect: (monitor) => ({
      isDragging: monitor.isDragging(),
    }),
  });

  return (
    <div ref={drag} className={`card card-caja ${isDragging ? 'dragging' : ''}`}>
      <button className="btn-x" onClick={() => onDelete(index)} title="Eliminar">
        <svg width="14" height="14" viewBox="0 0 24 24">
          <line x1="18" y1="6" x2="6" y2="18" stroke="currentColor" strokeWidth="2" />
          <line x1="6" y1="6" x2="18" y2="18" stroke="currentColor" strokeWidth="2" />
        </svg>
      </button>
      <SpriteYTipos sprite={pokemon.sprite} types={pokemon.types} />
      <p><strong>{pokemon.nickname || pokemon.name}</strong></p>
      <p className="estado-texto"><em>{pokemon.estado}</em></p>
    </div>
  );
};

export default DraggablePokemon;