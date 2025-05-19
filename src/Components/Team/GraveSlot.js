// GraveSlot.js
import React from 'react';
import { useDrop } from 'react-dnd';
import './PokeballSlot.css'; // reutilizamos los estilos base

const GraveSlot = ({ onDropToGrave }) => {
  const [{ isOver }, drop] = useDrop({
    accept: 'POKEMON',
    drop: (draggedPokemon) => {
      if (onDropToGrave) {
        onDropToGrave(draggedPokemon);
      }
    },
    collect: (monitor) => ({
      isOver: !!monitor.isOver(),
    }),
  });

  return (
    <div
      ref={drop}
      className={`grave-slot ${isOver ? 'grave-hover' : ''}`}
      title="Arrastra aquí para enviar al cementerio"
    >
    </div>
  );
};

export default GraveSlot;
