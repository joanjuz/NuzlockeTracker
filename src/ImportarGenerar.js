// ImportarGenerar.js
import React from 'react';
import './Components/ImportarGenerar.css';
import ImportarTxt from './ImportarTxt';
import GenerarTxt from './GenerarTxt';

const ImportarGenerar = ({ team, onImportPokemons }) => {
  return (
    <div className="importar-generar-wrapper">
      <div className="importar-section">
        <h2 className="titulo bold">Importar TXT</h2>
        <ImportarTxt onImportPokemons={onImportPokemons} />
      </div>

      <div className="generar-section">
        <h2 className="titulo bold">Generar TXT</h2>
        <GenerarTxt team={team} showPreview={false} />
      </div>
    </div>
  );
};

export default ImportarGenerar;
