// valoracion.js
import React, { useState } from 'react';
import '.container/Valoracion.css';

const attackTypesList = [
  'normal', 'fire', 'water', 'electric', 'grass', 'ice',
  'fighting', 'poison', 'ground', 'flying', 'psychic',
  'bug', 'rock', 'ghost', 'dragon', 'dark', 'steel', 'fairy'
];

// Función para calcular el multiplicador efectivo para un ataque dado en un Pokémon,
// basándose en la información de debilidades almacenada en pokemon.weaknesses.
const getEffectiveMultiplier = (pokemon, attackType) => {
  if (!pokemon.weaknesses || pokemon.weaknesses.length === 0) {
    return 1;
  }
  let multiplier = 1;
  pokemon.weaknesses.forEach((weakness) => {
    const key = Object.keys(weakness)[0];
    const relations = weakness[key];
    if (relations.no_damage_from.includes(attackType)) {
      multiplier *= 0;
    } else if (relations.double_damage_from.includes(attackType)) {
      multiplier *= 2;
    } else if (relations.half_damage_from.includes(attackType)) {
      multiplier *= 0.5;
    }
  });
  return multiplier;
};

// Mapeo de sugerencias para cubrir las debilidades más frecuentes
const coverageSuggestions = {
  fighting: "Tienes muchas debilidades a Fighting. Considera añadir Pokémon que tengan tipologías como Fairy, Psychic o Flying para cubrir esas carencias.",
  fire: "Tienes muchas debilidades a Fire. Pokémon de tipo Water o Rock podrían compensar esta vulnerabilidad.",
  water: "Tu equipo es vulnerable a Water. Pokémon de tipo Electric o Grass ayudarían a equilibrar la cobertura.",
  electric: "Tu equipo es débil frente a Electric. Incluir Pokémon de tipo Ground es recomendable.",
  grass: "Observas vulnerabilidad a Grass. Pokémon de tipo Fire, Ice o Bug pueden ser una buena opción.",
  ice: "Tienes problemas contra Ice. Considera añadir Pokémon con tipología Fire o Rock.",
  psychic: "Las debilidades a Psychic son altas. Pokémon de tipo Dark o Bug podrían ayudar a cubrirlas.",
  poison: "Para reducir la vulnerabilidad a Poison, Pokémon de tipo Ground o Psychic pueden ser útiles.",
  ground: "Las debilidades a Ground requieren cobertura. Pokémon de tipo Water o Grass son recomendables.",
  flying: "Frente a Flying, Pokémon de tipo Electric o Rock pueden ofrecer buena cobertura.",
  bug: "Si tienes debilidades a Bug, Pokémon de tipo Fire, Flying o Rock pueden compensar.",
  rock: "Tu equipo es vulnerable a Rock. Pokémon de tipo Water, Grass o Fighting ayudarían a balancear la defensa.",
  ghost: "Debilidades a Ghost se pueden cubrir con Pokémon de tipo Ghost o Dark.",
  dragon: "Para debilidades a Dragon, Pokémon de tipo Fairy son muy recomendables.",
  dark: "Si tu equipo sufre contra Dark, considera incluir Pokémon de tipo Fighting, Bug o Fairy.",
  steel: "Tienes vulnerabilidad a Steel. Pokémon de tipo Fire o Fighting podrían mejorar la cobertura.",
  fairy: "Si la debilidad es a Fairy, Pokémon de tipo Poison o Steel ayudarían.",
  normal: "Normal suele requerir cobertura. Un Pokémon de tipo Fighting puede ser útil para compensar."
};

const Valoracion = ({ team }) => {
  const [evaluation, setEvaluation] = useState("");

  // Función para evaluar el equipo
  const evaluateTeam = () => {
    const weaknessCount = {};
    team.forEach((pokemon) => {
      attackTypesList.forEach((attackType) => {
        const mult = getEffectiveMultiplier(pokemon, attackType);
        // Solo contamos aquellas situaciones donde la vulnerabilidad es exacta a 2x
        if (mult === 2) {
          weaknessCount[attackType] = (weaknessCount[attackType] || 0) + 1;
        }
      });
    });

    // Determinamos la debilidad más frecuente
    let maxWeakness = null;
    let maxCount = 0;
    for (const type in weaknessCount) {
      if (weaknessCount[type] > maxCount) {
        maxWeakness = type;
        maxCount = weaknessCount[type];
      }
    }
    if (maxWeakness && coverageSuggestions[maxWeakness]) {
      return coverageSuggestions[maxWeakness];
    }
    return "Tu equipo parece tener una buena cobertura de tipos.";
  };

  const handleEvaluateTeam = () => {
    const result = evaluateTeam();
    setEvaluation(result);
  };

  return (
    <div className="valoracion-container">
      <h2 className="titulo bold">Valoración del Equipo</h2>
      {team.length === 0 ? (
        <p>No tienes Pokémon en tu equipo.</p>
      ) : (
        <div className="equipo-valoracion">
          <ul className="lista-pokemons">
            {team.map((pokemon, index) => (
              <li key={index} className="pokemon-valoracion">
                <span className="pokemon-name">{pokemon.name}</span> -{" "}
                <span className="pokemon-types">{pokemon.types.join(', ')}</span>
              </li>
            ))}
          </ul>
          <button className="btn evaluar-btn" onClick={handleEvaluateTeam}>
            Valorar Equipo
          </button>
          {evaluation && <p className="evaluation-text">{evaluation}</p>}
        </div>
      )}
    </div>
  );
};

export default Valoracion;
