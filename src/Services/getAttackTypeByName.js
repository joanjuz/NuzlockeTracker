import axios from 'axios';
const baseUrl = 'https://pokeapi.co/api/v2/';

const getAttackTypeByName = async (attackName) => {
  try {
    const response = await axios.get(`${baseUrl}move/${attackName}`);
    return response.data.type.name;
  } catch (error) {
    throw new Error(`Error fetching type for attack ${attackName}`);
  }
};

export default getAttackTypeByName;
