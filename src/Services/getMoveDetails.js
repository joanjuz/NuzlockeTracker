import axios from 'axios';
const baseUrl = 'https://pokeapi.co/api/v2/';

// Nueva función: getMoveDetails (actualizada con accuracy)
const getMoveDetails = async (moveName) => {
  try {
    const response = await axios.get(`${baseUrl}move/${moveName}`);
    // Datos básicos del movimiento
    const type = response.data.type.name;
    const damageClass = response.data.damage_class.name; // physical, special, or status
    const power = response.data.power;         // Puede ser null
    const pp = response.data.pp;
    const accuracy = response.data.accuracy;   // Nueva propiedad: precisión

    // Obtener descripción del movimiento (buscar effect_entries en inglés)
    let description = 'N/A';
    if (response.data.effect_entries && response.data.effect_entries.length > 0) {
      const englishEntry = response.data.effect_entries.find(
        (entry) => entry.language.name === 'en'
      );
      if (englishEntry) {
        description = englishEntry.short_effect || englishEntry.effect || 'N/A';
      }
    }

    // Obtener contra qué tipos es efectivo: consultar el endpoint del tipo del movimiento
    const effectiveResponse = await axios.get(`${baseUrl}type/${type}`);
    const damageRelations = effectiveResponse.data.damage_relations;
    const effectiveAgainst = {
      doubleDamageTo: damageRelations.double_damage_to.map((d) => d.name),
      halfDamageTo: damageRelations.half_damage_to.map((d) => d.name),
      noDamageTo: damageRelations.no_damage_to.map((d) => d.name),
    };

    return { type, damageClass, effectiveAgainst, power, pp, description, accuracy };
  } catch (error) {
    throw new Error(`Error fetching move details for ${moveName}`);
  }
};

export default getMoveDetails;
