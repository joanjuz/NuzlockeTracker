# Partidas independientes

El selector **Partida**, en la barra superior, permite abrir una partida guardada. **Nueva** pide un nombre y crea una partida vacía: no copia el equipo de la anterior.

Cada partida tiene su propio equipo, cajas leídas, rutas, muertes, plantillas pk3DS, conexión guardada, configuración de OBS y datos de compañero. El tracker conserva las partidas anteriores como **Partida principal** y **Segundo jugador**, en sus carpetas originales. No cambia archivos de la ROM ni partidas del emulador.

Antes de conectar otra partida del emulador, selecciona su perfil en el tracker. Un cambio de juego en el selector de conexión no crea una partida nueva.

Cambiar de partida cierra los trabajadores y la conexión de la anterior antes de abrir la seleccionada. La ventana se actualiza y mantiene su dirección local para OBS. Los ajustes de OBS que aparecen pertenecen a la partida seleccionada. Una conexión Soul Link directa se cierra al cambiar; hay que volver a conectarla desde la nueva partida.

Pueden abrirse dos ventanas con fuentes OBS independientes. Una misma partida no puede estar abierta en ambas. Las carpetas y los nombres se guardan entre sesiones; al iniciar se abre una de las dos partidas originales disponibles y puedes seleccionar cualquier otra guardada.

Los nombres nuevos se guardan en `runtime/profiles/run-…/run-profile.json`; los demás archivos de esa partida viven en la misma carpeta. El perfil principal continúa en `runtime/` y el segundo en `runtime/profiles/segundo-jugador/`. No compartas estas carpetas públicamente: pueden contener credenciales del compañero.


## Eliminar una partida

**Eliminar…** abre la lista de partidas guardadas. Selecciona una partida que no esté abierta y pulsa **Eliminar partida**. Se eliminan únicamente sus datos del tracker: equipo y cajas guardados, rutas, historial, muertes, plantillas, ajustes OBS y credenciales propias de Soul Link. Las ROM y los guardados del emulador se conservan.

Para eliminar la partida actual, abre otra primero. Si otra ventana está usando la partida elegida, ciérrala o cambia su selección antes de borrarla. La partida principal se conserva porque su carpeta también contiene datos compartidos. El segundo jugador sí se puede eliminar y no reaparece automáticamente; puedes crear otra partida para usarla en una segunda ventana.
