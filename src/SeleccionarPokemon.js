import React, { useState, useEffect } from 'react';
import Select from 'react-select';
import {
  getPokemonTypes,
  getPokemonNames,
  getPokemonTypeByName,
  getPokemonWeaknesses,
  getPokemonSprite,
} from './Services/API';
import './Components/Pokemon.css'
import './Components/tipos.css'

function SeleccionarPokemon({ onAddPokemon }) {
  const allPokemonTypes = {
    'normal': 0,
    'fire': 0,
    'water': 0,
    'electric': 0,
    'grass': 0,
    'ice': 0,
    'fighting': 0,
    'poison': 0,
    'ground': 0,
    'flying': 0,
    'psychic': 0,
    'bug': 0,
    'rock': 0,
    'ghost': 0,
    'dragon': 0,
    'dark': 0,
    'steel': 0,
    'fairy': 0,
  };
  const [pokemonTypeCounts, setPokemonTypeCounts] = useState(allPokemonTypes);
  const [pokemonTypes, setPokemonTypes] = useState([]);
  const [allPokemonNames, setAllPokemonNames] = useState([]);
  const [selectedPokemon, setSelectedPokemon] = useState(null);
  const [pokemonType, setPokemonType] = useState([]);
  const [pokemonWeaknesses, setPokemonWeaknesses] = useState([]);
  const [pokemonSprite, setPokemonSprite] = useState('');
  const [searchTerm, setSearchTerm] = useState('');


  useEffect(() => {
    const fetchPokemonData = async () => {
      try {
        const types = await getPokemonTypes();
        setPokemonTypes(types);

        const names = await getPokemonNames();
        setAllPokemonNames(names);

      } catch (error) {
        console.error('Error fetching Pokemon data:', error);
      }
    };

    fetchPokemonData();
  }, []);


  const handlePokemonSelect = async (pokemonOption) => {
    try {
      const types = await getPokemonTypeByName(pokemonOption.label);
      const weaknesses = await getPokemonWeaknesses(pokemonOption.label);
      const sprite = await getPokemonSprite(pokemonOption.label);

      setPokemonType(types);
      setPokemonWeaknesses(weaknesses);
      setPokemonSprite(sprite);
      setSelectedPokemon(pokemonOption);


      // Reiniciar contadores
      const updatedPokemonTypeCounts = { ...allPokemonTypes };

      weaknesses.forEach((weakness) => {
        const typeKey = Object.keys(weakness)[0];
        const doubleDamageFrom = weakness[typeKey].double_damage_from;
        const halfDamageFrom = weakness[typeKey].half_damage_from;
        const no_damage_from = weakness[typeKey].no_damage_from;

        doubleDamageFrom.forEach((type) => {
          updatedPokemonTypeCounts[type] += 1;
        });

        halfDamageFrom.forEach((type) => {
          updatedPokemonTypeCounts[type] -= 1;
        });
        no_damage_from.forEach((type) => {
          updatedPokemonTypeCounts[type] -= 5;
        });
      });
      console.log(updatedPokemonTypeCounts)

      setPokemonTypeCounts(updatedPokemonTypeCounts);
    } catch (error) {
      console.error('Error fetching Pokemon type or weaknesses:', error);
    }
  };

  const handleSearch = () => {
    setSelectedPokemon(null);

    const searchTermLowerCase = searchTerm.toLowerCase();
    const foundPokemon = allPokemonNames.find((pokemonName) =>
      pokemonName.toLowerCase().includes(searchTermLowerCase)
    );

    if (foundPokemon) {
      handlePokemonSelect({ value: foundPokemon, label: foundPokemon });
    } else {
      console.log('No se encontró ningún Pokémon con ese nombre.');
    }
  };

  const handleInputChange = (newValue) => {
    setSearchTerm(newValue);
  };

  const pokemonOptions = allPokemonNames.map((pokemonName) => ({
    value: pokemonName,
    label: pokemonName,
  }));

  return (
    <div>
      <h2 className='titulo'>Search Pokémon by Name:</h2>
      <Select
        className='Seleccionar'
        options={pokemonOptions}
        onInputChange={handleInputChange}
        onChange={handlePokemonSelect}
        value={selectedPokemon}
      />

      {selectedPokemon && (
        <div>
          <img className="sprite" src={pokemonSprite} alt={`Sprite of ${selectedPokemon.label}`} />
          <ul className='boxTipo'>
            {pokemonType.map((type) => (
              <li className={`tipo ${type.toLowerCase()}`} key={type}>{type}</li>
            ))}
          </ul>

          <p className='texto'>Debilidades:</p>
          {selectedPokemon && (
            <div>
              <ul>
                {pokemonWeaknesses.map((weakness) => (
                  <li key={Object.keys(weakness)[0]} >
                    <ul>
                      {weakness[Object.keys(weakness)[0]].double_damage_from.length > 0 && (
                        <li>
                          {weakness[Object.keys(weakness)[0]].double_damage_from
                            .filter((type) => pokemonTypeCounts[type] === 2)
                            .map((type) => (
                              <div className='boxWeak'>
                                <span className={`tipo ${type.toLowerCase()}`}>
                                  {pokemonTypeCounts[type] === 2 ? `4x ${type}` : pokemonTypeCounts[type] === 1 ? `2x ${type}` : ''}
                                </span>
                              </div>
                            ))}
                        </li>
                      )}
                      {weakness[Object.keys(weakness)[0]].double_damage_from.length > 0 && (
                        <li>
                          {weakness[Object.keys(weakness)[0]].double_damage_from
                            .filter((type) => pokemonTypeCounts[type] === 1)
                            .map((type) => (
                              <div className='boxWeak'>
                                <span className={`tipo ${type.toLowerCase()}`}>
                                  {pokemonTypeCounts[type] === 2 ? `4x ${type}` : pokemonTypeCounts[type] === 1 ? `2x ${type}` : ''}
                                </span>
                              </div>
                            ))}
                        </li>
                      )}

                      {weakness[Object.keys(weakness)[0]].half_damage_from.length > 0 && (
                        <li>
                          {weakness[Object.keys(weakness)[0]].half_damage_from
                            .filter((type) => pokemonTypeCounts[type] === -1 || pokemonTypeCounts[type] === -2)
                            .map((type) => (
                              <div className='boxWeak'>
                                <span className={`tipo ${type.toLowerCase()}`}>
                                  {pokemonTypeCounts[type] === -1 ? ` 1/2 ${type}` : pokemonTypeCounts[type] === -2 ? `1/4 ${type}` : ''}
                                </span>
                              </div>
                            ))}
                        </li>
                      )}

                      {weakness[Object.keys(weakness)[0]].no_damage_from.length > 0 && (
                        <li>
                          {weakness[Object.keys(weakness)[0]].no_damage_from
                            .map((type) => (
                              <div className='boxWeak'>
                                <span className={`tipo none`}>
                                  {type}
                                </span>
                              </div>
                            ))}
                        </li>
                      )}
                    </ul>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {/* Botón para agregar este Pokémon al equipo */}
            <button className="btn"
              onClick={() => {
                const nuevoPokemon = {
                  name: selectedPokemon.label,
                  sprite: pokemonSprite,
                  types: pokemonType,
                  weaknesses: pokemonWeaknesses,
                  // Puedes agregar más datos si lo deseas
                };
                onAddPokemon(nuevoPokemon);
              }}
            >
              Agregar al Equipo
            </button>
          </div>

      )}
    </div>
  );
}
export default SeleccionarPokemon;
