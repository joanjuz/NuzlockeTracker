// GenerarTxt.js
import React from 'react';

const GenerarTxt = ({ team, showPreview = true }) => {
  const generateTextContent = () => {
    return team
      .map((pokemon) => {
        // Apodo: si se definió nickname, se usa; de lo contrario se usa el nombre
        const apodo = pokemon.nickname && pokemon.nickname.trim() !== "" ? pokemon.nickname : pokemon.name;
        // Especie: se toma de pokemon.species, sino se usa el nombre
        const species = pokemon.species && pokemon.species.trim() !== "" ? pokemon.species : pokemon.name;
        const gender = pokemon.gender && pokemon.gender.trim() !== "" ? pokemon.gender : "N/A";
        const item = pokemon.item && pokemon.item.trim() !== "" ? pokemon.item : "N/A";

        // Primera línea: "Apodo (Especie) (Género) @ Item"
        const headerLine = `${apodo} (${species}) (${gender}) @ ${item}`;

        // Otras líneas
        const abilityLine = `Ability: ${pokemon.ability || "N/A"}`;
        const levelLine = `Level: ${pokemon.level || "N/A"}`;
        const happinessLine = `Happiness: ${pokemon.happiness || "N/A"}`;
        const evsLine = `EVs: ${pokemon.evs || "N/A"}`;
        // Si la cadena de naturaleza ya incluye "Nature", no se repite; de lo contrario se añade
        const natureLine = pokemon.nature && pokemon.nature.includes("Nature")
          ? pokemon.nature
          : `${pokemon.nature || "N/A"} Nature`;
        const ivsLine = `IVs: ${pokemon.ivs || "N/A"}`;

        // Lista de movimientos, cada uno en una línea con prefijo "- "
        const movesLines =
          pokemon.moves && pokemon.moves.length > 0
            ? pokemon.moves.map((move) => `- ${move.name}`).join("\n")
            : "";

        return [
          headerLine,
          abilityLine,
          levelLine,
          happinessLine,
          evsLine,
          natureLine,
          ivsLine,
          movesLines
        ]
          .filter(line => line !== "")
          .join("\n");
      })
      .join("\n\n"); // Bloques separados por una línea vacía
  };

  const handleGenerateTxt = () => {
    const textContent = generateTextContent();
    const blob = new Blob([textContent], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'equipo.txt';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="generar-txt-container">
      {team.length === 0 ? (
        <p>No tienes Pokémon en tu equipo.</p>
      ) : (
        <div>
          {showPreview && (
            <pre className="txt-preview">{generateTextContent()}</pre>
          )}
          <button className="btn-min" onClick={handleGenerateTxt}>
            Generar txt
          </button>
        </div>
      )}
    </div>
  );
};

export default GenerarTxt;
