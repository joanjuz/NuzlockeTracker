import axios from 'axios';
const baseUrl = 'https://pokeapi.co/api/v2/';

const getAllItems = async () => {
  try {
    const response = await axios.get(`${baseUrl}item/?limit=100000`);
    return response.data.results.map((item) => item.name);
  } catch (error) {
    throw new Error('Error fetching items');
  }
};

export default getAllItems;
