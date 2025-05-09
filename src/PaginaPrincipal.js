import React, { useState, useEffect } from 'react';
import Header from './Header';
import SeleccionarPokemon from './SeleccionarPokemon';
import TeamTracker from './TeamTracker';
import Valoracion from './valoracion.js';
import GenerarTxt from './GenerarTxt.js';
import BitacoraAventura from './BitacoraAventura';
import ImportarTxt from './ImportarTxt.js';

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
  const exportarEquipo = () => {
    const equipo = JSON.parse(localStorage.getItem("miEquipo")) || [];
    const blob = new Blob([JSON.stringify(equipo, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'mi_equipo_pokemon.json';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const importarEquipoDesdeArchivo = (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
      try {
        const equipoImportado = JSON.parse(event.target.result);
        if (Array.isArray(equipoImportado)) {
          localStorage.setItem("miEquipo", JSON.stringify(equipoImportado));
          setMiEquipo(equipoImportado);
          alert("Equipo importado correctamente.");
          setActiveTab("equipo");
        } else {
          alert("El archivo no es válido.");
        }
      } catch (err) {
        alert("Error al leer el archivo JSON.");
      }
    };
    reader.readAsText(file);
  };


  return (
    <div style={{ padding: '20px' }}>
      <h1 className="titulo bold">Tracker Pokémon</h1>
      <Header activeTab={activeTab} setActiveTab={setActiveTab} />

      <div style={{ marginTop: '10px' }}>
        <button className="btn danger" onClick={borrarSavefile}>
          Borrar Savefile
        </button>

        <button className="btn" onClick={exportarEquipo} style={{ marginLeft: '10px' }}>
          Descargar Equipo
        </button>

        <label className="btn" style={{
          marginLeft: '10px',
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          height: '28px',
          padding: '0 12px',
          fontSize: '14px',
          cursor: 'pointer'
        }}>
          Importar Equipo 
          <input
            type="file"
            accept="application/json"
            onChange={importarEquipoDesdeArchivo}
            style={{
              display: 'none'
            }}
          />
        </label>

      </div>



      {activeTab === "agregar" && (
        <div style={{ display: 'flex', fontSize: '1.2em', padding: '10px', gap: '10px' }}>
          <div style={{ flex: 1 }}>
            <h2 className="titulo bold" style={{ fontSize: '1.4em', margin: '5px 0' }}>
              Agregar a Mi Equipo
            </h2>
            <SeleccionarPokemon onAddPokemon={(pokemon) => agregarPokemonAlTeam(pokemon, "miEquipo")} />
          </div>
          <div style={{ flex: 1 }}>
            <h2 className="titulo bold" style={{ fontSize: '1.4em', margin: '5px 0' }}>
              Agregar al Equipo Rival
            </h2>
            <SeleccionarPokemon onAddPokemon={(pokemon) => agregarPokemonAlTeam(pokemon, "rivalTeam")} />
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
            <h2 className="titulo bold">Mi Equipo:</h2>
            <TeamTracker
              team={miEquipo}
              onRemovePokemon={(index) => eliminarPokemonDelTeam(index, "miEquipo")}
              onAddMove={addMoveToPokemon}
              onChangeEstado={(index, teamType, nuevoEstado) => cambiarEstadoPokemon(index, teamType, nuevoEstado)}
            />
          </div>
          <div style={{ marginTop: '20px', flex: 1, marginRight: '20px' }}>
            <h2 className="titulo bold">Equipo Rival:</h2>
            <TeamTracker
              team={rivalTeam}
              onRemovePokemon={(index) => eliminarPokemonDelTeam(index, "rivalTeam")}
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

      {activeTab === "generacion" && (
        <div style={{ marginTop: '20px' }}>
          <GenerarTxt team={miEquipo} />
        </div>
      )}

      {activeTab === "importar" && (
        <div style={{ marginTop: '20px' }}>
          <ImportarTxt onImportPokemons={handleImportPokemons} />
        </div>
      )}
    </div>
  );
};

export default PaginaPrincipal;
