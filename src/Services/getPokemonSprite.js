import axios from 'axios';
const baseUrl = 'https://pokeapi.co/api/v2/';

const getPokemonSprite = async (pokemonName) => {
  try {
    const response = await axios.get(`${baseUrl}pokemon/${pokemonName}`);
    return response.data.sprites.front_default;
  } catch (error) {
    throw new Error(`Error fetching Pokemon sprite for ${pokemonName}`);
  }
};

export default getPokemonSprite;
