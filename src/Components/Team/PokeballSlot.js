// PokeballSlots.js
import React from 'react';
import { useDrop } from 'react-dnd';
import './PokeballSlot.css';

const PokeballSlot = ({ index, pokemon, onDrop }) => {
  const [{ isOver }, drop] = useDrop({
    accept: 'POKEMON',
    drop: (dragged) => onDrop(dragged, index),
    collect: monitor => ({ isOver: !!monitor.isOver() })
  });

  return (
    <div ref={drop} className={`pokeball-slot ${isOver ? 'hover' : ''}`}>
      {pokemon ? (
        <img src={pokemon.sprite} alt={pokemon.name} className="sprite" />
      ) : (
        <img src="/pokeball-empty.png" alt="Empty" className="placeholder" />
      )}
    </div>
  );
};

export default PokeballSlot;
