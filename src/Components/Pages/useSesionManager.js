// useSesionManager.js
import { useState, useEffect } from 'react';

const useSesionManager = () => {
  const [activeTab, setActiveTab] = useState(() => {
    return localStorage.getItem('activeTab') || 'agregar';
  });
  const [miEquipo, setMiEquipo] = useState([]);
  const [rivalTeam, setRivalTeam] = useState([]);
  const [cargaInicialCompleta, setCargaInicialCompleta] = useState(false);

  useEffect(() => {
    localStorage.setItem('activeTab', activeTab);
  }, [activeTab]);

  useEffect(() => {
    const equipoGuardado = JSON.parse(localStorage.getItem('miEquipo')) || [];
    const rivalGuardado = JSON.parse(localStorage.getItem('rivalTeam')) || [];
    setMiEquipo(equipoGuardado);
    setRivalTeam(rivalGuardado);
    setCargaInicialCompleta(true);
  }, []);

  useEffect(() => {
    if (!cargaInicialCompleta) return;
    localStorage.setItem('miEquipo', JSON.stringify(miEquipo));
    localStorage.setItem('rivalTeam', JSON.stringify(rivalTeam));
    console.log('✅ Guardado actualizado');
  }, [miEquipo, rivalTeam, cargaInicialCompleta]);

  const agregarPokemonAlTeam = (pokemon, teamType) => {
    const pokemonConEstado = { ...pokemon, estado: 'activo' };
    if (teamType === 'miEquipo') {
      setMiEquipo(prev => [...prev, pokemonConEstado]);
    } else if (teamType === 'rivalTeam') {
      setRivalTeam(prev => [...prev, pokemonConEstado]);
    }
  };

  const eliminarPokemonDelTeam = (index, teamType) => {
    if (teamType === 'miEquipo') {
      setMiEquipo(prev => prev.filter((_, idx) => idx !== index));
    } else if (teamType === 'rivalTeam') {
      setRivalTeam(prev => prev.filter((_, idx) => idx !== index));
    }
  };

  const addMoveToPokemon = (pokemonActualizado) => {
    setMiEquipo(prev =>
      prev.map(p =>
        p.name === pokemonActualizado.name && p.nickname === pokemonActualizado.nickname
          ? { ...pokemonActualizado }
          : p
      )
    );

    setRivalTeam(prev =>
      prev.map(p =>
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

    if (teamType === 'miEquipo') {
      setMiEquipo(prev => actualizarEquipo(prev));
    } else if (teamType === 'rivalTeam') {
      setRivalTeam(prev => actualizarEquipo(prev));
    }
  };

  const handleImportPokemons = (importedPokemons) => {
    const importadosConEstado = importedPokemons.map(p => ({ ...p, estado: 'activo' }));
    setMiEquipo(prev => [...prev, ...importadosConEstado]);
    setActiveTab('equipo');
  };

  const borrarSavefile = () => {
    localStorage.removeItem('miEquipo');
    localStorage.removeItem('rivalTeam');
    localStorage.removeItem('medallas');
    localStorage.removeItem('altoMando');
    localStorage.removeItem('activeTab');
    setMiEquipo([]);
    setRivalTeam([]);
    setActiveTab('agregar');
    alert('Progreso borrado.');
  };

  const exportarSesion = () => {
    const equipo = JSON.parse(localStorage.getItem('miEquipo')) || [];
    const rutasCapturadas = JSON.parse(localStorage.getItem('rutasCapturadas')) || {};
    const medallas = JSON.parse(localStorage.getItem('medallas')) || Array(8).fill(false);
    const altoMando = JSON.parse(localStorage.getItem('altoMando')) || Array(4).fill(false);
    const juegoSeleccionado = localStorage.getItem('juegoSeleccionado') || '';

    const sesion = {
      juegoSeleccionado,
      medallas,
      altoMando,
      rutasCapturadas,
      equipo,
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
          localStorage.setItem('miEquipo', JSON.stringify(sesionImportada.equipo));
          localStorage.setItem('rutasCapturadas', JSON.stringify(sesionImportada.rutasCapturadas || {}));
          localStorage.setItem('medallas', JSON.stringify(sesionImportada.medallas || Array(8).fill(false)));
          localStorage.setItem('altoMando', JSON.stringify(sesionImportada.altoMando || Array(4).fill(false)));
          localStorage.setItem('juegoSeleccionado', sesionImportada.juegoSeleccionado || '');

          setMiEquipo(sesionImportada.equipo || []);
          setActiveTab('equipo');
          alert('Sesión importada correctamente.');
        } else {
          alert('El archivo no es válido.');
        }
      } catch (err) {
        console.error('❌ Error al leer archivo:', err);
        alert('Error al leer el archivo JSON.');
      }
    };
    reader.readAsText(file);
  };

  return {
    activeTab,
    setActiveTab,
    miEquipo,
    rivalTeam,
    agregarPokemonAlTeam,
    eliminarPokemonDelTeam,
    addMoveToPokemon,
    cambiarEstadoPokemon,
    handleImportPokemons,
    borrarSavefile,
    exportarSesion,
    importarSesionDesdeArchivo,
  };
};

export default useSesionManager;
