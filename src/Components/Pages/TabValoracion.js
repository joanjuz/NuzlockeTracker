// TabValoracion.js
import React from 'react';
import Valoracion from '../Valoracion/Valoracion';

const TabValoracion = ({ miEquipo }) => {
  return (
    <div style={{ marginTop: '20px' }}>
      <Valoracion team={miEquipo} />
    </div>
  );
};

export default TabValoracion;