import axios from 'axios';
import getAttackTypeByName from './getAttackTypeByName';
// Services/getBaseStats.js
const baseUrl = 'https://pokeapi.co/api/v2/';

const getBaseStats = async (name) => {
  const response = await fetch(`${baseUrl}pokemon/${name.toLowerCase()}`);
  const data = await response.json();
  const stats = {};
  data.stats.forEach(s => {
    stats[s.stat.name] = s.base_stat;
  });
  return stats;
};

export default getBaseStats;
