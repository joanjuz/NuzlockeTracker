// Obtiene las rutas disponibles según la versión del juego
const getRutasPorJuego = async (nombreVersion) => {
  try {
    // Paso 1: obtener la lista de versiones
    const versionesRes = await fetch('https://pokeapi.co/api/v2/version');
    const versionesData = await versionesRes.json();
    const versionMatch = versionesData.results.find(v => v.name === nombreVersion);
    if (!versionMatch) throw new Error(`Versión no encontrada: ${nombreVersion}`);

    // Paso 2: obtener la información de la versión → version_group
    const versionDetalle = await fetch(versionMatch.url);
    const versionDetalleData = await versionDetalle.json();
    const versionGroupUrl = versionDetalleData.version_group.url;

    // Paso 3: obtener el grupo de versión → regiones asociadas
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

    // Devolver rutas únicas ordenadas alfabéticamente
    const rutasUnicas = Array.from(new Set(rutas)).sort();
    return rutasUnicas;
  } catch (error) {
    console.error('Error al obtener rutas por juego:', error);
    return [];
  }
};

export default getRutasPorJuego;
