import React, { useState, useEffect } from 'react';
import Select from 'react-select';
import {
  getAllPokemonMoves,
  getAttackTypeByName,
  getAttackEffectiveAgainst,
} from './Services/API';
import './Components/Ataques.css'
import './Components/tipos.css'

function SeleccionarAtaque() {
  const [attackType, setAttackType] = useState([]);
  const [effectiveAttack, setEfectiveAttack] = useState([]);
  const [selectedMove, setSelectedMove] = useState([null]);
  const [allPokemonMoves, setAllPokemonMoves] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');

  useEffect(() => {
    const fetchPokemonData = async () => {
      try {

        const moves = await getAllPokemonMoves();
        setAllPokemonMoves(moves);

      } catch (error) {
        console.error('Error fetching Pokemon data:', error);
      }
    };

    fetchPokemonData();
  }, []);

  const handleMoveSelect = async (moveOption) => {
    try {
      console.log(moveOption)
      const types = await getAttackTypeByName(moveOption.label);
      const weaknesses = await getAttackEffectiveAgainst(moveOption.label);
      console.log(types)
      console.log(weaknesses)


      setAttackType(types);
      setEfectiveAttack(weaknesses);
      setSelectedMove(moveOption);



    } catch (error) {
      console.error('Error fetching Pokemon type or weaknesses:', error);
    }
  };

  const handleInputChange = (newValue) => {
    setSearchTerm(newValue);
  };
  const moveOptions = allPokemonMoves.map((pokemonMove) => ({
    value: pokemonMove,
    label: pokemonMove,
  }))
  return (
    <div>
        <h2 className='titulo'>Search Move:</h2>
        <Select
          className='Seleccionar'
          options={moveOptions}
          onInputChange={handleInputChange}
          onChange={handleMoveSelect}
          value={selectedMove}
        />
        {selectedMove && effectiveAttack && Object.keys(effectiveAttack).length > 0 && (
  <div>
    <p className='texto'>Type of Move {selectedMove.label}:</p>
    <ul>
      <div>
        <ul className='BoxTiposAttack'>
          <p className={`tipo ${attackType}`}>{attackType}</p>
        </ul>
        <div className='clearfix'></div>
      </div>
    </ul>
    <p className='texto'>Effective Against Types:</p>
    <ul>
      {Object.entries(effectiveAttack).map(([effect, types]) => (
        types.length > 0 && (
          <div key={effect}>
            <ul className='BoxTiposAttack'>
              {types.map((type) => (
                <li key={type} className={(effect === "noDamageTo" ? "tipo none" : effect === "halfDamageTo" ? "tipo half" : `tipo ${type}`)}>
                  {type}
                </li>
              ))}
            </ul>
          </div>
        )
      ))}
    </ul>
  </div>
)}

      </div>
  );
}
export default SeleccionarAtaque