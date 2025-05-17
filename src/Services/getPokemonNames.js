import axios from 'axios';
const baseUrl = 'https://pokeapi.co/api/v2/';

const getPokemonNames = async () => {
  try {
    const response = await axios.get(`${baseUrl}pokemon/?limit=100000&offset=0`);
    return response.data.results.map((pokemon) => pokemon.name);
  } catch (error) {
    throw new Error('Error fetching Pokemon names');
  }
};

export default getPokemonNames;
