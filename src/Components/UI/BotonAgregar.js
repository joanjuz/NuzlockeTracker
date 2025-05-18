// BotonAgregar.js
import React from 'react';

const BotonAgregar = ({ disabled, onClick }) => (
  <div style={{ textAlign: 'left', marginTop: '20px', marginLeft: '40px' }}>
    <button
      className="btn"
      disabled={disabled}
      onClick={onClick}
    >
      Agregar
    </button>
  </div>
);

export default BotonAgregar;
