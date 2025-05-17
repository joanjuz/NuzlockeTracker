// DebilidadesResumen.js
import React from 'react';

const DebilidadesResumen = ({ pokemonTypeCounts }) => {
  const tipos = Object.keys(pokemonTypeCounts || {});

  const renderCategorias = () => {
    const debilidad4x = tipos.filter(t => pokemonTypeCounts[t] === 2);
    const debilidad2x = tipos.filter(t => pokemonTypeCounts[t] === 1);
    const resistenciaMedia = tipos.filter(t => pokemonTypeCounts[t] === -1);
    const resistenciaCuarta = tipos.filter(t => pokemonTypeCounts[t] === -2);
    const inmune = tipos.filter(t => pokemonTypeCounts[t] <= -5);

    return (
      <div>
        {debilidad4x.length > 0 && (
          <div>
            <p>Debilidad 4x</p>
            <div className="boxWeak">
              {debilidad4x.map(t => (
                <span key={t} className={`tipo ${t}`}>4x {t}</span>
              ))}
            </div>
          </div>
        )}
        {debilidad2x.length > 0 && (
          <div>
            <p>Debilidad 2x</p>
            <div className="boxWeak">
              {debilidad2x.map(t => (
                <span key={t} className={`tipo ${t}`}>2x {t}</span>
              ))}
            </div>
          </div>
        )}
        {resistenciaMedia.length > 0 && (
          <div>
            <p>Resistencia 1/2</p>
            <div className="boxWeak">
              {resistenciaMedia.map(t => (
                <span key={t} className={`tipo ${t}`}>½ {t}</span>
              ))}
            </div>
          </div>
        )}
        {resistenciaCuarta.length > 0 && (
          <div>
            <p>Resistencia 1/4</p>
            <div className="boxWeak">
              {resistenciaCuarta.map(t => (
                <span key={t} className={`tipo ${t}`}>¼ {t}</span>
              ))}
            </div>
          </div>
        )}
        {inmune.length > 0 && (
          <div>
            <p>Inmune</p>
            <div className="boxWeak">
              {inmune.map(t => (
                <span key={t} className={`tipo none`}>{t}</span>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  };

  return (
    <div style={{ textAlign: 'center', marginTop: '16px' }}>
      <h4>Debilidades</h4>
      {renderCategorias()}
    </div>
  );
};

export default DebilidadesResumen;
