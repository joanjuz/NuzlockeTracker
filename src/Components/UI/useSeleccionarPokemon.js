// useSeleccionarPokemon.js
import { useState, useEffect } from 'react';
import {
  getPokemonNames,
  getPokemonSprite,
  getPokemonTypeByName,
  getPokemonWeaknesses
} from '../../Services/API';

const useSeleccionarPokemon = () => {
  const allPokemonTypes = {
    'normal': 0,
    'fire': 0,
    'water': 0,
    'electric': 0,
    'grass': 0,
    'ice': 0,
    'fighting': 0,
    'poison': 0,
    'ground': 0,
    'flying': 0,
    'psychic': 0,
    'bug': 0,
    'rock': 0,
    'ghost': 0,
    'dragon': 0,
    'dark': 0,
    'steel': 0,
    'fairy': 0
  };

  const [pokemonOptions, setPokemonOptions] = useState([]);
  const [selectedPokemon, setSelectedPokemon] = useState(null);
  const [sprite, setSprite] = useState(null);
  const [types, setTypes] = useState([]);
  const [weaknesses, setWeaknesses] = useState([]);
  const [error, setError] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [pokemonTypeCounts, setPokemonTypeCounts] = useState(allPokemonTypes);

  useEffect(() => {
    getPokemonNames()
      .then(names => {
        const sortedNames = names.sort();
        const options = sortedNames.map(name => ({ value: name, label: name }));
        setPokemonOptions(options);
      })
      .catch(e => {
        console.error("Error fetching Pokemon names:", e);
        setError("Error al obtener los nombres de Pokémon.");
      });
  }, []);

  useEffect(() => {
    if (!selectedPokemon) {
      setSprite(null);
      setTypes([]);
      setWeaknesses([]);
      return;
    }

    const fetchPokemonData = async () => {
      try {
        const name = selectedPokemon.value;
        const spriteData = await getPokemonSprite(name);
        const typesData = await getPokemonTypeByName(name);
        const weaknessesData = await getPokemonWeaknesses(name);

        setSprite(spriteData);
        setTypes(typesData);
        setWeaknesses(weaknessesData);
        setError(null);

        const updatedCounts = { ...allPokemonTypes };

        weaknessesData.forEach((weakness) => {
          const key = Object.keys(weakness)[0];
          const rel = weakness[key];

          rel.double_damage_from.forEach(t => updatedCounts[t] += 1);
          rel.half_damage_from.forEach(t => updatedCounts[t] -= 1);
          rel.no_damage_from.forEach(t => updatedCounts[t] -= 5);
        });

        setPokemonTypeCounts(updatedCounts);
      } catch (err) {
        console.error("Error fetching Pokémon data:", err);
        setError("Error al obtener los datos del Pokémon seleccionado.");
      }
    };

    fetchPokemonData();
  }, [selectedPokemon]);

  return {
    pokemonOptions,
    selectedPokemon,
    setSelectedPokemon,
    sprite,
    types,
    weaknesses,
    pokemonTypeCounts,
    setPokemonTypeCounts,
    error,
    showModal,
    setShowModal
  };
};

export default useSeleccionarPokemon;