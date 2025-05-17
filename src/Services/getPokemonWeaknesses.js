import axios from 'axios';
const baseUrl = 'https://pokeapi.co/api/v2/';

const getPokemonWeaknesses = async (pokemonName) => {
  try {
    const response = await axios.get(`${baseUrl}pokemon/${pokemonName}`);
    const types = response.data.types.map((type) => type.type.name);
    const weaknesses = await Promise.all(
      types.map(async (type) => {
        const typeResponse = await axios.get(`${baseUrl}type/${type}`);
        const damageRelations = typeResponse.data.damage_relations;
        return {
          [type]: {
            double_damage_from: damageRelations.double_damage_from.map((d) => d.name),
            half_damage_from: damageRelations.half_damage_from.map((d) => d.name),
            no_damage_from: damageRelations.no_damage_from.map((d) => d.name),
          },
        };
      })
    );
    return weaknesses;
  } catch (error) {
    throw new Error(`Error fetching Pokemon weaknesses for ${pokemonName}`);
  }
};

export default getPokemonWeaknesses;
