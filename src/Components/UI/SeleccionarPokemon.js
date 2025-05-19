import React from 'react';
import Select from 'react-select';
import useSeleccionarPokemon from './useSeleccionarPokemon';
import SpriteYTipos from './SpriteYTipos';
import DebilidadesResumen from './DebilidadesResumen';
import BotonAgregar from './BotonAgregar';
import ModalIntegracion from './ModalIntegracion';
import './SeleccionarPokemon.css';

const SeleccionarPokemon = ({ onAddPokemon }) => {
  const {
    pokemonOptions,
    selectedPokemon,
    setSelectedPokemon,
    sprite,
    types,
    weaknesses,
    baseStats,
    pokemonTypeCounts,
    error,
    showModal,
    setShowModal
  } = useSeleccionarPokemon();

  return (
    <div className="selector-container">
      <h3 className="selector-title">Seleccionar Pokémon</h3>

      <Select
        className="react-select-container"
        classNamePrefix="react-select"
        options={pokemonOptions}
        onChange={setSelectedPokemon}
        placeholder="Buscar Pokémon..."
        isClearable
      />

      {error && <p className="error-msg">{error}</p>}

      {selectedPokemon && (
        <>
          <SpriteYTipos sprite={sprite} types={types} />
          <DebilidadesResumen pokemonTypeCounts={pokemonTypeCounts} />
          <BotonAgregar disabled={!sprite} onClick={() => setShowModal(true)} />
        </>
      )}

      <ModalIntegracion
        showModal={showModal}
        setShowModal={setShowModal}
        selectedPokemon={selectedPokemon}
        sprite={sprite}
        types={types}
        weaknesses={weaknesses}
        baseStats={baseStats} 
        onAddPokemon={onAddPokemon}
      />
    </div>
  );
};

export default SeleccionarPokemon;
