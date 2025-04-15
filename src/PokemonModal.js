// PokemonModal.js
import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './Components/PokemonModal.css';
import Select from 'react-select';

import { getAllItems } from './Services/API';

const PokemonModal = ({ pokemon, onSave, onClose }) => {
    // Estados para el formulario
    const [nickname, setNickname] = useState("");
    const [gender, setGender] = useState("N/A");
    const [item, setItem] = useState("N/A");

    const [itemOptions, setItemOptions] = useState([]);
    const [level, setLevel] = useState("");

    // EVs
    const [ev_hp, setEvHp] = useState("");
    const [ev_atk, setEvAtk] = useState("");
    const [ev_def, setEvDef] = useState("");
    const [ev_spa, setEvSpa] = useState("");
    const [ev_spd, setEvSpd] = useState("");
    const [ev_spe, setEvSpe] = useState("");

    // IVs
    const [iv_hp, setIvHp] = useState("");
    const [iv_atk, setIvAtk] = useState("");
    const [iv_def, setIvDef] = useState("");
    const [iv_spa, setIvSpa] = useState("");
    const [iv_spd, setIvSpd] = useState("");
    const [iv_spe, setIvSpe] = useState("");

    // Naturaleza y Habilidad
    const [nature, setNature] = useState("");
    const [ability, setAbility] = useState("");
    const [abilityOptions, setAbilityOptions] = useState([]);

    // Efecto para cargar la lista de habilidades
    useEffect(() => {
        const fetchAbilities = async () => {
            try {
                const response = await axios.get('https://pokeapi.co/api/v2/ability/?limit=100000');
                // Mapeamos a los nombres y los ordenamos alfabéticamente
                const options = response.data.results.map(ab => ab.name).sort();
                setAbilityOptions(options);
            } catch (error) {
                console.error("Error fetching abilities:", error);
            }
        };

        fetchAbilities();
    }, []);
    // Carga la lista de items desde la API (por ejemplo, en un useEffect)
    useEffect(() => {
        const fetchItems = async () => {
            try {
                const items = await getAllItems();
                setItemOptions(items);
            } catch (error) {
                console.error("Error fetching items:", error);
            }
        };
        fetchItems();
    }, []);

    // Función para manejar el submit del formulario
    const handleSubmit = (e) => {
        e.preventDefault();
        // Si Apodo está vacío, usamos el nombre del Pokémon como apodo.
        const finalNickname = nickname.trim() !== "" ? nickname.trim() : pokemon.name;
        // Formateamos EVs e IVs en una cadena (por ejemplo "22 HP / 30 Atk / ...")
        const evs = `HP: ${ev_hp || "N/A"} / Atk: ${ev_atk || "N/A"} / Def: ${ev_def || "N/A"} / SpA: ${ev_spa || "N/A"} / SpD: ${ev_spd || "N/A"} / Spe: ${ev_spe || "N/A"}`;
        const ivs = `HP: ${iv_hp || "N/A"} / Atk: ${iv_atk || "N/A"} / Def: ${iv_def || "N/A"} / SpA: ${iv_spa || "N/A"} / SpD: ${iv_spd || "N/A"} / Spe: ${iv_spe || "N/A"}`;

        const updatedPokemon = {
            ...pokemon,
            nickname: finalNickname,
            gender: gender || "N/A",
            item: item || "N/A",
            level: level || "N/A",
            evs,
            ivs,
            nature: nature,  // Ej: "Docile" (se mostrará "Docile Nature" al generar el TXT si lo necesitas)
            ability,
        };
        onSave(updatedPokemon);
    };

    // Función para cerrar el modal
    const handleModalClose = () => {
        onClose();
    };
    return (
        <div
            className="modal-overlay"
            onClick={(e) => {
                // Si se hace click fuera del contenedor modal, cerrar el modal.
                if (e.target === e.currentTarget) {
                    handleModalClose();
                }
            }}
        >
            <div className="modal-container">
                <h2>Completa la información del Pokémon</h2>
                <form onSubmit={handleSubmit} className="modal-form">
                    <div className="form-group">
                        <label>Apodo:</label>
                        <input
                            type="text"
                            value={nickname}
                            onChange={(e) => setNickname(e.target.value)}
                            placeholder={pokemon.name} // Usar el nombre del Pokémon por defecto si no se ingresa nada
                        />
                    </div>
                    <div className="form-group">
                        <label>Género:</label>
                        <select
                            type="text"
                            value={gender}
                            onChange={(e) => setGender(e.target.value)}
                            placeholder="N/A"
                        >

                            <option value="">Seleccione Genero</option>
                            <option value="M">Masculino</option>
                            <option value="F">Femenino</option>
                        </select>
                    </div>
                    <div className="form-group">
                        <label>Item:</label>
                        <Select
                            options={itemOptions.map((item) => ({ label: item, value: item }))}
                            value={item ? { label: item, value: item } : null}
                            onChange={(selectedOption) => setItem(selectedOption ? selectedOption.value : "N/A")}
                            placeholder="Seleccione Item..."
                            isClearable
                        />
                    </div>
                    <div className="form-group">
                        <label>Nivel:</label>
                        <input
                            type="number"
                            value={level}
                            onChange={(e) => setLevel(e.target.value)}
                            placeholder="N/A"
                        />
                    </div>
                    <fieldset className="form-group">
                        <legend>EVs</legend>
                        <div className="ev-group">
                            <label>HP:</label>
                            <input
                                type="number"
                                value={ev_hp}
                                onChange={(e) => setEvHp(e.target.value)}
                                placeholder="N/A"
                            />
                            <label>Atk:</label>
                            <input
                                type="number"
                                value={ev_atk}
                                onChange={(e) => setEvAtk(e.target.value)}
                                placeholder="N/A"
                            />
                            <label>Def:</label>
                            <input
                                type="number"
                                value={ev_def}
                                onChange={(e) => setEvDef(e.target.value)}
                                placeholder="N/A"
                            />
                            <label>SpA:</label>
                            <input
                                type="number"
                                value={ev_spa}
                                onChange={(e) => setEvSpa(e.target.value)}
                                placeholder="N/A"
                            />
                            <label>SpD:</label>
                            <input
                                type="number"
                                value={ev_spd}
                                onChange={(e) => setEvSpd(e.target.value)}
                                placeholder="N/A"
                            />
                            <label>Spe:</label>
                            <input
                                type="number"
                                value={ev_spe}
                                onChange={(e) => setEvSpe(e.target.value)}
                                placeholder="N/A"
                            />
                        </div>
                    </fieldset>
                    <fieldset className="form-group">
                        <legend>IVs</legend>
                        <div className="iv-group">
                            <label>HP:</label>
                            <input
                                type="number"
                                value={iv_hp}
                                onChange={(e) => setIvHp(e.target.value)}
                                placeholder="N/A"
                            />
                            <label>Atk:</label>
                            <input
                                type="number"
                                value={iv_atk}
                                onChange={(e) => setIvAtk(e.target.value)}
                                placeholder="N/A"
                            />
                            <label>Def:</label>
                            <input
                                type="number"
                                value={iv_def}
                                onChange={(e) => setIvDef(e.target.value)}
                                placeholder="N/A"
                            />
                            <label>SpA:</label>
                            <input
                                type="number"
                                value={iv_spa}
                                onChange={(e) => setIvSpa(e.target.value)}
                                placeholder="N/A"
                            />
                            <label>SpD:</label>
                            <input
                                type="number"
                                value={iv_spd}
                                onChange={(e) => setIvSpd(e.target.value)}
                                placeholder="N/A"
                            />
                            <label>Spe:</label>
                            <input
                                type="number"
                                value={iv_spe}
                                onChange={(e) => setIvSpe(e.target.value)}
                                placeholder="N/A"
                            />
                        </div>
                    </fieldset>
                    <div className="form-group">
                        <label>Naturaleza:</label>
                        <select
                            value={nature}
                            onChange={(e) => setNature(e.target.value)}
                            style={{ maxHeight: '100px', overflowY: 'auto' }}
                        >
                            <option value="">Seleccione Naturaleza</option>
                            <option value="Docile">Docile</option>
                            <option value="Quirky">Quirky</option>
                            <option value="Timid">Timid</option>
                            <option value="Brave">Brave</option>
                            <option value="Mild">Mild</option>
                            <option value="Bold">Bold</option>
                            <option value="Relaxed">Relaxed</option>
                            <option value="Impish">Impish</option>
                            <option value="Lax">Lax</option>
                        </select>
                    </div>
                    <div className="form-group">
                        <label>Habilidad:</label>
                        <Select
                            options={abilityOptions.map((ab) => ({ label: ab, value: ab }))}
                            value={ability ? { label: ability, value: ability } : null}
                            onChange={(selectedOption) =>
                                setAbility(selectedOption ? selectedOption.value : "")
                            }
                            placeholder="Seleccione Habilidad..."
                            isClearable
                        />
                    </div>
                    <div className="modal-actions">
                        <button type="submit" className="btn">Guardar</button>
                        <button
                            type="button"
                            className="btn"
                            onClick={handleModalClose}
                            style={{ marginLeft: '10px' }}
                        >
                            Cancelar
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
};

export default PokemonModal;
