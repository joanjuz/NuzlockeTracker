import React from 'react';
import './Header.css';

const tabs = [
  { id: 'agregar', label: 'Agregar' },
  { id: 'equipo', label: 'Ver Equipo' },
  { id: 'caja', label: 'Caja' },
  { id: 'valoracion', label: 'Valoración' },
  { id: 'bitacora', label: 'Bitácora' },
  { id: 'archivo', label: 'Showdown' },
];

const Header = ({ activeTab, setActiveTab }) => {
  return (
    <header className="main-header">
      {tabs.map(({ id, label }) => (
        <button
          key={id}
          className={`tab-btn ${activeTab === id ? 'active' : ''}`}
          onClick={() => setActiveTab(id)}
        >
          {label}
        </button>
      ))}
    </header>
  );
};

export default Header;
