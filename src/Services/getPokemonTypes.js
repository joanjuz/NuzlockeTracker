import axios from 'axios';
const baseUrl = 'https://pokeapi.co/api/v2/';

const getPokemonTypes = async () => {
  const response = await axios.get(`${baseUrl}type`);
  return response.data.results;
};

export default getPokemonTypes;
