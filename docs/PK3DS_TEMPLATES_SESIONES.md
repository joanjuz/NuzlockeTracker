# Perfiles persistentes y plantillas pk3DS Progressive (v0.24 experimental)

Esta rama no modifica ROM, saves ni memoria del emulador. Actualiza los datos **informativos** del tracker usando archivos CSV aportados por el jugador. Cada instancia del tracker tiene sus propios datos en la carpeta runtime de su perfil.

## Recuperar sesión

- Al conectarse correctamente a Lime3DS, el tracker guarda en `runtime/session-profile.json` el juego, modo, puerto GDB y PID elegido (si se proporcionó).
- Al iniciar el servidor de nuevo, intenta restaurar la selección y conectarse automáticamente. Las credenciales y la última copia del compañero se conservan por separado en `companion-credentials.json` y `companion-cache.json`: **no se requiere crear una pareja nueva**.
- En **Conexión** aparece **Guardar sesión** para volver a grabar manualmente la configuración.
- Si dos Lime3DS están abiertos, y al cerrarlos cambia el PID de Windows, es posible que debas seleccionar el nuevo PID. No se cambia de emulador automáticamente para evitar leer una partida distinta.
- El perfil principal usa `Iniciar.bat`. El otro usa `Iniciar_Segundo_Jugador.bat`, con directorios aislados `runtime/profiles/segundo-jugador/`.

## Importar plantillas

En **Conexión → Plantillas pk3DS Progressive**, selecciona uno, dos o los tres archivos y pulsa **Importar plantillas seleccionadas**. Admite respaldos de movimiento llamados `.csv.bak_...`, pues se lee el contenido CSV independientemente del nombre.

- **Movimientos**: CSV con `Move, Type, Category, Power, Accuracy, PP, Priority`, etc. Ignora líneas de comentarios `#`, celdas vacías y propiedades no representadas. Las celdas vacías **mantienen la referencia original**. Para campos avanzados como `BattlePatch`, solo se muestra la información; no afirmamos que el parche esté instalado en la ROM.
- **Estadísticas base**: CSV con `Entry, Pokemon, HP, ATK, DEF, SPA, SPD, SPE`. Se usa el ID numérico si se incluye o se busca la especie por su nombre si Entry está vacío. Aparece una sección separada de estadísticas base dentro de la ficha. Los PS actuales y los IV/EV siguen viniendo de la memoria del emulador.
- **Evoluciones**: CSV con `Source, Target, Method, Level, Argument, Form` y opcionalmente `ItemName, AltItemName`. Sustituye únicamente las evoluciones **source→target** indicadas, con preferencia de forma específica frente a genérica (`Form=-1`). Se conservan las ramas evolutivas no modificadas.
- Los métodos numéricos ambiguos de pk3DS (como 19 y 20) se muestran junto al nombre del objeto sin asumir falsamente que son el mismo método vanilla.
- Las evoluciones sin override muestran una **referencia general de Gen7 derivada de PokéAPI**, limitada a especies de Gen1–7 y versiones históricas; para métodos muy específicos puede no coincidir exactamente con los cambios de tu ROM.

Los CSV se importan **solo localmente**, no a GitHub ni al Worker. Los ajustes validados se guardan en `runtime/pk3ds-templates.json` (o en el directorio del perfil secundario), y vuelven a cargarse al iniciar. La carga es atómica: ante CSV incorrecto no se reemplaza el archivo anterior. Los datos visibles del equipo y cajas se actualizan al importar; el próximo ciclo de sincronización enviará la evolución y estadísticas base del Pokémon a la vista del compañero. El otro jugador debe importar su propia plantilla si desea que sus movimientos se describan según su ROM.

### Importante

Los templates describen la **configuración deseada del randomizer**. No demuestran que se aplicaran exitosamente a la ROM, ni corrigen parches Battle.cro, ni garantizan el comportamiento del juego. Los valores en RAM siguen siendo los que el emulador realmente reporta. No subas los archivos de `runtime` a Git.

## Prioridad posterior

Ventana nativa de escritorio (sin abrir manualmente `.bat`). No incluida en esta rama; no cambia el funcionamiento local del servidor HTTP ni la interfaz web.
