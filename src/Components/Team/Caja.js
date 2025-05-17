// Caja.js
import React from 'react';
import SpriteYTipos from '../UI/SpriteYTipos';
import './Caja.css';

const Caja = ({ team, onChangeEstado, onRemovePokemon }) => {
  const activos = team.filter(p => p.estado === 'activo');
  const enCaja = team.filter(p => p.estado === 'caja');
  const muertos = team.filter(p => p.estado === 'muertos');

  const renderBotonesEstado = (pokemon, index) => {
    const estadoActual = pokemon.estado;
    const estados = ['activo', 'caja', 'muertos'];
    const disponibles = estados.filter(e => e !== estadoActual);

    const getLabel = (estado) => {
      if (estado === 'activo') return 'Mover a Activo';
      if (estado === 'caja') return 'Mover a Caja';
      if (estado === 'muertos') return 'Mover a Muertos';
      return '';
    };

    return (
      <div className="acciones-caja" style={{ marginTop: '8px' }}>
        {disponibles.map((estado, idx) => (
          <button
            key={idx}
            className={`btn ${
              estado === 'muertos' ? 'rojo' :
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
          onClick={() => onRemovePokemon(index)}
        >
          Eliminar
        </button>
      </div>
    );
  };

  const renderGrid = (lista, titulo) => (
    <div className="bloque-caja">
      <h3 className="titulo" style={{ marginTop: '32px' }}>{titulo}</h3>
      <div
        className="grid-caja"
        style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '12px' }}
      >
        {lista.map((pokemon, index) => (
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
            <p style={{ fontSize: '0.85em', color: '#555' }}><em>{pokemon.estado}</em></p>
            {renderBotonesEstado(pokemon, team.indexOf(pokemon))}
          </div>
        ))}
      </div>
    </div>
  );

  return (
    <div className="caja-container">
      <h2 className="titulo">Gestión de Pokémon</h2>
      {renderGrid(activos, 'Pokémon Activos')}
      {renderGrid(enCaja, 'Pokémon en Caja')}
      {muertos.length > 0 && renderGrid(muertos, 'Pokémon Muertos')}
    </div>
  );
};

export default Caja;