import React, { useState, useEffect } from 'react';
import Select from 'react-select';
import { getAllPokemonMoves, getMoveDetails } from './Services/API';
import './Components/TeamTracker.css';

const TeamTracker = ({ team, onRemovePokemon, onAddMove, onChangeEstado }) => {
    const [selectedTeamPokemon, setSelectedTeamPokemon] = useState(null);
    const [moveOptions, setMoveOptions] = useState([]);
    const [showMoveSelector, setShowMoveSelector] = useState(false);
    const [showMovesDetails, setShowMovesDetails] = useState(true);
    const [mostrarLista, setMostrarLista] = useState(true);


    const attackTypesList = [
        'normal', 'fire', 'water', 'electric', 'grass', 'ice',
        'fighting', 'poison', 'ground', 'flying', 'psychic',
        'bug', 'rock', 'ghost', 'dragon', 'dark', 'steel', 'fairy'
    ];

    const getEffectiveMultiplier = (pokemon, attackType) => {
        if (!pokemon.weaknesses || pokemon.weaknesses.length === 0) return 1;
        let multiplier = 1;
        pokemon.weaknesses.forEach((weakness) => {
            const key = Object.keys(weakness)[0];
            const relations = weakness[key];
            if (relations.no_damage_from.includes(attackType)) multiplier *= 0;
            else if (relations.double_damage_from.includes(attackType)) multiplier *= 2;
            else if (relations.half_damage_from.includes(attackType)) multiplier *= 0.5;
        });
        return multiplier;
    };

    const getX2Weaknesses = (pokemon) =>
        attackTypesList.filter((type) => getEffectiveMultiplier(pokemon, type) >= 2);

    useEffect(() => {
        const fetchMoves = async () => {
            try {
                const moves = await getAllPokemonMoves();
                setMoveOptions(moves.map(m => ({ value: m, label: m })));
            } catch (err) {
                console.error('Error fetching moves:', err);
            }
        };
        fetchMoves();
    }, []);

    const handleMoveSelect = async (selectedMoveOption) => {
        try {
            const moveDetails = await getMoveDetails(selectedMoveOption.label);
            const moveObject = {
                name: selectedMoveOption.label,
                type: moveDetails.type,
                damageClass: moveDetails.damageClass,
                effectiveAgainst: moveDetails.effectiveAgainst,
                power: moveDetails.power,
                pp: moveDetails.pp,
                description: moveDetails.description,
                accuracy: moveDetails.accuracy,
            };
            if (!selectedTeamPokemon.moves) selectedTeamPokemon.moves = [];
            selectedTeamPokemon.moves.push(moveObject);
            setSelectedTeamPokemon({ ...selectedTeamPokemon });
            if (onAddMove) onAddMove({ ...selectedTeamPokemon });
            setShowMoveSelector(false);
        } catch (err) {
            console.error('Error adding move:', err);
        }
    };

    const handleRemoveMoveFromTeam = (pokemonIndex, moveIndex) => {
        const updated = { ...team[pokemonIndex] };
        if (updated.moves) {
            updated.moves = updated.moves.filter((_, idx) => idx !== moveIndex);
            if (onAddMove) onAddMove(updated);
            if (selectedTeamPokemon?.name === updated.name) {
                setSelectedTeamPokemon({ ...updated });
            }
        }
    };

    const dividirPorEstado = (estado) => team.filter((p) => p.estado === estado);

    const renderListado = (lista, estadoActual) => (
        <ul>
            {lista.map((pokemon) => {
                const realIndex = team.findIndex(p => p.nickname === pokemon.nickname && p.name === pokemon.name);
                return (
                    <li key={realIndex} style={{ display: 'flex', alignItems: 'center', marginBottom: '8px' }}>
                        <img src={pokemon.sprite} alt={pokemon.name} style={{ width: '48px', marginRight: '10px' }} />
                        <div style={{ flexGrow: 1 }} onClick={() => setSelectedTeamPokemon(pokemon)}>
                            <strong>{pokemon.nickname || pokemon.name}</strong>
                            <ul className="boxTipo" style={{ display: 'inline-block', marginLeft: '6px' }}>
                                {pokemon.types.map((type) => (
                                    <li key={type} className={`tipo ${type.toLowerCase()}`}>{type}</li>
                                ))}
                            </ul>
                        </div>
                        <div>
                            {estadoActual !== "activo" && (
                                <button className="btn" onClick={() => onChangeEstado(realIndex, "miEquipo", "activo")}>🟢 Activo</button>
                            )}
                            {estadoActual !== "caja" && (
                                <button className="btn" onClick={() => onChangeEstado(realIndex, "miEquipo", "caja")}>📦 Caja</button>
                            )}
                            <button className="btn" onClick={() => onRemovePokemon(realIndex)}>❌</button>
                            {estadoActual !== "cementerio" && (
                                <button className="btn" onClick={() => onChangeEstado(realIndex, "miEquipo", "cementerio")}>☠ Cementerio</button>
                            )}
                        </div>
                    </li>
                );
            })}
        </ul>
    );

    return (
        <div className="team-tracker">
            <h2 className="titulo bold">Team Tracker</h2>
            <button
                className="btn"
                onClick={() => setMostrarLista(prev => !prev)}
                style={{ marginBottom: '10px' }}
            >
                {mostrarLista ? 'Ocultar Lista' : 'Mostrar Lista'}
            </button>

            {mostrarLista && (
                <div className="leyenda-estado" style={{ marginBottom: '10px', fontWeight: 'bold' }}>
                    <span style={{ color: '#2ecc71' }}>🟢 Activo</span> |{" "}
                    <span style={{ color: '#3498db' }}>📦 Caja</span> |{" "}
                    <span style={{ color: '#e74c3c' }}>☠ Cementerio</span>
                </div>)}

            {mostrarLista && (
                <>
                    <h3>Equipo Activo</h3>
                    {renderListado(dividirPorEstado("activo"), "activo")}

                    <h3>Caja</h3>
                    {renderListado(dividirPorEstado("caja"), "caja")}

                    <h3>Cementerio</h3>
                    {renderListado(dividirPorEstado("cementerio"), "cementerio")}
                </>
            )}


            <div className="team-summary">
                <h3 className="titulo bold">Resumen de debilidades (x2) por Pokémon:</h3>
                <div className="summary-columns" style={{ display: 'flex' }}>
                    {dividirPorEstado("activo").map((pokemon, index) => (
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
                                                    className={`tipo ${move.type.toLowerCase()}`}
                                                    style={{
                                                        width: '100px',
                                                        display: 'block',
                                                        textAlign: 'center',
                                                    }}
                                                >
                                                    {move.name}
                                                </span>
                                                <button
                                                    className="btn tin"
                                                    onClick={() => handleRemoveMoveFromTeam(team.indexOf(pokemon), idx)}
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


            {selectedTeamPokemon && (
                <div className="pokemon-details" style={{ marginTop: '20px' }}>
                    <h3>Detalles de {selectedTeamPokemon.name}</h3>
                    <img src={selectedTeamPokemon.sprite} alt={selectedTeamPokemon.name} width="96" />
                    <p><strong>Tipos:</strong></p>
                    <ul className="boxTipo">
                        {selectedTeamPokemon.types.map((type) => (
                            <li key={type} className={`tipo ${type.toLowerCase()}`}>{type}</li>
                        ))}
                    </ul>

                    <p><strong>Debilidades (x2):</strong></p>
                    <ul style={{ listStyle: 'none', padding: 0 }}>
                        {getX2Weaknesses(selectedTeamPokemon).length > 0 ? (
                            getX2Weaknesses(selectedTeamPokemon).map((w, i) => (
                                <li key={i} className={`tipo ${w}`}>{w}</li>
                            ))
                        ) : (
                            <li>No x2 Weakness</li>
                        )}
                    </ul>

                    <button className="btn" onClick={() => setShowMovesDetails(!showMovesDetails)} style={{ marginTop: '10px' }}>
                        {showMovesDetails ? 'Ocultar Movimientos' : 'Mostrar Movimientos'}
                    </button>

                    {showMovesDetails && (
                        <div style={{ marginTop: '20px' }}>
                            <h4>Movimientos Asignados:</h4>
                            {selectedTeamPokemon.moves?.length > 0 ? (
                                <ul>
                                    {selectedTeamPokemon.moves.map((move, i) => (
                                        <li key={i} style={{ border: '1px solid #aaa', margin: '4px', padding: '4px' }}>
                                            <strong>{move.name}</strong><br />
                                            Tipo: <span className={`tipo ${move.type.toLowerCase()}`}>{move.type}</span> | Clase: <span className={`tipo ${move.damageClass.toLowerCase()}`}>{move.damageClass}</span><br />
                                            Daño: {move.power ?? 'N/A'} | Precisión: {move.accuracy ?? 'N/A'}<br />
                                            Descripción: {move.description ?? 'N/A'}<br />
                                            <button
                                                className="btn tin"
                                                onClick={() => handleRemoveMoveFromTeam(team.indexOf(selectedTeamPokemon), i)}
                                                style={{ marginTop: '4px' }}
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
                                <Select options={moveOptions} onChange={handleMoveSelect} placeholder="Buscar movimiento..." />
                            ) : (
                                <button className="btn" onClick={() => setShowMoveSelector(true)}>Agregar Movimiento</button>
                            )}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};

export default TeamTracker;
