// BitacoraAventura.js
import React from 'react';
import useBitacora from './useBitacora';
import MedallasPanel from './MedallasPanel';
import AltoMandoPanel from './AltoMandoPanel';
import SelectorJuego from './SelectorJuego';
import ListaRutasCaptura from './ListaRutasCaptura';
import './Bitacora.css';

const BitacoraAventura = () => {
  const {
    cargado,
    juegosDisponibles,
    medallas,
    toggleMedalla,
    altoMando,
    toggleAltoMando,
    juegoSeleccionado,
    setJuegoSeleccionado,
    rutasDisponibles,
    rutasCapturadas,
    toggleRuta,
    categorizarRutas,
  } = useBitacora();

  if (!cargado) return null;

  return (
    <div className="bitacora-contenedor">
      <h2 className="titulo bold">Bitácora de Aventura</h2>
      <MedallasPanel medallas={medallas} toggleMedalla={toggleMedalla} />
      <AltoMandoPanel altoMando={altoMando} toggleAltoMando={toggleAltoMando} />
      <SelectorJuego
        juegosDisponibles={juegosDisponibles}
        juegoSeleccionado={juegoSeleccionado}
        setJuegoSeleccionado={setJuegoSeleccionado}
      />
      <ListaRutasCaptura
        juegoSeleccionado={juegoSeleccionado}
        rutasDisponibles={rutasDisponibles}
        rutasCapturadas={rutasCapturadas}
        toggleRuta={toggleRuta}
        categorizarRutas={categorizarRutas}
      />
    </div>
  );
};

export default BitacoraAventura;