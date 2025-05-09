// API.js
import axios from 'axios';


const baseUrl = 'https://pokeapi.co/api/v2/';

const getPokemonTypes = async () => {
  const response = await axios.get(`${baseUrl}type`);
  return response.data.results;
};

const getPokemonNames = async () => {
  try {
    const response = await axios.get(`${baseUrl}pokemon/?limit=100000&offset=0`);
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
    const response = await axios.get(`${baseUrl}move/?limit=100000&offset=0`);
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
    return {
      doubleDamageTo: damageRelations.double_damage_to.map((t) => t.name),
      halfDamageTo: damageRelations.half_damage_to.map((t) => t.name),
      noDamageTo: damageRelations.no_damage_to.map((t) => t.name),
    };
  } catch (error) {
    throw new Error(`Error fetching types for attack effective against ${attackName}`);
  }
};

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

    // Obtener descripción del movimiento (buscando en effect_entries en inglés)
    let description = 'N/A';
    if (response.data.effect_entries && response.data.effect_entries.length > 0) {
      const englishEntry = response.data.effect_entries.find(
        (entry) => entry.language.name === 'en'
      );
      if (englishEntry) {
        description = englishEntry.short_effect || englishEntry.effect || 'N/A';
      }
    }

    // Obtener contra lo que es efectivo: consultar el endpoint del tipo del movimiento
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



// API.js (agregar al final o donde correspondan las funciones)
const getAllItems = async () => {
  try {
    const response = await axios.get(`${baseUrl}item/?limit=100000`);
    return response.data.results.map((item) => item.name);
  } catch (error) {
    throw new Error('Error fetching items');
  }
};
export async function getGameVersions() {
  const res = await fetch("https://pokeapi.co/api/v2/version/");
  const data = await res.json();
  return data.results; // [{ name, url }]
}

export async function getAllLocationAreas() {
  const res = await fetch("https://pokeapi.co/api/v2/location-area?limit=1000");
  const data = await res.json();
  return data.results; // [{ name, url }]
}
export async function getRutasPorJuego(nombreVersion) {
  try {
    // Paso 1: obtener la lista de versiones
    const versionesRes = await fetch('https://pokeapi.co/api/v2/version');
    const versionesData = await versionesRes.json();
    const versionMatch = versionesData.results.find(v => v.name === nombreVersion);

    if (!versionMatch) throw new Error(`Versión no encontrada: ${nombreVersion}`);

    // Paso 2: obtener versión → version_group
    const versionDetalle = await fetch(versionMatch.url);
    const versionDetalleData = await versionDetalle.json();
    const versionGroupUrl = versionDetalleData.version_group.url;

    // Paso 3: obtener grupo de versión → regiones
    const grupoRes = await fetch(versionGroupUrl);
    const grupoData = await grupoRes.json();
    const regiones = grupoData.regions;

    if (!regiones.length) throw new Error('No se encontraron regiones asociadas.');

    // Paso 4: obtener las ubicaciones (locations) de cada región
    let rutas = [];
    for (const region of regiones) {
      const regionRes = await fetch(region.url);
      const regionData = await regionRes.json();

      const locations = regionData.locations.map(loc => loc.name);
      rutas.push(...locations);
    }

    // Devolver rutas únicas ordenadas
    const rutasUnicas = Array.from(new Set(rutas)).sort();
    return rutasUnicas;
  } catch (error) {
    console.error('Error al obtener rutas por juego:', error);
    return [];
  }
}



export { 
  getPokemonTypes, 
  getPokemonNames, 
  getPokemonTypeByName, 
  getPokemonWeaknesses, 
  getPokemonSprite, 
  getAllPokemonMoves, 
  getAttackTypeByName, 
  getAttackEffectiveAgainst,
  getMoveDetails,
  getAllItems  // Asegúrate de exportar la nueva función.
};

