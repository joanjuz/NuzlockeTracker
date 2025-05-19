import React from 'react';

const tipos = [
  'normal', 'fire', 'water', 'electric', 'grass', 'ice',
  'fighting', 'poison', 'ground', 'flying', 'psychic',
  'bug', 'rock', 'ghost', 'dragon', 'dark', 'steel', 'fairy'
];

const getEffectiveMultiplier = (pokemon, attackType) => {
  if (!pokemon.weaknesses || pokemon.weaknesses.length === 0) return 1;
  let multiplier = 1;
  pokemon.weaknesses.forEach((typeObj) => {
    const type = Object.keys(typeObj)[0];
    const relations = typeObj[type];

    if (relations.no_damage_from.includes(attackType)) {
      multiplier *= 0;
    } else if (relations.double_damage_from.includes(attackType)) {
      multiplier *= 2;
    } else if (relations.half_damage_from.includes(attackType)) {
      multiplier *= 0.5;
    }
  });
  return multiplier;
};

const SeccionResistencias = ({ activos }) => {
  const tipoResistencia = {};

  activos.forEach(pokemon => {
    tipos.forEach(tipo => {
      const mult = getEffectiveMultiplier(pokemon, tipo);
      if (mult > 0 && mult < 1) {
        tipoResistencia[tipo] = (tipoResistencia[tipo] || 0) + 1;
      }
    });
  });

  return (
    <div className="section">
      <h3 className="subtitulo">🛡 Resistencias comunes</h3>
      <div className="tipo-resistencias-grid">
        {Object.entries(tipoResistencia)
          .sort((a, b) => b[1] - a[1])
          .map(([tipo, count]) => (
            <div key={tipo} className={`tipo-cuadro ${tipo}`}>
              <div className="contador">{count}</div>
              <div>{tipo}</div>
            </div>
          ))}
      </div>
    </div>
  );
};

export default SeccionResistencias;
