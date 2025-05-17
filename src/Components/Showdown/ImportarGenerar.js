import React from 'react';
import ImportarTxt from './ImportarTxt';
import GenerarTxt from './GenerarTxt';
import './ImportarGenerar.css';

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
