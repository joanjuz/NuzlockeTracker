import React from 'react';

const SeccionCoberturaOfensiva = ({ activos }) => {
  const tipoMovimientoSet = new Set();
  let movimientosFisicos = 0;
  let movimientosEspeciales = 0;
  let movimientosStatus = 0;

  activos.forEach(pokemon => {
    if (!Array.isArray(pokemon.moves) || pokemon.moves.length === 0) return;

    pokemon.moves.forEach(m => {
      tipoMovimientoSet.add(m.type);
      if (m.damageClass === 'physical') movimientosFisicos++;
      else if (m.damageClass === 'special') movimientosEspeciales++;
      else movimientosStatus++;
    });
  });

  const coberturaOfensiva = Array.from(tipoMovimientoSet);

  const renderTipos = (tipos) =>
    tipos.length ? (
      <div>
        {tipos.map((tipo, i) => (
          <span key={i} className={`tipo-cuadro ${tipo.toLowerCase()}`}>{tipo}</span>
        ))}
      </div>
    ) : (
      <p>No detectado.</p>
    );

  return (
    <div className="section">
      <h3 className="subtitulo">⚔ Cobertura ofensiva</h3>
      {renderTipos(coberturaOfensiva)}
      <p>
        🌀 Físicos: {movimientosFisicos} | 🔮 Especiales: {movimientosEspeciales} | 🧠 Estado: {movimientosStatus}
      </p>
    </div>
  );
};

export default SeccionCoberturaOfensiva;
