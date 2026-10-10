# Rutas de Kalos y Hoenn — Pokémon X/Y y ORAS

Los perfiles de **Pokémon X / Y** usan el mismo catálogo de **80 zonas de Kalos**; **Omega Ruby / Alpha Sapphire**, **92 zonas de Hoenn**. Son archivos diferentes (`data/Routes_XY.json` y `data/Routes_ORAS.json`), con nombres e identificadores PK6 sacados de los recursos españoles de ubicaciones de PKHeX incluidos en `data/Locations6_0.txt`.

Los catálogos abarcan:
- Kalos: rutas **1–22**, localidades, cuevas, bosques, instalaciones y zonas opcionales, en un orden editorial aproximado de progresión.
- Hoenn: rutas **101–134**, ciudades, cuevas, bosques, zonas acuáticas, edificios y ubicaciones opcionales, en un orden editorial aproximado.
- Los ID de ubicación son los datos de captura registrados por el juego; **no se deduce especie, encuentro garantizado, fósil, regalo o intercambio** a partir del nombre de una ubicación.
- Las ubicaciones especiales de la tabla de PKHeX que no corresponden a una zona de aventura se muestran en **«Otros orígenes registrados»** si hay un Pokémon que las utiliza.
- El orden editorial no representa la única ruta jugable y algunas zonas comparten ID de captura. Cada tarjeta corresponde a un ID explícito, sin inventar encuentros.

El sistema reutiliza la misma interfaz de **USUM**: un recuadro por zona con el nombre en el borde, sprites juntos y sin motes visibles, estado MISS reversible, botón «Intercambiado» para rutas vacías, acciones Muerte/Fósil/Deshacer, agrupación por origen en Fósiles/Regalos/Huevos/Intercambios, historial tras salir del equipo o cajas, y lectura de solo consulta del compañero donde corresponda.

Los Pokémon de X/Y se clasifican mediante **origin_version 24/25**, los de ORAS **26/27** y los de USUM **30–33**. Transferidos de otro juego aparecen en «Otros orígenes registrados» cuando su origen no pertenece a la región seleccionada. El progreso de cada versión usa un archivo local separado.

## Cajas automáticas

El botón manual «Actualizar todas las cajas» se elimina de la interfaz. Se inicia el escaneo completo **al conectar una partida con equipo PK6 válido** y se repite cada **180 segundos** mientras la conexión está operativa. Se muestran progreso y estado, y se conserva la opción de cancelar un recorrido en curso. Gen6 requiere exactamente **31 cajas**, USUM mantiene sus **32**.

El detector conservador de intercambios automáticos compara **dos lecturas completas y verificadas** del PC y equipo, igual que USUM. No infiere intercambio por la desaparición temporal de un Pokémon de una caja. Se requiere que salga uno del entrenador y llegue uno de otro OT, con suficiente historial del dueño. El botón manual «Intercambiado» sigue siendo la alternativa.

## Comprobaciones antes de fusionar

- La compatibilidad práctica de equipo, PC y PS en batalla de **X, Y, Omega Ruby y Alpha Sapphire** fue confirmada por el usuario en Lime3DS.
- Las listas de ubicaciones y las anotaciones de aventura todavía se deben comprobar visualmente con partidas reales para confirmar la presentación, orden y todos los casos especiales.
- La reconexión en caliente de Gen6 (sin reiniciar el juego en Lime3DS) sigue siendo un problema separado; todavía no se afirma resuelto.
- El PR #14 permanece en borrador hasta validar que la actualización automática y las nuevas rutas funcionan en todos los juegos.
