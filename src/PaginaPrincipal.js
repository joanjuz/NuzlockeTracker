import React from 'react';
import SeleccionarAtaque from './SeleccionarAtaque';
import SeleccionarPokemon from './SeleccionarPokemon';

const PaginaPrincipal = () => {
  return (
    <div style={{ display: 'flex' }}>
      <div style={{ flex: 1 }}>
        <SeleccionarAtaque />
      </div>
      <div style={{ flex: 1 }}>
        <SeleccionarPokemon />
      </div>
      <div style={{ flex: 1 }}>
        <SeleccionarAtaque />
      </div>
      <div style={{ flex: 1 }}>
        <SeleccionarPokemon />
      </div>
    </div>
  );
};

export default PaginaPrincipal;
