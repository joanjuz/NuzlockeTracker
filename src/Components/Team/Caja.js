import React from 'react';
import PokeballSlot from './PokeballSlot';
import DraggablePokemon from './DraggablePokemon';
import ZonaDrop from './ZonaDrop'; // nuevo componente externo
import './Caja.css';

const Caja = ({ team, setTeam }) => {
  const activos = team.filter(p => p.estado === 'activo');
  const enCaja = team.filter(p => p.estado === 'caja');
  const muertos = team.filter(p => p.estado === 'muertos');

  const handleDelete = (index) => {
    const updated = [...team];
    updated.splice(index, 1);
    setTeam(updated);
  };

  const handleDropToSlot = (draggedPokemon, slotIndex) => {
  const nuevoTeam = [...team];
  const anterior = team.filter(p => p.estado === 'activo')[slotIndex];

  if (anterior) {
    const idxAnterior = nuevoTeam.findIndex(p =>
      p.name === anterior.name &&
      p.nickname === anterior.nickname
    );
    if (idxAnterior !== -1) {
      nuevoTeam[idxAnterior].estado = 'caja';
    }
  }

  const idxDrag = nuevoTeam.findIndex(p =>
    p.name === draggedPokemon.name &&
    p.nickname === draggedPokemon.nickname
  );

  if (idxDrag !== -1) {
    nuevoTeam[idxDrag].estado = 'activo';
    setTeam(nuevoTeam); // Este `setTeam` viene de props, asegúrate que esté disponible
  } else {
    console.warn('❗ No se encontró el Pokémon arrastrado en el equipo');
  }
};


  return (
    <div className="caja-container">
      <h2 className="titulo">Gestión de Pokémon</h2>

      <div className="pokeball-slots">
        {[0, 1, 2, 3, 4, 5].map((i) => (
          <PokeballSlot
            key={i}
            index={i}
            pokemon={activos[i] || null}
            onDrop={(pokemon) => handleDropToSlot(pokemon, i)}
          />
        ))}
      </div>

      <ZonaDrop
        titulo="Pokémon en Caja"
        lista={enCaja}
        estado="caja"
        team={team}
        setTeam={setTeam}
        onDelete={handleDelete}
      />

      {muertos.length > 0 && (
        <ZonaDrop
          titulo="Pokémon Muertos"
          lista={muertos}
          estado="muertos"
          team={team}
          setTeam={setTeam}
          onDelete={handleDelete}
        />
      )}
    </div>
  );
};

export default Caja;
