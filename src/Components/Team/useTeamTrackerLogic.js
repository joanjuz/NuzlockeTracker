// useTeamTrackerLogic.js
import { useState, useEffect } from 'react';
import { getAllPokemonMoves, getMoveDetails, getNextEvolution, getPokemonSprite, getPokemonTypeByName, getPokemonWeaknesses } from '../../Services/API';

const useTeamTrackerLogic = (team, onAddMove) => {
  const [selectedTeamPokemon, setSelectedTeamPokemon] = useState(null);
  const [moveOptions, setMoveOptions] = useState([]);
  const [showMoveSelector, setShowMoveSelector] = useState(false);
  const [showMovesDetails, setShowMovesDetails] = useState(true);
  const [mostrarLista, setMostrarLista] = useState(true);

  const attackTypesList = [
    'normal', 'fire', 'water', 'electric', 'grass', 'ice',
    'fighting', 'poison', 'ground', 'flying', 'psychic',
    'bug', 'rock', 'ghost', 'dragon', 'dark', 'steel', 'fairy'
  ];

  useEffect(() => {
    const fetchMoves = async () => {
      try {
        const moves = await getAllPokemonMoves();
        setMoveOptions(moves.map(m => ({ value: m, label: m })));
      } catch (err) {
        console.error('Error fetching moves:', err);
      }
    };
    fetchMoves();
  }, []);

  const getEffectiveMultiplier = (pokemon, attackType) => {
    if (!pokemon.weaknesses || pokemon.weaknesses.length === 0) return 1;
    let multiplier = 1;
    pokemon.weaknesses.forEach((weakness) => {
      const key = Object.keys(weakness)[0];
      const relations = weakness[key];
      if (relations.no_damage_from.includes(attackType)) multiplier *= 0;
      else if (relations.double_damage_from.includes(attackType)) multiplier *= 2;
      else if (relations.half_damage_from.includes(attackType)) multiplier *= 0.5;
    });
    return multiplier;
  };

  const getX2Weaknesses = (pokemon) =>
    attackTypesList.filter((type) => getEffectiveMultiplier(pokemon, type) >= 2);

  const dividirPorEstado = (estado) => team.filter((p) => p.estado === estado);

  const handleMoveSelect = async (selectedMoveOption) => {
    try {
      const moveDetails = await getMoveDetails(selectedMoveOption.label);
      const moveObject = {
        name: selectedMoveOption.label,
        type: moveDetails.type,
        damageClass: moveDetails.damageClass,
        effectiveAgainst: moveDetails.effectiveAgainst,
        power: moveDetails.power,
        pp: moveDetails.pp,
        description: moveDetails.description,
        accuracy: moveDetails.accuracy,
      };
      if (!selectedTeamPokemon.moves) selectedTeamPokemon.moves = [];
      selectedTeamPokemon.moves.push(moveObject);
      setSelectedTeamPokemon({ ...selectedTeamPokemon });
      if (onAddMove) onAddMove({ ...selectedTeamPokemon });
      setShowMoveSelector(false);
    } catch (err) {
      console.error('Error adding move:', err);
    }
  };

  const handleRemoveMoveFromTeam = (pokemonIndex, moveIndex) => {
    const updated = { ...team[pokemonIndex] };
    if (updated.moves) {
      updated.moves = updated.moves.filter((_, idx) => idx !== moveIndex);
      if (onAddMove) onAddMove(updated);
      if (selectedTeamPokemon?.name === updated.name) {
        setSelectedTeamPokemon({ ...updated });
      }
    }
  };

  const evolucionarPokemon = async (index) => {
    const actual = team[index];
    const evolucion = await getNextEvolution(actual.name);
    if (!evolucion) return;

    const nuevoPokemon = {
      ...actual,
      name: evolucion.name,
      nickname: actual.nickname === actual.name ? evolucion.name : actual.nickname,
      sprite: await getPokemonSprite(evolucion.name),
      types: await getPokemonTypeByName(evolucion.name),
      weaknesses: await getPokemonWeaknesses(evolucion.name),
    };

    team[index] = nuevoPokemon;
    if (onAddMove) onAddMove(nuevoPokemon);
    setSelectedTeamPokemon(null);
  };

  return {
    selectedTeamPokemon,
    setSelectedTeamPokemon,
    moveOptions,
    showMoveSelector,
    setShowMoveSelector,
    showMovesDetails,
    setShowMovesDetails,
    mostrarLista,
    setMostrarLista,
    getEffectiveMultiplier,
    getX2Weaknesses,
    dividirPorEstado,
    handleMoveSelect,
    handleRemoveMoveFromTeam,
    evolucionarPokemon,
  };
};

export default useTeamTrackerLogic;