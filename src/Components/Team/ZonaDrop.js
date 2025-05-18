import React from 'react';
import { useDrop } from 'react-dnd';
import DraggablePokemon from './DraggablePokemon';

const ZonaDrop = ({ titulo, lista, estado, team, setTeam, onDelete }) => {
  const [{ isOver }, drop] = useDrop({
    accept: 'POKEMON',
    drop: (draggedPokemon) => {
      const nuevoTeam = [...team];
      const idx = nuevoTeam.findIndex(p =>
        p.name === draggedPokemon.name &&
        p.nickname === draggedPokemon.nickname
      );
      if (idx !== -1) {
        nuevoTeam[idx].estado = estado;
        setTeam(nuevoTeam);
      }
    },
    collect: (monitor) => ({
      isOver: monitor.isOver(),
    }),
  });

  return (
    <div className={`bloque-caja zona-drop ${isOver ? 'hover' : ''}`} ref={drop}>
      <h3 className="titulo">{titulo}</h3>
      <div className="grid-caja">
        {lista.map((pokemon, i) => (
          <DraggablePokemon
            key={pokemon.name + pokemon.nickname}
            pokemon={pokemon}
            onDelete={onDelete}
          />
        ))}
      </div>
    </div>
  );
};

export default ZonaDrop;
