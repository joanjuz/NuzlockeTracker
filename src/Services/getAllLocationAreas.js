// Usa la API fetch nativa
const getAllLocationAreas = async () => {
  const res = await fetch("https://pokeapi.co/api/v2/location-area?limit=1000");
  const data = await res.json();
  return data.results; // [{ name, url }]
};

export default getAllLocationAreas;
