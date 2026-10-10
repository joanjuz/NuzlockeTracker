# Compatibilidad experimental: Pokémon X/Y y ORAS (Gen6)

**Fase 2 experimental: equipo validado por el usuario en los cuatro juegos; cajas y PS en combate pendientes de validación real.**

## Juegos
- Pokémon X 1.0 y Pokémon Y 1.0: candidato de equipo `0x08CE1CE8`.
- Pokémon Omega Ruby 1.0 y Pokémon Alpha Sapphire 1.0: candidato `0x08CF727C`.
- Fuente de candidatos y envoltorio PK6: `kcblack42/Citra-Tracker-v2`, `citra-updater.py`, `getaddresses()` y constantes `SLOT_OFFSET=484`, `SLOT_DATA_SIZE=232`, `STAT_DATA_OFFSET=112`, `STAT_DATA_SIZE=22`.

Las direcciones son **candidatas históricas de Citra**; NO equivalen a direcciones confirmadas en Lime3DS/Azahar, versiones modificadas o ROMs parcheadas. El conector de Windows busca la memoria de invitado mediante referencias de 32 bits y **valida** un PK6 completo con checksum antes de exponer datos. GDB intenta leer la dirección candidata suministrada por el perfil. Sin un equipo válido, NO se declara conectada la sesión.

## Implementado en esta fase

- Cuatro opciones de juego en Conexión y perfiles de aventura por juego, sin mezclar progreso Gen6 con USUM.
- Descifrado de PK6 con la rutina común de 232 bytes, comprobación de checksum, límite de 721 especies, estado del equipo y estadísticas del bloque correspondiente si es válido.
- Nombres localizados de procedencia Gen6 (Kalos/Hoenn) por IDs PKHeX, sin inferir especies ni rutas a partir de un randomizer.
- Descubrimiento experimental de RAM Windows para la región de invitado `0x08000000..0x0FFFFFFF`, separado de Gen7.
- **Cajas PK6 (experimental):** direcciones candidatas `0x08C861C8` (X/Y) y `0x08C9E134` (ORAS), según `Sources/PKHeX.cpp` de `samabr85/Gen6CTRPFrameworkOverhauled` (`DetermineSpeciesPointer()`). Gen6 emplea 31 cajas de 30 espacios. Se lee cada caja dos veces; no se publica ninguna hasta comprobar las 31 lecturas con checksum válido y al menos un Pokémon presente. Un PC totalmente vacío o una lectura inestable se reportan como **no verificables**.
- **PS durante combate (experimental):** estructura candidata a partir de `Citra-Tracker-v2/getaddresses()` y lectura Gen6 `hpnum` (stride 580). Solo se aceptan PS cuando coinciden equipo PK6, identidad EC, especie, nivel, habilidad, PS máximos y dos lecturas consecutivas; en caso contrario, se conservan los PS del equipo fuera de combate.
- Diagnóstico exportable sin volcado de memoria, PIN, token o lista de Pokémon.

## Pendiente y expresamente deshabilitado

- **Cajas:** direcciones candidatas aún requieren validación en los cuatro juegos y emuladores. Gen6 usa 31 cajas, no 32.
- **PS en combate:** los candidatos pueden no coincidir según juego/versión, y quedan por validar contra cambios de daño en batalla real. Se descartan valores sospechosos.
- **Catálogo completo de rutas Nuzlocke X/Y/Hoenn:** se muestran lugares registrados del equipo y cajas si se verifican como «Otros orígenes»; no se inventan contadores ni marcas MISS para zonas no verificadas.
- **Análisis y evoluciones:** utilizan referencias generales existentes, con posibles diferencias entre generaciones; se muestran como aproximación, no como análisis Gen6 verificado.
- **Soul Link entre generaciones:** requiere comprobaciones de localizaciones y emparejamientos Gen6 antes de considerarse compatible.

## Cómo ayudarnos a verificarlo

1. Mantén instalada la versión estable de USUM. Descomprime el ZIP de prueba en otra carpeta.
2. Abre una partida **1.0** de X o Y, u Omega Ruby/Alpha Sapphire, en Citra/Azahar/Lime3DS, preferiblemente con uno o más Pokémon en el equipo.
3. En Pokémon Tracker, Conexión → elige el título correspondiente → Memoria Windows y, si aparecen dos emuladores, indica PID.
4. En **Cajas**, pulsa el botón **Actualizar todas las cajas** (la casilla «Mostrar todas las cajas leídas» solo es un filtro). Espera el escaneo **31/31**. Con un Pokémon depositado, verifica la aparición del PC; si falla, **Guardar diagnóstico…** permitirá ver bases candidatas y primera caja rechazada sin copiar PK6 ni guardados.
5. Durante una batalla real, recibe daño y comprueba que los PS cambian **antes de salir**. Sin salir del combate, pulsa **Guardar diagnóstico…**: ahora registra si los candidatos de batalla fallan por lectura, identidad del equipo o validación de PS. Al salir del combate, vuelve a comprobar la lectura.
6. Si sigue apareciendo «Cajas no verificadas», adjunta ese nuevo diagnóstico e indica en qué caja tienes un Pokémon y dónde estaba durante la captura. Para Gen6 en Lime3DS se añade una segunda base candidata con el desplazamiento de RAM encontrado en el equipo.

**No fusionar con master hasta que se pruebe en juegos reales.**

## Diagnóstico Lime3DS Pokémon X — segunda captura

En el diagnóstico de 2026-10-09 a las 22:10 (Costa Rica) el equipo se detecta en `0x08CE1C68`, pero ambas direcciones de cajas (`0x08C861C8` y `0x08C86148`) fallan desde la primera casilla con errores de estructura/checksum. Ninguna se acepta como válida.

- Si el escaneo normal no valida ninguna base, se busca **solo una vez** un encabezado PK6 almacenado válido en la zona de ±512 KiB de la base candidata, en lecturas de máximo 64 KiB; se descartan estructuras corruptas por checksum.
- Para aceptar una base de memoria, las 31 cajas deben validarse, repetirse las lecturas y existir **una única** alineación candidata. Si hay más de una válida, ninguna se aplica automáticamente.
- `gen6_box_search` en el JSON registra bytes revisados, número de PK6 válidos, direcciones candidatas y motivos de ambigüedad. No exporta datos Pokémon, guardados ni memoria cruda.
- **Prueba importante:** antes de pulsar «Actualizar todas las cajas», coloca un Pokémon en **Caja 1 → casilla 1**. Esto permite comprobar que el primer PK6 válido corresponde al inicio real del almacenamiento.
- **Corrección batalla Gen6:** el código de Citra-Tracker-v2 `read_party()` comienza directamente por los 232 bytes PK6 y lee estadísticas a +344 dentro de cada bloque de 484; **no** incluye el encabezado de 128 bytes de los datos de equipo normal. El lector de combate ahora adapta este formato correctamente. Todavía falta validar el descenso de PS durante una batalla real en Lime3DS.
- Si durante combate sigue mostrando `battle_roster_unavailable`, guardar diagnóstico **durante el combate** para diferenciar estado no activo y dirección incorrecta.

## Recuperación del equipo — diagnóstico 22:23 en Lime3DS

El tercer diagnóstico de Pokémon X encontró **0 equipos válidos** antes de alcanzar un límite de 90 segundos, después de buscar en más de 800 MiB de memoria. La versión anterior sí había validado entre 4 y 6 Pokémon con el mismo emulador, por lo que no se considera un error de la partida ni evidencia de fallo de PK6.

- La conexión de Gen6 primero prueba de forma **acotada** la localización conocida del equipo X/Y o ORAS dentro de las regiones grandes de RAM. Considera la dirección normal y variantes desplazadas ±128 bytes; solo acepta checksum PK6 válido y dos lecturas idénticas. Si no encuentra un equipo, ejecuta el descubrimiento anterior como respaldo.
- El escaneo de 31 cajas Gen6 **ya no se ejecuta automáticamente al conectar**, para evitar que una búsqueda de memoria experimental bloquee la detección del equipo. Debe iniciarse con **Cajas → Actualizar todas las cajas**.
- Después de un escaneo válido de cajas, la actualización periódica continúa. Si una búsqueda no consigue verificar cajas, no se repite sola cada tres minutos.
- Durante la primera conexión conviene estar en el mundo del juego (fuera del PC y del combate), con al menos un Pokémon en el equipo. Las funciones X/Y y ORAS de cajas/PS siguen **sin validar en pruebas reales**, no fusionar con master.

## Captura real de Pokémon X en Lime3DS — 10 de octubre de 2026

Los dos archivos `diagnostico_gen6_20261010_044658.json` y `diagnostico_gen6_20261010_044809.json` entregados por el usuario muestran:

- Primera ejecución: **captura interrumpida** sin datos de equipo; no prueba fallo de memoria.
- Segunda ejecución: **31 cajas verificadas** a partir de la base `0x08C861B8` en Pokémon X 1.0. Una copia `0x08C79DA8` falla estructura en la casilla 2 y se rechaza.
- Equipo X localizado en `0x08CE1C68` mediante búsqueda dinámica; es 128 bytes antes de la referencia histórica, pero **el desplazamiento de cajas es de 16 bytes**, no 128.
- Estructura PK6 de combate: `0x08804A70`, validada por identidad del roster en las tres muestras.
- Lectura diferencial de **PS actuales en combate**: `0x08203ED8` entre las cuatro direcciones supervivientes a `16 → 8 → 9`. Coincide exactamente con la lectura de HP del candidato de batalla `0x08203FE0 - 264` del tracker.
- **Corrección en Gen6:** conservar último equipo validado como apoyo cuando la copia del overworld se vuelve ilegible o se reordena durante combate; aceptar PS solo cuando el roster y estadísticas vuelven a validar.
- **Pendiente:** el usuario observa que la búsqueda inicial de equipo Gen6 en Lime3DS requiere a veces reiniciar el juego. En la segunda captura hubo un hallazgo exitoso en 8.37 s, pero el sondeo rápido falló en 59 regiones y 3540 posiciones; la búsqueda dinámica funcionó. Una captura anterior agotó 90 s. No existe todavía causa demostrada ni garantía de conexión en caliente.
- Los offsets anteriores son específicos de **la instalación de Pokémon X 1.0 en Lime3DS probada**, y no se consideran automáticamente comprobados para Y/ORAS ni otros emuladores.

La rama sigue siendo **experimental**; no fusionar con `master` antes de validar la nueva versión ejecutable en el juego real.
