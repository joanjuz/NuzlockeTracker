import React from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';

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

const SeccionDebilidadesChart = ({ activos }) => {
  const tipoDebilidadCount = {};

  activos.forEach(pokemon => {
    tipos.forEach(tipo => {
      const mult = getEffectiveMultiplier(pokemon, tipo);
      if (mult >= 2) {
        tipoDebilidadCount[tipo] = (tipoDebilidadCount[tipo] || 0) + 1;
      }
    });
  });

  const dataDebilidades = Object.entries(tipoDebilidadCount)
    .filter(([_, count]) => count > 0)
    .map(([tipo, count]) => ({ tipo, cantidad: count }));

  return (
    <div className="section">
      <h3 className="subtitulo">📊 Debilidades acumuladas por tipo</h3>
      {dataDebilidades.length > 0 ? (
        <ResponsiveContainer width="100%" height={400}>
          <BarChart layout="vertical" data={dataDebilidades} margin={{ top: 10, right: 30, left: 30, bottom: 10 }}>
            <XAxis
              type="number"
              domain={[0, 'dataMax']}
              tickFormatter={(value) => Number.isInteger(value) ? value : ''}
              allowDecimals={false}
            />
            <YAxis type="category" dataKey="tipo" />
            <Tooltip />
            <Bar dataKey="cantidad" fill="#e74c3c">
              {dataDebilidades.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={`var(--${entry.tipo}-color, #e74c3c)`} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      ) : (
        <p>No hay debilidades acumuladas para graficar.</p>
      )}
    </div>
  );
};

export default SeccionDebilidadesChart;
