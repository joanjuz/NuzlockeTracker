// Caja.js
import React from 'react';
import SpriteYTipos from '../UI/SpriteYTipos';
import './Caja.css';

const Caja = ({ team, onChangeEstado, onRemovePokemon }) => {
  const renderBotonesEstado = (pokemon, index) => {
    const estadoActual = pokemon.estado;
    const estados = ['activo', 'caja', 'cementerio'];
    const disponibles = estados.filter(e => e !== estadoActual);

    const getLabel = (estado) => {
      if (estado === 'activo') return 'Activo';
      if (estado === 'caja') return 'Caja';
      if (estado === 'cementerio') return 'Cementerio';
      return '';
    };

    return (
      <div className="acciones-caja" style={{ marginTop: '8px' }}>
        {disponibles.map((estado, idx) => (
          <button
            key={idx}
            className={`btn ${estado === 'cementerio' ? 'rojo' :
                estado === 'activo' ? 'verde' :
                  estado === 'caja' ? 'azul' : ''
              }`}
            onClick={() => onChangeEstado(index, 'miEquipo', estado)}
          >
            {getLabel(estado)}
          </button>
        ))}
        <button
          className="btn gris"
          onClick={() => onRemovePokemon(index, 'miEquipo')}
        >
          Eliminar
        </button>
      </div>
    );
  };

  return (
    <div className="caja-container">
      <h2 className="titulo">Gestión de Pokémon</h2>
      <div
        className="grid-caja"
        style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '12px' }}
      >
        {team.map((pokemon, index) => (
          <div
            key={index}
            className="card-caja"
            style={{
              padding: '10px',
              border: '1px solid #ccc',
              borderRadius: '8px',
              textAlign: 'center',
            }}
          >
            <SpriteYTipos sprite={pokemon.sprite} types={pokemon.types} />
            <p><strong>{pokemon.nickname || pokemon.name}</strong></p>
            <p style={{ fontSize: '0.85em', color: '#555' }}>
              <em>{pokemon.estado}</em>
            </p>
            {renderBotonesEstado(pokemon, index)}
          </div>
        ))}
      </div>
    </div>
  );
};

export default Caja;
