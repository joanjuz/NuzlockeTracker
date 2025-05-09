import React, { useState, useEffect } from 'react';
import './Components/Bitacora.css';
import { getRutasPorJuego } from './Services/API';

const juegosDisponibles = [
  'red', 'blue', 'yellow',
  'gold', 'silver', 'crystal',
  'ruby', 'sapphire', 'emerald',
  'firered', 'leafgreen',
  'diamond', 'pearl', 'platinum',
  'black', 'white',
  'black-2', 'white-2'
];

const BitacoraAventura = () => {
  const [medallas, setMedallas] = useState(Array(8).fill(false));
  const [altoMando, setAltoMando] = useState(Array(4).fill(false));
  const [cargado, setCargado] = useState(false);

  const [juegoSeleccionado, setJuegoSeleccionado] = useState('');
  const [rutasDisponibles, setRutasDisponibles] = useState([]);
  const [rutasCapturadas, setRutasCapturadas] = useState({});

  useEffect(() => {
    try {
      const m = JSON.parse(localStorage.getItem("medallas"));
      const e = JSON.parse(localStorage.getItem("altoMando"));
      const j = localStorage.getItem("juegoSeleccionado");
      const rc = JSON.parse(localStorage.getItem("rutasCapturadas"));

      if (Array.isArray(m) && m.length === 8) setMedallas(m);
      if (Array.isArray(e) && e.length === 4) setAltoMando(e);
      if (j) setJuegoSeleccionado(j);
      if (rc && typeof rc === 'object') setRutasCapturadas(rc);
    } catch (err) {
      console.warn("Bitácora: Error al cargar localStorage", err);
    } finally {
      setCargado(true);
    }
  }, []);

  useEffect(() => {
    if (!cargado) return;
    localStorage.setItem("medallas", JSON.stringify(medallas));
    localStorage.setItem("altoMando", JSON.stringify(altoMando));
    localStorage.setItem("juegoSeleccionado", juegoSeleccionado);
    localStorage.setItem("rutasCapturadas", JSON.stringify(rutasCapturadas));
  }, [medallas, altoMando, juegoSeleccionado, rutasCapturadas, cargado]);

  useEffect(() => {
    if (!juegoSeleccionado) return;
    getRutasPorJuego(juegoSeleccionado).then(setRutasDisponibles);
  }, [juegoSeleccionado]);

  const toggleMedalla = (index) => {
    const nuevo = [...medallas];
    nuevo[index] = !nuevo[index];
    setMedallas(nuevo);
  };

  const toggleAltoMando = (index) => {
    const nuevo = [...altoMando];
    nuevo[index] = !nuevo[index];
    setAltoMando(nuevo);
  };

  const toggleRuta = (ruta) => {
    setRutasCapturadas(prev => ({
      ...prev,
      [ruta]: !prev[ruta]
    }));
  };

  const categorizarRutas = (rutas) => {
    const categorias = {
      Capturadas: [],
      Routes: [],
      Cities: [],
      Forests: [],
      Caves: [],
      Towns: [],
      Lakes: [],
      Islands: [],
      Towers: [],
      Bridges: [],
      Facilities: [],
      Others: []
    };

    rutas.forEach(nombre => {
      const nombreFormateado = nombre
        .replace(/-/g, ' ')
        .replace(/\b\w/g, (l) => l.toUpperCase());

      if (rutasCapturadas[nombreFormateado]) {
        categorias.Capturadas.push(nombreFormateado);
      } else if (/\broute\b/i.test(nombre)) categorias.Routes.push(nombreFormateado);
      else if (/(city|metropolis)/i.test(nombre)) categorias.Cities.push(nombreFormateado);
      else if (/forest/i.test(nombre)) categorias.Forests.push(nombreFormateado);
      else if (/cave|cavern/i.test(nombre)) categorias.Caves.push(nombreFormateado);
      else if (/town/i.test(nombre)) categorias.Towns.push(nombreFormateado);
      else if (/lake|pond/i.test(nombre)) categorias.Lakes.push(nombreFormateado);
      else if (/island/i.test(nombre)) categorias.Islands.push(nombreFormateado);
      else if (/tower/i.test(nombre)) categorias.Towers.push(nombreFormateado);
      else if (/bridge/i.test(nombre)) categorias.Bridges.push(nombreFormateado);
      else if (/facility|power|plant|mansion|hideout|gym|hall/i.test(nombre)) categorias.Facilities.push(nombreFormateado);
      else categorias.Others.push(nombreFormateado);
    });

    return categorias;
  };

  if (!cargado) return null;

  return (
    <div className="bitacora-contenedor">
      <h2 className="titulo bold">Bitácora de Aventura</h2>

      <div className="bitacora-seccion">
        <h3 className="bitacora-subtitulo">🏅 Medallas obtenidas</h3>
        <div className="bitacora-grid">
          {medallas.map((m, i) => (
            <label key={i} className={`bitacora-card ${m ? 'activa' : ''}`}>
              <input type="checkbox" checked={m} onChange={() => toggleMedalla(i)} />
              Medalla {i + 1}
            </label>
          ))}
        </div>
      </div>

      <div className="bitacora-seccion">
        <h3 className="bitacora-subtitulo">👑 Alto Mando derrotado</h3>
        <div className="bitacora-grid">
          {altoMando.map((e, i) => (
            <label key={i} className={`bitacora-card alto ${e ? 'activa' : ''}`}>
              <input type="checkbox" checked={e} onChange={() => toggleAltoMando(i)} />
              Alto Mando {i + 1}
            </label>
          ))}
        </div>
      </div>

      <div className="bitacora-seccion">
        <h3 className="bitacora-subtitulo">🎮 Seleccionar Juego</h3>
        <select
          className="bitacora-select"
          value={juegoSeleccionado}
          onChange={(e) => setJuegoSeleccionado(e.target.value)}
        >
          <option value="">-- Selecciona un juego --</option>
          {juegosDisponibles.map(j => (
            <option key={j} value={j}>{j}</option>
          ))}
        </select>
      </div>

      {juegoSeleccionado && rutasDisponibles.length > 0 && (
        <div className="bitacora-seccion">
          <h3 className="bitacora-subtitulo">📍 Rutas de Captura</h3>
          {Object.entries(categorizarRutas(rutasDisponibles)).map(([grupo, nombres]) => (
            <div key={grupo} style={{ marginBottom: '20px' }}>
              <h4 style={{ color: '#2c3e50', borderBottom: '1px solid #ccc' }}>{grupo}</h4>
              <div className="bitacora-grid">
                {nombres.map((nombre) => (
                  <label key={nombre} className={`bitacora-card ruta ${rutasCapturadas[nombre] ? 'activa' : ''}`}>
                    <input
                      type="checkbox"
                      checked={!!rutasCapturadas[nombre]}
                      onChange={() => toggleRuta(nombre)}
                    />
                    {nombre}
                  </label>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default BitacoraAventura;
