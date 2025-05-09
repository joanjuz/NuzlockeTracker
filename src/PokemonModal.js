// PokemonModal.js
import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './Components/PokemonModal.css';
import Select from 'react-select';

const PokemonModal = ({ pokemon, onSave, onClose }) => {
  const [nickname, setNickname] = useState('');
  const [level, setLevel] = useState('');
  const [ability, setAbility] = useState('');
  const [abilityOptions, setAbilityOptions] = useState([]);

  useEffect(() => {
    const fetchAbilities = async () => {
      try {
        const response = await axios.get('https://pokeapi.co/api/v2/ability/?limit=100000');
        const options = response.data.results.map(ab => ab.name).sort();
        setAbilityOptions(options);
      } catch (error) {
        console.error('Error fetching abilities:', error);
      }
    };

    fetchAbilities();
  }, []);

  const handleSubmit = (e) => {
    e.preventDefault();
    const finalNickname = nickname.trim() !== '' ? nickname.trim() : pokemon.name;

    const updatedPokemon = {
      ...pokemon,
      nickname: finalNickname,
      ability,
    };

    onSave(updatedPokemon);
  };

  const handleModalClose = () => {
    onClose();
  };

  return (
    <div
      className="modal-overlay"
      onClick={(e) => {
        if (e.target === e.currentTarget) {
          handleModalClose();
        }
      }}
    >
      <div className="modal-container" style={{ maxWidth: '400px' }}>
        <h2>Información del Pokémon</h2>
        <form onSubmit={handleSubmit} className="modal-form">
          <div className="form-group">
            <label>Apodo:</label>
            <input
              type="text"
              value={nickname}
              onChange={(e) => setNickname(e.target.value)}
              placeholder={pokemon.name}
            />
          </div>
          <div className="form-group">
            <label>Habilidad:</label>
            <Select
              options={abilityOptions.map(ab => ({ label: ab, value: ab }))}
              value={ability ? { label: ability, value: ability } : null}
              onChange={(selectedOption) =>
                setAbility(selectedOption ? selectedOption.value : '')
              }
              placeholder="Seleccione habilidad..."
              isClearable
            />
          </div>

          <div className="modal-actions">
            <button type="submit" className="btn">Guardar</button>
            <button type="button" className="btn" onClick={handleModalClose} style={{ marginLeft: '10px' }}>
              Cancelar
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default PokemonModal;
