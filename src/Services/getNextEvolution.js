// getNextEvolution.js
import axios from 'axios';

export const getNextEvolution = async (pokemonName) => {
  try {
    const speciesUrl = `https://pokeapi.co/api/v2/pokemon-species/${pokemonName.toLowerCase()}`;
    const speciesData = await axios.get(speciesUrl);
    const evoChainUrl = speciesData.data.evolution_chain.url;
    const evoChainData = await axios.get(evoChainUrl);

    const findEvolution = (chain, target, condition = null) => {
      if (chain.species.name === target.toLowerCase()) {
        if (chain.evolves_to.length > 0) {
          const next = chain.evolves_to[0];
          const evoSpecies = next.species.name;
          const evoDetails = next.evolution_details?.[0] || {};
          return {
            name: evoSpecies,
            min_level: evoDetails.min_level || null,
            trigger: evoDetails.trigger?.name || null,
            item: evoDetails.item?.name || null
          };
        }
        return null;
      }
      for (let evo of chain.evolves_to) {
        const result = findEvolution(evo, target);
        if (result) return result;
      }
      return null;
    };

    const evolution = findEvolution(evoChainData.data.chain, pokemonName);
    return evolution;
  } catch (error) {
    console.error('Error fetching evolution:', error);
    return null;
  }
};

export default getNextEvolution;