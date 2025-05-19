import React from 'react';

const SeccionTiposRepetidos = ({ activos }) => {
  const tipoPokemonCount = {};

  activos.forEach(pokemon => {
    pokemon.types.forEach(t => {
      tipoPokemonCount[t] = (tipoPokemonCount[t] || 0) + 1;
    });
  });

  const tiposRepetidos = Object.entries(tipoPokemonCount).filter(([_, count]) => count > 1);

  return (
    <div className="section">
      <h3 className="subtitulo">🔥 Tipos de Pokémon repetidos</h3>
      {tiposRepetidos.length > 0 ? (
        <ul>
          {tiposRepetidos.map(([tipo, count]) => (
            <li key={tipo}>{tipo}: {count} veces</li>
          ))}
        </ul>
      ) : (
        <p>No hay tipos repetidos significativamente.</p>
      )}
    </div>
  );
};

export default SeccionTiposRepetidos;
