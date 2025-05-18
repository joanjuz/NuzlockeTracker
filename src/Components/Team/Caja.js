import React from 'react';
import PokeballSlot from './PokeballSlot';
import ZonaDrop from './ZonaDrop';
import GraveSlot from './GraveSlot';
import './Caja.css';

const Caja = ({ team, setTeam }) => {
  const activos = team.filter(p => p.estado === 'activo');
  const enCaja = team.filter(p => p.estado === 'caja');
  const muertos = team.filter(p => p.estado === 'muertos');

  const handleDelete = (pokeToDelete) => {
    const updated = team.filter(p =>
      !(p.name === pokeToDelete.name && p.nickname === pokeToDelete.nickname)
    );
    setTeam(updated);
  };

  const moverAPokemonACaja = (pokemon) => {
    const nuevoTeam = [...team];
    const idx = nuevoTeam.findIndex(p =>
      p.name === pokemon.name && p.nickname === pokemon.nickname
    );
    if (idx !== -1) {
      nuevoTeam[idx].estado = 'caja';
      setTeam(nuevoTeam);
    }
  };

  const moverAPokemonAlCementerio = (pokemon) => {
    const nuevoTeam = [...team];
    const idx = nuevoTeam.findIndex(p =>
      p.name === pokemon.name && p.nickname === pokemon.nickname
    );
    if (idx !== -1) {
      nuevoTeam[idx].estado = 'muertos';
      setTeam(nuevoTeam);
    }
  };

  const handleDropToSlot = (draggedPokemon, slotIndex) => {
    const nuevoTeam = [...team];

    // Ver si ya hay un Pokémon en ese slot activo
    const activosIndices = team
      .map((p, i) => (p.estado === 'activo' ? i : -1))
      .filter(i => i !== -1);

    const idxAnterior = activosIndices[slotIndex];
    if (idxAnterior !== undefined) {
      nuevoTeam[idxAnterior].estado = 'caja';
    }

    const idxDrag = nuevoTeam.findIndex(p =>
      p.name === draggedPokemon.name && p.nickname === draggedPokemon.nickname
    );

    if (idxDrag !== -1) {
      nuevoTeam[idxDrag].estado = 'activo';
      setTeam(nuevoTeam);
    } else {
      console.warn('❗ No se encontró el Pokémon arrastrado:', draggedPokemon);
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
            onDrop={handleDropToSlot}
            onClick={moverAPokemonACaja}
          />
        ))}
        <GraveSlot onDropToGrave={moverAPokemonAlCementerio} />
      </div>

      <ZonaDrop
        titulo="Pokémon en Caja"
        lista={enCaja}
        estado="caja"
        team={team}
        setTeam={setTeam}
        onDelete={handleDelete}
      />
      {activos.length > 0 && (
        <ZonaDrop
          titulo="Pokémon Activos (Vista)"
          lista={activos}
          estado="activo"
          team={team}
          setTeam={() => { }} // no modificar
          onDelete={() => { }} // prevenir eliminación
          soloLectura={true} // si decides usar una prop para evitar acciones
        />
      )}


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
