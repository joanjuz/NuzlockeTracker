// SpriteYTipos.js
import React from 'react';
import './Pokemon.css'
import './tipos.css'
const SpriteYTipos = ({ sprite, types }) => {
  if (!sprite || types.length === 0) return null;

  return (
    <div style={{ textAlign: 'center' }}>
      <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '12px' }}>
        <img src={sprite} alt="Sprite" style={{ width: '150px' }} />
      </div>
      <div className="boxTipo">
        {types.map((type) => (
          <span key={type} className={`tipo ${type.toLowerCase()}`}>{type}</span>
        ))}
      </div>
    </div>
  );
};

export default SpriteYTipos;
