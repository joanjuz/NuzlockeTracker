import React from 'react';

const habilidadesInmunes = {
  levitate: ['ground'],
  "water absorb": ['water'],
  "volt absorb": ['electric'],
  "flash fire": ['fire'],
  "sap sipper": ['grass'],
  "storm drain": ['water'],
  "lightning rod": ['electric'],
  "dry skin": ['water'],
  "motor drive": ['electric'],
};

const attackTypesList = [
  'normal', 'fire', 'water', 'electric', 'grass', 'ice',
  'fighting', 'poison', 'ground', 'flying', 'psychic',
  'bug', 'rock', 'ghost', 'dragon', 'dark', 'steel', 'fairy'
];

const Valoracion = ({ team }) => {
  const activos = team.filter(p => p.estado === "activo");

  if (activos.length === 0) {
    return <p>No hay Pokémon activos para valorar.</p>;
  }

  const tipoMovimientoSet = new Set();
  const tipoPokemonCount = {};
  const tipoDebilidadCount = {};
  const tipoDefensivoMitigado = {};

  let movimientosFisicos = 0;
  let movimientosEspeciales = 0;
  let movimientosStatus = 0;

  activos.forEach(p => {
    // Conteo de tipos del equipo
    p.types.forEach(t => {
      tipoPokemonCount[t] = (tipoPokemonCount[t] || 0) + 1;
    });

    // Inmunidades por habilidad
    const inmunidades = habilidadesInmunes[p.ability?.toLowerCase()] || [];

    // Cálculo real de multiplicadores combinados
    const debilidadPorTipo = {};

    p.weaknesses.forEach((entry) => {
      const tipo = Object.keys(entry)[0];
      const relations = entry[tipo];

      attackTypesList.forEach((t) => {
        let mult = 1;

        if (relations.no_damage_from.includes(t)) mult = 0;
        else if (relations.double_damage_from.includes(t)) mult = 2;
        else if (relations.half_damage_from.includes(t)) mult = 0.5;

        debilidadPorTipo[t] = (debilidadPorTipo[t] || 1) * mult;
      });
    });

    // Registrar debilidades reales
    Object.entries(debilidadPorTipo).forEach(([tipo, mult]) => {
      if (inmunidades.includes(tipo)) {
        tipoDefensivoMitigado[tipo] = (tipoDefensivoMitigado[tipo] || 0) + 1;
      } else if (mult >= 2) {
        tipoDebilidadCount[tipo] = (tipoDebilidadCount[tipo] || 0) + 1;
      }
    });

    // Registro de movimientos
    if (Array.isArray(p.moves)) {
      p.moves.forEach(m => {
        tipoMovimientoSet.add(m.type);
        if (m.damageClass === 'physical') movimientosFisicos++;
        if (m.damageClass === 'special') movimientosEspeciales++;
        if (m.damageClass === 'status') movimientosStatus++;
      });
    }
  });

  const coberturaOfensiva = Array.from(tipoMovimientoSet);
  const tiposRepetidos = Object.entries(tipoPokemonCount).filter(([_, count]) => count > 1);
  const tiposConDebilidadMasiva = Object.entries(tipoDebilidadCount).filter(([_, count]) => count >= 2);

  return (
    <div style={{ marginTop: '20px' }}>
      <h2 className="titulo bold">Valoración del Equipo Activo</h2>

      <p><strong>🛡 Mitigación de habilidades defensivas:</strong></p>
      {Object.keys(tipoDefensivoMitigado).length > 0 ? (
        <ul>
          {Object.entries(tipoDefensivoMitigado).map(([tipo, count]) => (
            <li key={tipo}>→ {count} Pokémon ignoran <strong>{tipo}</strong> gracias a su habilidad</li>
          ))}
        </ul>
      ) : (
        <p>Ninguna habilidad defensiva mitiga debilidades actuales.</p>
      )}

      <p><strong>⚔ Cobertura ofensiva:</strong> {coberturaOfensiva.join(', ') || 'Sin cobertura detectada'}</p>
      <p><strong>🌀 Movimientos físicos:</strong> {movimientosFisicos}</p>
      <p><strong>🔮 Movimientos especiales:</strong> {movimientosEspeciales}</p>
      <p><strong>🧠 Movimientos de estado:</strong> {movimientosStatus}</p>

      <p><strong>🔥 Tipos de Pokémon repetidos:</strong></p>
      {tiposRepetidos.length > 0 ? (
        <ul>
          {tiposRepetidos.map(([tipo, count]) => (
            <li key={tipo}>{tipo}: {count} veces</li>
          ))}
        </ul>
      ) : (
        <p>No hay tipos repetidos significativamente.</p>
      )}

      <p><strong>⚠️ Debilidades acumuladas (x2 o más):</strong></p>
      {tiposConDebilidadMasiva.length > 0 ? (
        <ul>
          {tiposConDebilidadMasiva.map(([tipo, count]) => (
            <li key={tipo}>{count} Pokémon con debilidad x2 a <strong>{tipo}</strong></li>
          ))}
        </ul>
      ) : (
        <p>No hay debilidades repetidas peligrosas (x2 o más).</p>
      )}
    </div>
  );
};

export default Valoracion;
