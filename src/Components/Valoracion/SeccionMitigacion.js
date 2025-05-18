import React from 'react';

const habilidadesInmunes = {
  levitate: ['ground'],
  'Water Absorb': ['water'],
  'Volt Absorb': ['electric'],
  'Flash Fire': ['fire'],
  'Sap Sipper': ['grass'],
  'Storm Drain': ['water'],
  'Lightning Rod': ['electric'],
  'Dry Skin': ['water'],
  'Motor Drive': ['electric'],
  'Thick Fat': ['fire', 'ice'],
  'Bulletproof': ['shadow ball', 'sludge bomb', 'energy ball'],
};

const SeccionMitigacion = ({ activos }) => {
  const tipoDefensivoMitigado = {};

  activos.forEach(pokemon => {
    const inmunes = habilidadesInmunes[pokemon.ability] || [];
    inmunes.forEach(tipo => {
      tipoDefensivoMitigado[tipo] = (tipoDefensivoMitigado[tipo] || 0) + 1;
    });
  });

  return (
    <div className="section">
      <h3 className="subtitulo">🛡 Mitigación por habilidades</h3>
      {Object.keys(tipoDefensivoMitigado).length > 0 ? (
        <ul>
          {Object.entries(tipoDefensivoMitigado).map(([tipo, count]) => (
            <li key={tipo}>→ {count} Pokémon ignoran <strong>{tipo}</strong> gracias a su habilidad</li>
          ))}
        </ul>
      ) : (
        <p>Ninguna inmunidad defensiva activa.</p>
      )}
    </div>
  );
};

export default SeccionMitigacion;
