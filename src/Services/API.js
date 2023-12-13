import axios from 'axios';

const getPokemonTypes = async () => {
    const response = await axios.get('https://pokeapi.co/api/v2/type/');
    return response.data.results;
  };

const baseUrl = 'https://pokeapi.co/api/v2/';

const getPokemonNames = async () => {
  try {
    const response = await axios.get(`${baseUrl}pokemon/?limit=1000`);
    return response.data.results.map((pokemon) => pokemon.name);
  } catch (error) {
    throw new Error('Error fetching Pokemon names');
  }
};

const getPokemonTypeByName = async (pokemonName) => {
  try {
    const response = await axios.get(`${baseUrl}pokemon/${pokemonName}`);
    return response.data.types.map((type) => type.type.name);
  } catch (error) {
    throw new Error(`Error fetching Pokemon type for ${pokemonName}`);
  }
};

const getPokemonWeaknesses = async (pokemonName) => {
    try {
      const response = await axios.get(`${baseUrl}pokemon/${pokemonName}`);
      const types = response.data.types.map((type) => type.type.name);
  
      // Obtener debilidades basadas en los tipos
      const weaknesses = await Promise.all(
        types.map(async (type) => {
          const typeResponse = await axios.get(`${baseUrl}type/${type}`);
          const damageRelations = typeResponse.data.damage_relations;
          return {
            [type]: {
              double_damage_from: damageRelations.double_damage_from.map((weakness) => weakness.name),
              half_damage_from: damageRelations.half_damage_from.map((resistance) => resistance.name),
              no_damage_from: damageRelations.no_damage_from.map((immune) => immune.name),
            },
          };
        })
      );
  
      return weaknesses;
    } catch (error) {
      throw new Error(`Error fetching Pokemon weaknesses for ${pokemonName}`);
    }
  };
  const getPokemonSprite = async (pokemonName) => {
    try {
      const response = await axios.get(`${baseUrl}pokemon/${pokemonName}`);
      return response.data.sprites.front_default;
    } catch (error) {
      throw new Error(`Error fetching Pokemon sprite for ${pokemonName}`);
    }
  };
  
  const getAllPokemonMoves = async () => {
    try {
      const response = await axios.get(`${baseUrl}move/?limit=1000`);
      return response.data.results.map((move) => move.name);
    } catch (error) {
      throw new Error('Error fetching Pokemon moves');
    }
  };
  const getAttackTypeByName = async (attackName) => {
    try {
      const response = await axios.get(`${baseUrl}move/${attackName}`);
      return response.data.type.name;
    } catch (error) {
      throw new Error(`Error fetching type for attack ${attackName}`);
    }
  };
  const getAttackEffectiveAgainst = async (attackName) => {
    try {
      const attackType = await getAttackTypeByName(attackName);
  
      const response = await axios.get(`${baseUrl}type/${attackType}`);
      const damageRelations = response.data.damage_relations;
  
      const doubleDamageTo = damageRelations.double_damage_to.map((type) => type.name);
      const halfDamageTo = damageRelations.half_damage_to.map((type) => type.name);
      const noDamageTo = damageRelations.no_damage_to.map((type) => type.name);
  
      return {
        doubleDamageTo,
        halfDamageTo,
        noDamageTo,
      };
    } catch (error) {
      throw new Error(`Error fetching types for attacks effective against ${attackName}`);
    }
  };
  export { getPokemonTypes, getPokemonNames, getPokemonTypeByName, getPokemonWeaknesses, getPokemonSprite, getAllPokemonMoves, getAttackTypeByName, getAttackEffectiveAgainst };
  
  