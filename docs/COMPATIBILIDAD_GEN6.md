# Compatibilidad experimental: Pokémon X/Y y ORAS (Gen6)

**Fase 1: lectura del equipo y diagnóstico. No es soporte completo ni validado en hardware real.**

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
- Diagnóstico exportable sin volcado de memoria, PIN, token o lista de Pokémon.

## Pendiente y expresamente deshabilitado

- **Cajas y escaneo 32 cajas:** desconocemos la dirección PC válida para Gen6. No se reutiliza jamás `0x33015AB0` de USUM.
- **PS durante combate:** direcciones y estructuras todavía no validadas; se mantienen datos del equipo fuera de combate.
- **Catálogo completo de rutas Nuzlocke X/Y/Hoenn:** actualmente se muestran los lugares registrados del equipo como «Otros orígenes», pero no se inventan contadores ni marcas MISS para zonas no verificadas.
- **Análisis y evoluciones:** utilizan referencias generales existentes, con posibles diferencias entre generaciones; se muestran como aproximación, no como análisis Gen6 verificado.
- **Soul Link entre generaciones:** requiere comprobaciones de localizaciones y emparejamientos Gen6 antes de considerarse compatible.

## Cómo ayudarnos a verificarlo

1. Mantén instalada la versión estable de USUM. Descomprime el ZIP de prueba en otra carpeta.
2. Abre una partida **1.0** de X o Y, u Omega Ruby/Alpha Sapphire, en Citra/Azahar/Lime3DS, preferiblemente con uno o más Pokémon en el equipo.
3. En Pokémon Tracker, Conexión → elige el título correspondiente → Memoria Windows y, si aparecen dos emuladores, indica PID.
4. Espera la detección. Si no funciona, usa **Guardar diagnóstico…** y comparte el JSON; no necesitas compartir ROM, guardado, credenciales ni memoria cruda.
5. Si funciona, comprueba seis slots, nivel, PS, especie, mote, datos de captura y que el juego siga funcionando al salir de combate. Repite con el otro juego y el mismo emulador.
6. Para validar **cajas** en una fase posterior harán falta capturas de diagnóstico más específicas, siempre solo datos necesarios y con permiso del usuario.

**No fusionar con master hasta que se pruebe en juegos reales.**
