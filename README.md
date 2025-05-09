# 🕹️ NuzTracker

**NuzTracker** es una aplicación web interactiva para gestionar equipos de Pokémon en desafíos tipo *Nuzlocke*. Permite añadir, editar y visualizar Pokémon con sus habilidades, tipos, debilidades, movimientos y estados (activo, caja o cementerio). También ofrece valoración estratégica del equipo, bitácora de progreso, e importación/exportación desde archivos `.txt` estilo Showdown.

---

## 🚀 Funcionalidades principales

- ✅ **Gestión de equipo**: añade Pokémon con sus movimientos, habilidades y nivel.
- 🔄 **Cambio de estado**: marca un Pokémon como activo, en la caja o fallecido.
- 📊 **Valoración del equipo**: cobertura ofensiva, debilidades, STAB, resistencias e inmunidades.
- 📘 **Bitácora de aventura**: marca medallas, miembros del Alto Mando derrotados y rutas de captura por juego.
- 📥 **Importación desde Showdown.txt**: analiza y convierte archivos `.txt` al equipo actual.
- 📤 **Exportación a Showdown.txt**: genera archivos `.txt` del equipo actual.
- 💾 **Guardado automático en localStorage**: persistencia entre sesiones.
- 🌐 **Integración con PokéAPI**: para obtener sprites, tipos, habilidades, debilidades y movimientos.

---

## 🖥️ Tecnologías utilizadas

- ⚛️ **React** (con `useState`, `useEffect`)
- 🖌️ **CSS modularizado** para estilos por componente
- 🔧 **React Select** para campos de selección dinámica
- 📦 **PokéAPI** para datos en tiempo real

---

## 📦 Instalación

```bash
git clone https://github.com/tu-usuario/nuztracker.git
cd nuztracker
npm install
npm start
```

---

## 📁 Estructura del proyecto

```
src/
├── Components/
│   ├── TeamTracker.js
│   ├── Valoracion.js
│   ├── BitacoraAventura.js
│   ├── PokemonModal.js
│   ├── ImportarTxt.js
│   ├── GenerarTxt.js
│   ├── Header.js
│   └── styles (TeamTracker.css, Bitacora.css, etc.)
├── Services/
│   └── API.js
├── App.js
├── index.js
└── README.md
```

---

## 📄 Formato del archivo TXT (Showdown)

**Importa/Exporta archivos `.txt`** siguiendo el formato de Pokémon Showdown. Cada Pokémon debe estar separado por una línea vacía y debe incluir datos como:

```
Apodo (Pikachu) (M) @ Light Ball
Ability: Static
Level: 50
Happiness: 255
EVs: 252 Atk / 4 Def / 252 Spe
Jolly Nature
IVs: 31 HP / 31 Atk / 31 Def / 31 SpA / 31 SpD / 31 Spe
- Thunderbolt
- Iron Tail
- Quick Attack
- Volt Tackle
```

---

## 📝 Créditos

- Desarrollado por [joanjuz]
- Datos y recursos provienen de [https://pokeapi.co](https://pokeapi.co)
- Inspirado en los desafíos Nuzlocke

---
