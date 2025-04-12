// TeamTracker.js
import React, { useState } from 'react';

const TeamTracker = ({ team, onRemovePokemon }) => {
    const [selectedTeamPokemon, setSelectedTeamPokemon] = useState(null);

    // Lista fija de tipos de ataque a considerar
    const attackTypesList = [
        'normal',
        'fire',
        'water',
        'electric',
        'grass',
        'ice',
        'fighting',
        'poison',
        'ground',
        'flying',
        'psychic',
        'bug',
        'rock',
        'ghost',
        'dragon',
        'dark',
        'steel',
        'fairy',
    ];

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
            } else {
                multiplier *= 1;
            }
        });
        return multiplier;
    };

    const getX2Weaknesses = (pokemon) => {
        return attackTypesList.filter((attackType) => {
            const mult = getEffectiveMultiplier(pokemon, attackType);
            return mult === 2;
        });
    };

    return (
        <div className="team-tracker">
            <h2>Team Tracker</h2>
            {team.length === 0 ? (
                <p>No hay Pokémon en el equipo.</p>
            ) : (
                <div className="team-container">
                    {/* Listado de Pokémon del equipo */}
                    <div className="team-list">
                        <h3>Equipo:</h3>
                        <ul>
                            {team.map((pokemon, index) => (
                                <li
                                    key={index}
                                    style={{
                                        display: 'flex',
                                        alignItems: 'center',
                                        marginBottom: '8px',
                                    }}
                                    onClick={() => setSelectedTeamPokemon(pokemon)}
                                >
                                    <img
                                        src={pokemon.sprite}
                                        alt={pokemon.name}
                                        style={{ width: '48px', verticalAlign: 'middle' }}
                                    />
                                    <div style={{ width: '600px' }}>
                                        <span style={{ marginLeft: '1px' }}>
                                            {pokemon.name} – Tipos:
                                            <ul className="boxTipo" style={{ display: 'inline-block', marginLeft: '4px' }}>
                                                {pokemon.types.map((type) => (
                                                    <li key={type} className={`tipo ${type.toLowerCase()}`}>
                                                        {type}
                                                    </li>
                                                ))}
                                            </ul>
                                        </span>
                                    </div>

                                    <button className="btn" onClick={() => onRemovePokemon(index)}>Eliminar</button>
                                </li>
                            ))}
                        </ul>
                    </div>

                    {/* Resumen de debilidades del equipo, en columnas según el orden del equipo */}
                    <div className="team-summary">
                        <h3>Resumen de debilidades (x2) por Pokémon:</h3>
                        <div className="summary-columns" style={{ display: 'flex' }}>
                            {team.map((pokemon, index) => (
                                <div
                                    key={index}
                                    style={{
                                        flex: 1,
                                        border: '1px solid #ccc',
                                        margin: '4px',
                                        padding: '4px',
                                        textAlign: 'center',
                                    }}
                                >
                                    <h4>{pokemon.name}</h4>
                                    <ul style={{ listStyle: 'none', padding: 0 }}>
                                        {getX2Weaknesses(pokemon).length > 0 ? (
                                            getX2Weaknesses(pokemon).map((weakness, i) => (
                                                <li key={i} className={`tipo ${weakness}`}>
                                                    {weakness}
                                                </li>
                                            ))
                                        ) : (
                                            <li>No x2 Weakness</li>
                                        )}
                                    </ul>
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Detalles del Pokémon seleccionado al hacer click */}
                    <div className="pokemon-details" style={{ marginTop: '20px' }}>
                        {selectedTeamPokemon ? (
                            <div>
                                <h3>Detalles de {selectedTeamPokemon.name}</h3>
                                <img
                                    src={selectedTeamPokemon.sprite}
                                    alt={selectedTeamPokemon.name}
                                    style={{ width: '96px' }}
                                />
                                <p>
                                    <strong>Tipos:</strong>
                                </p>
                                <ul className="boxTipo">
                                    {selectedTeamPokemon.types.map((type) => (
                                        <li className={`tipo ${type.toLowerCase()}`} key={type}>
                                            {type}
                                        </li>
                                    ))}
                                </ul>
                                <p>
                                    <strong>Weaknesses (x2):</strong>
                                </p>
                                <ul style={{ listStyle: 'none', padding: 0 }}>
                                    {getX2Weaknesses(selectedTeamPokemon).length > 0 ? (
                                        getX2Weaknesses(selectedTeamPokemon).map((weakness, idx) => (
                                            <li key={idx} className={`tipo ${weakness}`}>
                                                {weakness}
                                            </li>
                                        ))
                                    ) : (
                                        <li>No x2 Weakness</li>
                                    )}
                                </ul>
                            </div>
                        ) : (
                            <p>Haz clic en un Pokémon del equipo para ver sus detalles.</p>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
};

export default TeamTracker;
