import axios from 'axios';
const baseUrl = 'https://pokeapi.co/api/v2/';

const getPokemonTypeByName = async (pokemonName) => {
  try {
    const response = await axios.get(`${baseUrl}pokemon/${pokemonName}`);
    return response.data.types.map((type) => type.type.name);
  } catch (error) {
    throw new Error(`Error fetching Pokemon type for ${pokemonName}`);
  }
};

export default getPokemonTypeByName;
