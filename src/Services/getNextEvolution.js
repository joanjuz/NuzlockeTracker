// getNextEvolution.js
import axios from 'axios';

export const getNextEvolution = async (pokemonName) => {
  try {
    const speciesUrl = `https://pokeapi.co/api/v2/pokemon-species/${pokemonName.toLowerCase()}`;
    const speciesData = await axios.get(speciesUrl);
    const evoChainUrl = speciesData.data.evolution_chain.url;
    const evoChainData = await axios.get(evoChainUrl);

    const findEvolutions = (chain, target) => {
      if (chain.species.name === target.toLowerCase()) {
        return chain.evolves_to.map(next => {
          const evoDetails = next.evolution_details?.[0] || {};
          return {
            name: next.species.name,
            min_level: evoDetails.min_level || null,
            trigger: evoDetails.trigger?.name || null,
            item: evoDetails.item?.name || null
          };
        });
      }
      for (let evo of chain.evolves_to) {
        const result = findEvolutions(evo, target);
        if (result) return result;
      }
      return null;
    };

    const evolutions = findEvolutions(evoChainData.data.chain, pokemonName);
    return evolutions; // Puede ser null o array con 1+ evoluciones
  } catch (error) {
    console.error('Error fetching evolution:', error);
    return null;
  }
};

export default getNextEvolution;