import React from 'react';
import './Components/valoracion.css';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';

const habilidadesInmunes = {
  levitate: ['ground'],
  "Water Absorb": ['water'],
  "Volt Absorb": ['electric'],
  "Flash Fire": ['fire'],
  "Sap Sipper": ['grass'],
  "Storm Drain": ['water'],
  "Lightning Rod": ['electric'],
  "Dry Skin": ['water'],
  "Motor Drive": ['electric'],
  "Thick Fat": ['fire', 'ice'],
  "Bulletproof": ['shadow ball', 'sludge bomb', 'energy ball']
};

const tiposClave = ['dragon', 'steel', 'fairy', 'ground', 'ghost'];

const Valoracion = ({ team }) => {
  const activos = team.filter(p => p.estado === "activo");
  if (activos.length === 0) return <p>No hay Pokémon activos para valorar.</p>;

  const tipoMovimientoSet = new Set();
  const tipoPokemonCount = {};
  const tipoDebilidadCount = {};
  const tipoResistencia = {};
  const tipoDefensivoMitigado = {};
  let movimientosFisicos = 0, movimientosEspeciales = 0, movimientosStatus = 0;
  let sinMovimientos = 0, sinStab = 0;

  const attackTypesList = [
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

  activos.forEach(p => {
    const inmunes = habilidadesInmunes[p.ability] || [];

    p.types.forEach(t => {
      tipoPokemonCount[t] = (tipoPokemonCount[t] || 0) + 1;
    });

    attackTypesList.forEach(tipo => {
      const mult = getEffectiveMultiplier(p, tipo);
      if (inmunes.includes(tipo)) {
        tipoDefensivoMitigado[tipo] = (tipoDefensivoMitigado[tipo] || 0) + 1;
      } else if (mult >= 2) {
        tipoDebilidadCount[tipo] = (tipoDebilidadCount[tipo] || 0) + 1;
      } else if (mult > 0 && mult < 1) {
        tipoResistencia[tipo] = (tipoResistencia[tipo] || 0) + 1;
      }
    });

    if (!Array.isArray(p.moves) || p.moves.length === 0) {
      sinMovimientos++;
      return;
    }

    const tiposDelPokemon = new Set(p.types);
    let tieneStab = false;

    p.moves.forEach(m => {
      tipoMovimientoSet.add(m.type);
      if (m.damageClass === 'physical') movimientosFisicos++;
      else if (m.damageClass === 'special') movimientosEspeciales++;
      else movimientosStatus++;

      if (tiposDelPokemon.has(m.type)) tieneStab = true;
    });

    if (!tieneStab) sinStab++;
  });

  const coberturaOfensiva = Array.from(tipoMovimientoSet);
  const tiposRepetidos = Object.entries(tipoPokemonCount).filter(([_, count]) => count > 1);
  const tiposConDebilidadMasiva = Object.entries(tipoDebilidadCount).filter(([_, count]) => count >= 2);

  const dataDebilidades = Object.entries(tipoDebilidadCount)
    .filter(([_, count]) => count > 0)
    .map(([tipo, count]) => ({ tipo, cantidad: count }));

  const renderTipos = (tipos) => (
    tipos.length ? (
      <div>
        {tipos.map((tipo, i) => (
          <span key={i} className={`tipo-cuadro ${tipo.toLowerCase()}`}>{tipo}</span>
        ))}
      </div>
    ) : <p>No detectado.</p>
  );

  return (
    <div className="valoracion">
      <h2 className="titulo bold">Valoración del Equipo Activo</h2>

      <div className="section">
        <h3 className="subtitulo">🛡 Mitigación por habilidades</h3>
        {Object.keys(tipoDefensivoMitigado).length > 0 ? (
          <ul>
            {Object.entries(tipoDefensivoMitigado).map(([tipo, count]) => (
              <li key={tipo}>→ {count} Pokémon ignoran <strong>{tipo}</strong> gracias a su habilidad</li>
            ))}
          </ul>
        ) : <p>Ninguna inmunidad defensiva activa.</p>}
      </div>

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

      <div className="section">
        <h3 className="subtitulo">⚔ Cobertura ofensiva</h3>
        {renderTipos(coberturaOfensiva)}
        <p>🌀 Físicos: {movimientosFisicos} | 🔮 Especiales: {movimientosEspeciales} | 🧠 Estado: {movimientosStatus}</p>
      </div>

      <div className="section">
        <h3 className="subtitulo">🔥 Tipos de Pokémon repetidos</h3>
        {tiposRepetidos.length > 0 ? (
          <ul>
            {tiposRepetidos.map(([tipo, count]) => (
              <li key={tipo}>{tipo}: {count} veces</li>
            ))}
          </ul>
        ) : <p>No hay tipos repetidos significativamente.</p>}
      </div>

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

      <div className="section">
        <p><strong>❌ Pokémon sin movimientos ofensivos:</strong> {sinMovimientos}</p>
        <p><strong>⚠️ Pokémon sin STAB ofensivo:</strong> {sinStab}</p>
      </div>

      <div className="section">
        <h3 className="subtitulo">🧠 Tipos clave sin cobertura ofensiva</h3>
        <ul>
          {tiposClave.filter(t => !tipoMovimientoSet.has(t)).map(tipoFaltante => (
            <li key={tipoFaltante}>No hay cobertura contra <strong>{tipoFaltante}</strong></li>
          ))}
        </ul>
      </div>
    </div>
  );
};

export default Valoracion;
