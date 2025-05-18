# NuzTracker

**NuzTracker** es una aplicación web interactiva para organizar y llevar el control de tu equipo Pokémon, útil especialmente para retos como Nuzlocke. Permite importar equipos desde archivos TXT, personalizar cada Pokémon, registrar rutas de captura, y gestionar evoluciones.

---

## 🧩 Funcionalidades principales

### 1. **Gestión del equipo**
- Agrega Pokémon personalizados con apodo, habilidad, tipos, etc.
- Visualización clara del equipo activo.
- División del equipo en:
  - **Activos**
  - **Caja**
  - **Muertos**
- Cambia el estado de un Pokémon (activo, caja o muerto).
- Elimina Pokémon si lo deseas.

### 2. **Movimientos**
- Asigna movimientos personalizados a cada Pokémon.
- Visualiza su tipo y daño.
- Elimina movimientos con facilidad.

### 3. **Importar desde Showdown (TXT)**
- Carga un archivo `.txt` en formato de exportación de Pokémon Showdown.
- Los Pokémon se cargarán automáticamente con sus datos y movimientos.
- Se realiza una actualización automática de tipos y debilidades usando la PokéAPI.

### 4. **Generar archivo Showdown**
- Genera y descarga el archivo `.txt` de tu equipo actual en formato Showdown compatible.

### 5. **Bitácora de aventura**
- Marca las medallas obtenidas y miembros del Alto Mando vencidos.
- Registra qué rutas ya han sido usadas para capturar Pokémon.

### 6. **Sistema de evolución**
- Se muestra la evolución siguiente (si existe) del Pokémon activo.
- Aparece el botón **Evolucionar** si se cumplen las condiciones.
- Se indican los requisitos para evolucionar: nivel, ítem, etc.
- Al evolucionar, el Pokémon se reemplaza automáticamente por su forma evolucionada con datos actualizados.

---

## 🛠️ Tecnologías utilizadas
- **React** + Hooks
- **PokéAPI REST** para obtener información de Pokémon
- **React Select** para campos desplegables mejorados
- **CSS personalizado** para interfaz tipo Pokédex

---

## 📦 Instalación y ejecución local

```bash
git clone https://github.com/tu-usuario/nuztracker.git
cd nuztracker
npm install
npm start
```

---

## 🚧 Pendiente / Futuras mejoras
- Soporte para múltiples versiones de evolución.
- Control de niveles y experiencia.
---

## 🧠 Autor
Desarrollado por joanjuz.