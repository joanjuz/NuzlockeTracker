import React from 'react';
import PokemonModal from '../Modals/PokemonModal';

const ModalIntegracion = ({ showModal, setShowModal, selectedPokemon, sprite, types, weaknesses, onAddPokemon }) => {
  if (!showModal) return null;

  const cerrar = () => setShowModal(false);

  const agregar = (pokemon) => {
    onAddPokemon(pokemon);
    cerrar();
  };

  return (
    <PokemonModal
      pokemon={{
        name: selectedPokemon.value,
        sprite,
        types,
        weaknesses
      }}
      onSave={agregar}
      onClose={cerrar}
    />
  );
};

export default ModalIntegracion;
