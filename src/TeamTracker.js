// TeamTracker.js
import React, { useState, useEffect } from 'react';
import Select from 'react-select';
import { getAllPokemonMoves, getMoveDetails } from './Services/API';
import './Components/TeamTracker.css'


const TeamTracker = ({ team, onRemovePokemon, onAddMove }) => {
    const [selectedTeamPokemon, setSelectedTeamPokemon] = useState(null);
    const [showMovesDetails, setShowMovesDetails] = useState(true);

    const [moveOptions, setMoveOptions] = useState([]);
    const [showMoveSelector, setShowMoveSelector] = useState(false);
    const typeColors = {
        fire: '#e25822',
        water: '#3399ff',
        grass: '#66cc33',
        electric: '#ffcc00',
        ice: '#99d9ea',
        fighting: '#cc3300',
        poison: '#9933ff',
        ground: '#d2b48c',
        flying: '#6699ff',
        psychic: '#ff66cc',
        bug: '#99cc33',
        rock: '#b3a369',
        ghost: '#6666cc',
        dragon: '#6666ff',
        dark: '#333333',
        steel: '#99aabb',
        fairy: '#ff99cc',
        normal: '#a8a878',
    };

    // Lista fija de tipos para el resumen de debilidades
    const attackTypesList = [
        'normal', 'fire', 'water', 'electric', 'grass', 'ice',
        'fighting', 'poison', 'ground', 'flying', 'psychic',
        'bug', 'rock', 'ghost', 'dragon', 'dark', 'steel', 'fairy'
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
            }
        });
        return multiplier;
    };

    const getX2Weaknesses = (pokemon) => {
        return attackTypesList.filter((attackType) => {
            const mult = getEffectiveMultiplier(pokemon, attackType);
            return mult >= 2;
        });
    };

    // Cargar opciones de movimientos al montar
    useEffect(() => {
        const fetchMoves = async () => {
            try {
                const moves = await getAllPokemonMoves();
                const options = moves.map((move) => ({ value: move, label: move }));
                setMoveOptions(options);
            } catch (error) {
                console.error('Error fetching moves:', error);
            }
        };
        fetchMoves();
    }, []);

    // Handler para agregar un movimiento al Pokémon seleccionado
    const handleMoveSelect = async (selectedMoveOption) => {
        try {
            const moveDetails = await getMoveDetails(selectedMoveOption.label);
            const moveObject = {
                name: selectedMoveOption.label,
                type: moveDetails.type,
                damageClass: moveDetails.damageClass,
                effectiveAgainst: moveDetails.effectiveAgainst,
                power: moveDetails.power,         // Daño del movimiento
                pp: moveDetails.pp,               // Puntos de poder
                description: moveDetails.description, // Descripción del movimiento
                accuracy: moveDetails.accuracy,   // Precisión
            };

            // Si el Pokémon no tiene el array "moves", se inicializa
            if (!selectedTeamPokemon.moves) {
                selectedTeamPokemon.moves = [];
            }
            selectedTeamPokemon.moves.push(moveObject);
            // Actualizamos el estado del Pokémon seleccionado para forzar re-render
            setSelectedTeamPokemon({ ...selectedTeamPokemon });
            if (onAddMove) {
                onAddMove(selectedTeamPokemon, moveObject);
            }
            setShowMoveSelector(false);
        } catch (error) {
            console.error('Error adding move:', error);
        }
    };


    const handleRemoveMoveFromTeam = (pokemonIndex, moveIndex) => {
        // Creamos una copia del equipo
        const updatedTeam = [...team];
        // Verificamos que el Pokémon tenga movimientos
        if (updatedTeam[pokemonIndex].moves) {
            updatedTeam[pokemonIndex].moves = updatedTeam[pokemonIndex].moves.filter(
                (_, idx) => idx !== moveIndex
            );
            // Actualizamos el equipo global llamando a onAddMove (o el callback correspondiente)
            if (onAddMove) {
                onAddMove(updatedTeam[pokemonIndex]);
            }
            // Si el Pokémon eliminado es el seleccionado, actualizamos su estado local
            if (selectedTeamPokemon && selectedTeamPokemon.name === updatedTeam[pokemonIndex].name) {
                setSelectedTeamPokemon({ ...updatedTeam[pokemonIndex] });
            }
        }
    };


    return (
        <div className="team-tracker">
            <h2 className='titulo bold'>Team Tracker</h2>
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
                                        <span style={{ marginLeft: '8px', flexGrow: 0.4 }}>
                                            {pokemon.name} – Tipos:
                                            <ul
                                                className="boxTipo"
                                                style={{ display: 'inline-block', marginLeft: '4px' }}
                                            >
                                                {pokemon.types.map((type) => (
                                                    <li key={type} className={`tipo ${type.toLowerCase()}`}>
                                                        {type}
                                                    </li>
                                                ))}
                                            </ul>
                                        </span>
                                    </div>
                                    <button className='btn' onClick={() => onRemovePokemon(index)}>
                                        Eliminar
                                    </button>
                                </li>
                            ))}
                        </ul>
                    </div>

                    {/* Resumen de debilidades con movimientos asociados */}
                    <div className="team-summary">
                        <h3 className='titulo bold'>Resumen de debilidades (x2) por Pokémon:</h3>
                        <div className="summary-columns" style={{ display: 'flex' }}>
                            {team.map((pokemon, index) => (
                                <div
                                    key={index}
                                    onClick={() => setSelectedTeamPokemon(pokemon)}
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
                                    {/* Sección de movimientos asociados */}
                                    <div style={{ marginTop: '10px' }}>
                                        <h5>Movimientos:</h5>
                                        {pokemon.moves && pokemon.moves.length > 0 ? (
                                            <ul style={{ listStyle: 'none', padding: 0 }}>
                                                {pokemon.moves.map((move, idx) => (
                                                    <li
                                                        key={idx}
                                                        style={{
                                                            display: 'flex',
                                                            alignItems: 'center',
                                                            justifyContent: 'center',
                                                            marginBottom: '4px',
                                                        }}
                                                    >
                                                        <span
                                                            className={move.type.toLowerCase()} // Se usa la clase correspondiente al tipo
                                                            style={{
                                                                width: '100px',
                                                                display: 'block',
                                                                textAlign: 'center'
                                                            }}
                                                        >
                                                            {move.name}
                                                        </span>
                                                        <button
                                                            className="btn tin"
                                                            onClick={() => handleRemoveMoveFromTeam(index, idx)}
                                                            style={{
                                                                marginLeft: '10px',
                                                                padding: '2px 6px',
                                                                fontSize: '12px',
                                                                cursor: 'pointer',
                                                            }}
                                                        >
                                                            Eliminar
                                                        </button>
                                                    </li>
                                                ))}
                                            </ul>
                                        ) : (
                                            <p>No hay movimientos asignados.</p>
                                        )}
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                    {/* Detalles del Pokémon seleccionado */}
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
                                        <li key={type} className={`tipo ${type.toLowerCase()}`}>
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
                                {/* Botón para ocultar o mostrar la sección de Movimientos */}
                                <button
                                    className="btn"
                                    onClick={() => setShowMovesDetails(!showMovesDetails)}
                                    style={{ marginTop: '10px' }}
                                >
                                    {showMovesDetails ? 'Ocultar Movimientos' : 'Mostrar Movimientos'}
                                </button>

                                {/* Nueva sección: Lista de Movimientos Asignados con detalles */}
                                {showMovesDetails && (
                                    <div style={{ marginTop: '20px' }}>
                                        <h4>Movimientos Asignados:</h4>
                                        {selectedTeamPokemon.moves && selectedTeamPokemon.moves.length > 0 ? (
                                            <ul style={{ listStyle: 'none', padding: 0 }}>
                                                {selectedTeamPokemon.moves.map((move, i) => (
                                                    <li
                                                        key={i}
                                                        style={{
                                                            border: '1px solid #aaa',
                                                            margin: '4px',
                                                            padding: '4px',
                                                            textAlign: 'left'
                                                        }}
                                                    >
                                                        <div style={{ textAlign: 'center' }}>
                                                            <strong>{move.name}</strong>
                                                        </div>
                                                        <div style={{ display: 'flex', justifyContent: 'space-around', marginTop: '10px' }}>
                                                            <div>
                                                                <strong>Tipo:</strong>
                                                                <br />
                                                                <ul className="boxTipo" style={{ display: 'inline-block', marginLeft: '4px' }}>
                                                                    <li className={`tipo ${move.type.toLowerCase()}`}>
                                                                        {move.type}
                                                                    </li>
                                                                </ul>
                                                            </div>
                                                            <div>
                                                                <strong>Clase:</strong>
                                                                <br />
                                                                <ul className="boxTipo" style={{ display: 'inline-block', marginLeft: '4px' }}>
                                                                    <li className={`tipo ${move.damageClass.toLowerCase()}`}>
                                                                        {move.damageClass}
                                                                    </li>
                                                                </ul>
                                                            </div>
                                                            <div>
                                                                <strong>Efectivo contra:</strong>
                                                                <br />
                                                                <ul className="boxTipo" style={{ display: 'inline-block', marginLeft: '4px' }}>
                                                                    {move.effectiveAgainst &&
                                                                        move.effectiveAgainst.doubleDamageTo &&
                                                                        move.effectiveAgainst.doubleDamageTo.length > 0 ? (
                                                                        move.effectiveAgainst.doubleDamageTo.map((t) => (
                                                                            <li key={t} className={`tipo ${t.toLowerCase()}`}>
                                                                                {t}
                                                                            </li>
                                                                        ))
                                                                    ) : (
                                                                        <li>N/A</li>
                                                                    )}
                                                                </ul>
                                                            </div>
                                                        </div>
                                                        <div style={{ display: 'flex', justifyContent: 'space-around', marginTop: '10px' }}>
                                                            <div>
                                                                <strong>Daño:</strong>
                                                                <br />
                                                                {move.power !== undefined ? move.power : 'N/A'}
                                                            </div>
                                                            <div>
                                                                <strong>PP:</strong>
                                                                <br />
                                                                {move.pp !== undefined ? move.pp : 'N/A'}
                                                            </div>
                                                            <div>
                                                                <strong>Precisión:</strong>
                                                                <br />
                                                                {move.accuracy !== null ? move.accuracy : 'N/A'}
                                                            </div>
                                                        </div>
                                                        <div style={{ marginTop: '10px', textAlign: 'center' }}>
                                                            <strong>Descripción:</strong> {move.description ? move.description : 'N/A'}
                                                        </div>
                                                        <button
                                                            className="btn tin"
                                                            onClick={() => handleRemoveMoveFromTeam(i)}
                                                            style={{
                                                                marginTop: '4px',
                                                                padding: '2px 6px',
                                                                fontSize: '12px',
                                                                cursor: 'pointer'
                                                            }}
                                                        >
                                                            Eliminar
                                                        </button>
                                                    </li>
                                                ))}
                                            </ul>
                                        ) : (
                                            <p>No hay movimientos asignados.</p>
                                        )}
                                        {showMoveSelector ? (
                                            <div style={{ marginTop: '10px' }}>
                                                <Select
                                                    options={moveOptions}
                                                    onChange={handleMoveSelect}
                                                    placeholder="Buscar movimiento..."
                                                />
                                            </div>
                                        ) : (
                                            <button className="btn" onClick={() => setShowMoveSelector(true)}>
                                                Agregar Movimiento
                                            </button>
                                        )}
                                    </div>
                                )}
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
