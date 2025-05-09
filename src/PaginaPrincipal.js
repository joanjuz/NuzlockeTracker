import React, { useState, useEffect } from 'react';
import Header from './Header';
import SeleccionarPokemon from './SeleccionarPokemon';
import TeamTracker from './TeamTracker';
import Valoracion from './valoracion.js';
import BitacoraAventura from './BitacoraAventura';
import './Components/Apps.css';
import ImportarGenerar from './ImportarGenerar.js';

const PaginaPrincipal = () => {
  const [activeTab, setActiveTab] = useState(() => {
    return localStorage.getItem("activeTab") || "agregar";
  });
  const [miEquipo, setMiEquipo] = useState([]);
  const [rivalTeam, setRivalTeam] = useState([]);
  const [cargaInicialCompleta, setCargaInicialCompleta] = useState(false);

  // Guardar pestaña activa
  useEffect(() => {
    localStorage.setItem("activeTab", activeTab);
  }, [activeTab]);

  // Cargar datos del localStorage al iniciar
  useEffect(() => {
    const equipoGuardado = JSON.parse(localStorage.getItem("miEquipo")) || [];
    const rivalGuardado = JSON.parse(localStorage.getItem("rivalTeam")) || [];
    setMiEquipo(equipoGuardado);
    setRivalTeam(rivalGuardado);
    setCargaInicialCompleta(true);
  }, []);

  // Guardar automáticamente cuando se actualiza
  useEffect(() => {
    if (!cargaInicialCompleta) return;
    localStorage.setItem("miEquipo", JSON.stringify(miEquipo));
    localStorage.setItem("rivalTeam", JSON.stringify(rivalTeam));
    console.log("✅ Guardado actualizado");
  }, [miEquipo, rivalTeam, cargaInicialCompleta]);

  const agregarPokemonAlTeam = (pokemon, teamType) => {
    const pokemonConEstado = { ...pokemon, estado: "activo" };
    if (teamType === "miEquipo") {
      setMiEquipo((prevTeam) => [...prevTeam, pokemonConEstado]);
    } else if (teamType === "rivalTeam") {
      setRivalTeam((prevTeam) => [...prevTeam, pokemonConEstado]);
    }
  };

  const eliminarPokemonDelTeam = (index, teamType) => {
    if (teamType === "miEquipo") {
      setMiEquipo((prevTeam) => prevTeam.filter((_, idx) => idx !== index));
    } else if (teamType === "rivalTeam") {
      setRivalTeam((prevTeam) => prevTeam.filter((_, idx) => idx !== index));
    }
  };

  const addMoveToPokemon = (pokemonActualizado, move) => {
    setMiEquipo((prev) =>
      prev.map((p) =>
        p.name === pokemonActualizado.name && p.nickname === pokemonActualizado.nickname
          ? { ...pokemonActualizado }
          : p
      )
    );

    setRivalTeam((prev) =>
      prev.map((p) =>
        p.name === pokemonActualizado.name && p.nickname === pokemonActualizado.nickname
          ? { ...pokemonActualizado }
          : p
      )
    );
  };

  const cambiarEstadoPokemon = (index, teamType, nuevoEstado) => {
    const actualizarEquipo = (equipo) => {
      const nuevo = [...equipo];
      nuevo[index] = { ...nuevo[index], estado: nuevoEstado };
      return nuevo;
    };

    if (teamType === "miEquipo") {
      setMiEquipo((prev) => actualizarEquipo(prev));
    } else if (teamType === "rivalTeam") {
      setRivalTeam((prev) => actualizarEquipo(prev));
    }
  };

  const handleImportPokemons = (importedPokemons) => {
    const importadosConEstado = importedPokemons.map(p => ({ ...p, estado: "activo" }));
    setMiEquipo((prevTeam) => [...prevTeam, ...importadosConEstado]);
    setActiveTab("equipo");
  };

  const borrarSavefile = () => {
    localStorage.removeItem("miEquipo");
    localStorage.removeItem("rivalTeam");
    localStorage.removeItem("medallas");
    localStorage.removeItem("altoMando");
    localStorage.removeItem("activeTab");
    setMiEquipo([]);
    setRivalTeam([]);
    setActiveTab("agregar");
    alert("Progreso borrado.");
  };
  const exportarSesion = () => {
    const equipo = JSON.parse(localStorage.getItem("miEquipo")) || [];
    const rutasCapturadas = JSON.parse(localStorage.getItem("rutasCapturadas")) || {};
    const medallas = JSON.parse(localStorage.getItem("medallas")) || Array(8).fill(false);
    const altoMando = JSON.parse(localStorage.getItem("altoMando")) || Array(4).fill(false);
    const juegoSeleccionado = localStorage.getItem("juegoSeleccionado") || "";

    const sesion = {
      juegoSeleccionado,
      medallas,
      altoMando,
      rutasCapturadas,
      equipo
    };

    const blob = new Blob([JSON.stringify(sesion, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'sesion_pokemon.json';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const importarSesionDesdeArchivo = (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
      try {
        const sesionImportada = JSON.parse(event.target.result);

        if (
          sesionImportada &&
          typeof sesionImportada === 'object' &&
          Array.isArray(sesionImportada.equipo)
        ) {
          // Restaurar datos
          localStorage.setItem("miEquipo", JSON.stringify(sesionImportada.equipo));
          localStorage.setItem("rutasCapturadas", JSON.stringify(sesionImportada.rutasCapturadas || {}));
          localStorage.setItem("medallas", JSON.stringify(sesionImportada.medallas || Array(8).fill(false)));
          localStorage.setItem("altoMando", JSON.stringify(sesionImportada.altoMando || Array(4).fill(false)));
          localStorage.setItem("juegoSeleccionado", sesionImportada.juegoSeleccionado || "");

          // Actualizar estados si están disponibles
          setMiEquipo(sesionImportada.equipo || []);
          setActiveTab("equipo");

          alert("Sesión importada correctamente.");
        } else {
          alert("El archivo no es válido.");
        }
      } catch (err) {
        console.error("❌ Error al leer archivo:", err);
        alert("Error al leer el archivo JSON.");
      }
    };
    reader.readAsText(file);
  };



  return (
    <div style={{ padding: '20px' }}>
      <h1 className="titulo-nuztracker">NuzTracker</h1>

      <Header activeTab={activeTab} setActiveTab={setActiveTab} />

      {activeTab === "agregar" && (
        <div style={{ display: 'flex', fontSize: '1.2em', padding: '10px', gap: '10px' }}>
          <div style={{ flex: 1 }}>
            <h2 className="titulo bold" style={{ fontSize: '1.4em', margin: '5px 0' }}>
              Agregar a Mi Equipo
            </h2>

            <div className="botonera-sesion-minimal">
              <button className="btn-min" onClick={borrarSavefile}>
                Borrar
              </button>

              <button className="btn-min" onClick={exportarSesion}>
                Exportar
              </button>

              <label className="btn-min importar">
                Importar
                <input
                  type="file"
                  accept="application/json"
                  onChange={importarSesionDesdeArchivo}
                  style={{ display: 'none' }}
                />
              </label>
            </div>



            <div className="centrado">
              <SeleccionarPokemon onAddPokemon={(pokemon) => agregarPokemonAlTeam(pokemon, "miEquipo")} />
            </div>
          </div>
        </div>
      )}

      {activeTab === "bitacora" && (
        <div style={{ marginTop: '20px' }}>
          <BitacoraAventura />
        </div>
      )}

      {activeTab === "equipo" && (
        <div style={{ display: 'flex' }}>
          <div style={{ marginTop: '20px', flex: 1, marginRight: '30px' }}>
            <TeamTracker
              team={miEquipo}
              onRemovePokemon={(index) => eliminarPokemonDelTeam(index, "miEquipo")}
              onAddMove={addMoveToPokemon}
              onChangeEstado={(index, teamType, nuevoEstado) => cambiarEstadoPokemon(index, teamType, nuevoEstado)}
            />
          </div>

        </div>
      )}

      {activeTab === "valoracion" && (
        <div style={{ marginTop: '20px' }}>
          <Valoracion team={miEquipo} />
        </div>
      )}

      {activeTab === "archivo" && (
        <ImportarGenerar
          team={miEquipo}
          onImportPokemons={handleImportPokemons}
        />
      )}

    </div>
  );
};

export default PaginaPrincipal;
