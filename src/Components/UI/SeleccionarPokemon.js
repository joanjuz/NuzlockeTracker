// SeleccionarPokemon.js
import React from 'react';
import Select from 'react-select';
import useSeleccionarPokemon from './useSeleccionarPokemon';
import SpriteYTipos from './SpriteYTipos';
import DebilidadesResumen from './DebilidadesResumen';
import BotonAgregar from './BotonAgregar';
import ModalIntegracion from './ModalIntegracion';
import './Pokemon.css';
import './tipos.css';

const SeleccionarPokemon = ({ onAddPokemon }) => {
  const {
    pokemonOptions,
    selectedPokemon,
    setSelectedPokemon,
    sprite,
    types,
    weaknesses,
    pokemonTypeCounts,  // 👈 lo usas acá
    error,
    showModal,
    setShowModal
  } = useSeleccionarPokemon();

  return (
    <div className="selector-container" style={{ textAlign: 'center', maxWidth: '400px', margin: '0 auto' }}>
      <h3 style={{ marginBottom: '10px' }}>Seleccionar Pokémon</h3>
      <Select
        options={pokemonOptions}
        onChange={setSelectedPokemon}
        placeholder="Buscar Pokémon..."
        isClearable
      />

      {error && <p style={{ color: 'red' }}>{error}</p>}

      <SpriteYTipos sprite={sprite} types={types} />
      <DebilidadesResumen pokemonTypeCounts={pokemonTypeCounts} />
      <BotonAgregar disabled={!selectedPokemon || !sprite} onClick={() => setShowModal(true)} />
      <ModalIntegracion
        showModal={showModal}
        setShowModal={setShowModal}
        selectedPokemon={selectedPokemon}
        sprite={sprite}
        types={types}
        weaknesses={weaknesses}
        onAddPokemon={onAddPokemon}
      />
    </div>
  );
};

export default SeleccionarPokemon;
