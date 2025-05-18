import React from 'react';

const tiposClave = ['dragon', 'steel', 'fairy', 'ground', 'ghost'];

const SeccionFinales = ({ activos }) => {
  let sinMovimientos = 0;
  let sinStab = 0;
  const tipoMovimientoSet = new Set();

  activos.forEach(pokemon => {
    if (!Array.isArray(pokemon.moves) || pokemon.moves.length === 0) {
      sinMovimientos++;
      return;
    }

    const tiposDelPokemon = new Set(pokemon.types);
    let tieneStab = false;

    pokemon.moves.forEach(m => {
      tipoMovimientoSet.add(m.type);
      if (tiposDelPokemon.has(m.type)) tieneStab = true;
    });

    if (!tieneStab) sinStab++;
  });

  const tiposClaveSinCobertura = tiposClave.filter(t => !tipoMovimientoSet.has(t));

  return (
    <div className="section">
      <p><strong>❌ Pokémon sin movimientos ofensivos:</strong> {sinMovimientos}</p>
      <p><strong>⚠️ Pokémon sin STAB ofensivo:</strong> {sinStab}</p>

      <h3 className="subtitulo">🧠 Tipos clave sin cobertura ofensiva</h3>
      {tiposClaveSinCobertura.length > 0 ? (
        <ul>
          {tiposClaveSinCobertura.map(tipo => (
            <li key={tipo}>No hay cobertura contra <strong>{tipo}</strong></li>
          ))}
        </ul>
      ) : (
        <p>Cobertura completa para tipos clave.</p>
      )}
    </div>
  );
};

export default SeccionFinales;
