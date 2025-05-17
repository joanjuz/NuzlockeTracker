// Usa la API fetch nativa
const getGameVersions = async () => {
  const res = await fetch("https://pokeapi.co/api/v2/version/");
  const data = await res.json();
  return data.results; // [{ name, url }]
};

export default getGameVersions;
