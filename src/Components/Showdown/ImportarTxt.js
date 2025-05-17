// ImportarTxt.js
import React, { useState } from 'react';
import {
    getPokemonSprite,
    getPokemonTypeByName,
    getPokemonWeaknesses,
    getMoveDetails
} from '../../Services/API';

const ImportarTxt = ({ onImportPokemons }) => {
    const [error, setError] = useState("");

    // Función para actualizar la información del Pokémon utilizando la API
    const updatePokemonData = async (pokemon) => {
        try {
            // Obtenemos la imagen, tipos y debilidades usando el nombre
            const sprite = await getPokemonSprite(pokemon.name);
            const types = await getPokemonTypeByName(pokemon.name);
            const weaknesses = await getPokemonWeaknesses(pokemon.name);

            // Actualizamos la información de cada movimiento (si es que tiene nombre)
            // Dentro de updatePokemonData
            const updatedMoves = await Promise.all(
                pokemon.moves.map(async (move) => {
                    if (move.name && move.name !== "N/A") {
                        try {
                            // Convertir el nombre del movimiento: reemplazar espacios por guiones y pasarlo a minúsculas
                            const moveSlug = move.name.toLowerCase().replace(/\s+/g, '-');
                            const moveDetails = await getMoveDetails(moveSlug);
                            return {
                                ...move,
                                type: moveDetails.type,
                                damageClass: moveDetails.damageClass,
                                effectiveAgainst: moveDetails.effectiveAgainst,
                                power: moveDetails.power,
                                pp: moveDetails.pp,
                                accuracy: moveDetails.accuracy,
                                description: moveDetails.description,
                            };
                        } catch (moveError) {
                            // Si falla la actualización de un movimiento, dejamos los valores por defecto
                            return move;
                        }
                    }
                    return move;
                })
            );


            return { ...pokemon, sprite, types, weaknesses, moves: updatedMoves };
        } catch (err) {
            console.error("Error updating data for", pokemon.name, err);
            return pokemon;
        }
    };

    const handleFileChange = (event) => {
        const file = event.target.files[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = async (e) => {
            const text = e.target.result;
            try {
                const parsedPokemons = parseShowdownTxt(text);
                // Actualizamos cada Pokémon con los datos de la API
                const updatedPokemons = await Promise.all(
                    parsedPokemons.map((pokemon) => updatePokemonData(pokemon))
                );
                onImportPokemons(updatedPokemons);
            } catch (err) {
                setError("Error al parsear el archivo: " + err.message);
            }
        };
        reader.readAsText(file);
    };

    // Función que parsea el formato de txt de Pokémon Showdown.
    // Formato del header: "Apodo (Nombre del pokemon) (Género) @ Item"
    // Se ignora el Apodo; si no hay Género o Item se asigna "N/A".
    const parseShowdownTxt = (text) => {
        // Divide el contenido en bloques (para cada Pokémon)
        const blocks = text.split(/\n\s*\n/);
        const pokemons = blocks.map((block) => {
            // Separamos las líneas y eliminamos espacios extras y líneas vacías.
            const lines = block.split('\n').map(line => line.trim()).filter(line => line.length > 0);
            if (lines.length < 7) {
                throw new Error("Bloque incompleto: " + block);
            }
            // Regex actualizado: ignoramos el apodo y capturamos el Nombre, Género e Item (opcional)
            // Formato: "Apodo (Nombre) (Género) @ Item" ó "Apodo (Nombre) (Género)"
            const headerRegex = /^.+? \((.+?)\)(?: \((.+?)\))?(?: @ (.+))?$/;
            const headerMatch = lines[0].match(headerRegex);
            if (!headerMatch) {
                throw new Error("Formato de header incorrecto: " + lines[0]);
            }
            const [, name, gender, item] = headerMatch;
            const finalGender = gender ? gender : "N/A";
            const finalItem = item ? item : "N/A";

            // Línea 2: Ability
            const abilityLine = lines[1];
            const ability = abilityLine.startsWith("Ability:") ? abilityLine.replace("Ability:", "").trim() : "N/A";

            // Línea 3: Level
            const levelLine = lines[2];
            const level = levelLine.startsWith("Level:") ? levelLine.replace("Level:", "").trim() : "N/A";

            // Línea 4: Happiness
            const happinessLine = lines[3];
            const happiness = happinessLine.startsWith("Happiness:") ? happinessLine.replace("Happiness:", "").trim() : "N/A";

            // Línea 5: EVs
            const evsLine = lines[4];
            const evs = evsLine.startsWith("EVs:") ? evsLine.replace("EVs:", "").trim() : "N/A";

            // Línea 6: Nature
            const nature = lines[5] || "N/A";

            // Línea 7: IVs
            const ivsLine = lines[6];
            const ivs = ivsLine.startsWith("IVs:") ? ivsLine.replace("IVs:", "").trim() : "N/A";

            // Las líneas restantes son los movimientos (que comienzan con "-")
            const moves = [];
            for (let i = 7; i < lines.length; i++) {
                if (lines[i].startsWith("- ")) {
                    const moveName = lines[i].substring(2).trim();
                    moves.push({
                        name: moveName,
                        type: "N/A",
                        damageClass: "N/A",
                        effectiveAgainst: { doubleDamageTo: [] },
                        power: "N/A",
                        pp: "N/A",
                        accuracy: "N/A",
                        description: "N/A",
                    });
                }
            }

            return {
                name,
                species: "", // No se incluye en el TXT
                gender: finalGender,
                item: finalItem,
                ability,
                level,
                happiness,
                evs,
                nature,
                ivs,
                moves,
                types: [],      // Se rellenará mediante la API
                weaknesses: [], // Se puede recalcular usando la API
                sprite: "",     // Se actualizará mediante la API
            };
        }).filter(pokemon => pokemon !== null);
        return pokemons;
    };

    return (
        <div className="importar-txt-container">
            <label className="btn-min" style={{ cursor: 'pointer' }}>
                Seleccionar archivo
                <input
                    type="file"
                    accept=".txt"
                    onChange={handleFileChange}
                    style={{ display: 'none' }}
                />
            </label>
            {error && <p className="error">{error}</p>}
        </div>

    );
};

export default ImportarTxt;