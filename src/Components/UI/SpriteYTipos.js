// SpriteYTipos.js
import React from 'react';
import './Pokemon.css'
import './tipos.css'
const SpriteYTipos = ({ sprite, types }) => {
  if (!sprite || types.length === 0) return null;

  return (
    <div style={{ textAlign: 'center' }}>
      <img src={sprite} alt="Sprite" style={{ width: '96px', marginBottom: '8px' }} />
      <div className="boxTipo">
        {types.map((type) => (
          <span key={type} className={`tipo ${type.toLowerCase()}`}>{type}</span>
        ))}
      </div>
    </div>
  );
};

export default SpriteYTipos;
