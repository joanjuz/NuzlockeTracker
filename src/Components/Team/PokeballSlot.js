import React, { useState } from 'react';
import { useDrop } from 'react-dnd';
import './PokeballSlot.css';

const PokeballSlot = ({ index, pokemon, onDrop, onClick }) => {
  const [clicked, setClicked] = useState(false);

  const [{ isOver }, drop] = useDrop({
    accept: 'POKEMON',
    drop: (draggedPokemon) => onDrop(draggedPokemon, index),
    collect: (monitor) => ({
      isOver: !!monitor.isOver(),
    }),
  });

  const handleClick = () => {
    if (pokemon && onClick) {
      setClicked(true);
      onClick(pokemon);
      setTimeout(() => setClicked(false), 200); // animación breve
    }
  };

  return (
    <div
      ref={drop}
      className={`pokeball-slot ${isOver ? 'hover' : ''} ${pokemon ? 'clickable' : ''} ${clicked ? 'clicked' : ''}`}
      onClick={handleClick}
    >
      {pokemon ? (
        <img src={pokemon.sprite} alt={pokemon.name} className="sprite" />
      ) : (
        <div className="circle-placeholder" />
      )}
    </div>
  );
};

export default PokeballSlot;
