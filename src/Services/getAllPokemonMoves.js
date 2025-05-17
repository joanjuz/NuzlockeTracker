import axios from 'axios';
const baseUrl = 'https://pokeapi.co/api/v2/';

const getAllPokemonMoves = async () => {
  try {
    const response = await axios.get(`${baseUrl}move/?limit=100000&offset=0`);
    return response.data.results.map((move) => move.name);
  } catch (error) {
    throw new Error('Error fetching Pokemon moves');
  }
};

export default getAllPokemonMoves;
