// Header.js
import React from 'react';
import './Components/Header.css';

const Header = ({ activeTab, setActiveTab }) => {
  return (
    <header>
      <button
        className="btn"
        onClick={() => setActiveTab("agregar")}
        style={{ marginRight: '10px', fontWeight: activeTab === "agregar" ? 'bold' : 'normal' }}
      >
        Agregar Pokémon
      </button>
      <button
        className="btn"
        onClick={() => setActiveTab("equipo")}
        style={{ marginRight: '10px', fontWeight: activeTab === "equipo" ? 'bold' : 'normal' }}
      >
        Ver Equipo
      </button>
      <button
        className="btn"
        onClick={() => setActiveTab("importar")}
        style={{ fontWeight: activeTab === "importar" ? 'bold' : 'normal' }}
      >
        Importar TXT
      </button>
      <button
        className="btn"
        onClick={() => setActiveTab("generacion")}
        style={{ fontWeight: activeTab === "generacion" ? 'bold' : 'normal' }}
      >
        Generar txt
      </button>

    </header>
  );
};

export default Header;
