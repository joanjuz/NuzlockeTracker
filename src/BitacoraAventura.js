// BitacoraAventura.js
import React, { useState, useEffect } from 'react';
import './Components/Bitacora.css';

const BitacoraAventura = () => {
  const [medallas, setMedallas] = useState(Array(8).fill(false));
  const [altoMando, setAltoMando] = useState(Array(4).fill(false));
  const [cargado, setCargado] = useState(false); // ← nuevo estado de carga

  // Cargar desde localStorage al iniciar
  useEffect(() => {
    try {
      const m = JSON.parse(localStorage.getItem("medallas"));
      const e = JSON.parse(localStorage.getItem("altoMando"));
      if (Array.isArray(m) && m.length === 8) setMedallas(m);
      if (Array.isArray(e) && e.length === 4) setAltoMando(e);
    } catch (err) {
      console.warn("Bitácora: Error al cargar desde localStorage", err);
    } finally {
      setCargado(true); // ← marca como listo para mostrar
    }
  }, []);

  // Guardar en localStorage cuando hay cambios
  useEffect(() => {
    if (!cargado) return; // evita guardar antes de cargar
    localStorage.setItem("medallas", JSON.stringify(medallas));
    localStorage.setItem("altoMando", JSON.stringify(altoMando));
  }, [medallas, altoMando, cargado]);

  const toggleMedalla = (index) => {
    const nuevoEstado = [...medallas];
    nuevoEstado[index] = !nuevoEstado[index];
    setMedallas(nuevoEstado);
  };

  const toggleAltoMando = (index) => {
    const nuevoEstado = [...altoMando];
    nuevoEstado[index] = !nuevoEstado[index];
    setAltoMando(nuevoEstado);
  };

  if (!cargado) return null; // No renderiza nada hasta estar listo

  return (
    <div>
      <h2 className="titulo bold">Bitácora de Aventura</h2>

      <h3>Medallas obtenidas</h3>
      <div className="bitacora-grid">
        {medallas.map((m, i) => (
          <label key={i} className="bitacora-checkbox">
            <input
              type="checkbox"
              checked={m}
              onChange={() => toggleMedalla(i)}
            />
            Medalla {i + 1}
          </label>
        ))}
      </div>

      <h3>Miembros del Alto Mando derrotados</h3>
      <div className="bitacora-grid">
        {altoMando.map((e, i) => (
          <label key={i} className="bitacora-checkbox">
            <input
              type="checkbox"
              checked={e}
              onChange={() => toggleAltoMando(i)}
            />
            Alto Mando {i + 1}
          </label>
        ))}
      </div>
    </div>
  );
};

export default BitacoraAventura;
