import React from 'react';
import './Valoracion.css';
import './tipos.css';
import SeccionMitigacion from './SeccionMitigacion';
import SeccionResistencias from './SeccionResistencias';
import SeccionCoberturaOfensiva from './SeccionCoberturaOfensiva';
import SeccionTiposRepetidos from './SeccionTiposRepetidos';
import SeccionDebilidadesChart from './SeccionDebilidadesChart';
import SeccionFinales from './SeccionFinales';

const Valoracion = ({ team }) => {
  const activos = team.filter(p => p.estado === 'activo');
  if (activos.length === 0) return <p>No hay Pokémon activos para valorar.</p>;

  return (
    <div className="valoracion">
      <h2 className="titulo bold">Valoración del Equipo Activo</h2>
      <SeccionMitigacion activos={activos} />
      <SeccionResistencias activos={activos} />
      <SeccionCoberturaOfensiva activos={activos} />
      <SeccionTiposRepetidos activos={activos} />
      <SeccionDebilidadesChart activos={activos} />
      <SeccionFinales activos={activos} />
    </div>
  );
};

export default Valoracion;
