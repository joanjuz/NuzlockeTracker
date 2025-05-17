import axios from 'axios';
import getAttackTypeByName from './getAttackTypeByName';
const baseUrl = 'https://pokeapi.co/api/v2/';

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

export default getAttackEffectiveAgainst;
