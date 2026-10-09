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
- Los métodos numéricos 19 y 20 se interpretan según el editor Gen7 de pk3DS: subir de nivel de día o de noche llevando el objeto indicado. Otros códigos no identificados se muestran como método numérico sin inventar su funcionamiento.
- Las evoluciones sin override muestran una **referencia general de Gen7 derivada de PokéAPI**, limitada a especies de Gen1–7 y versiones históricas; para métodos muy específicos puede no coincidir exactamente con los cambios de tu ROM.

Los CSV se importan **solo localmente**, no a GitHub ni al Worker. Los ajustes validados se guardan en `runtime/pk3ds-templates.json` (o en el directorio del perfil secundario), y vuelven a cargarse al iniciar. La carga es atómica: ante CSV incorrecto no se reemplaza el archivo anterior. Los datos visibles del equipo y cajas se actualizan al importar; el próximo ciclo de sincronización enviará la evolución y estadísticas base del Pokémon a la vista del compañero. El otro jugador debe importar su propia plantilla si desea que sus movimientos se describan según su ROM.

### Importante

Los templates describen la **configuración deseada del randomizer**. No demuestran que se aplicaran exitosamente a la ROM, ni corrigen parches Battle.cro, ni garantizan el comportamiento del juego. Los valores en RAM siguen siendo los que el emulador realmente reporta. No subas los archivos de `runtime` a Git.

## Prioridad posterior

Ventana nativa de escritorio (sin abrir manualmente `.bat`). No incluida en esta rama; no cambia el funcionamiento local del servidor HTTP ni la interfaz web.


## Correcciones de evoluciones y últimos datos (v0.24 experimental)

- Evoluciones regionales: Vulpix normal → Ninetales con **piedra fuego** y Vulpix de Alola → Ninetales de Alola con **piedra hielo**; cada forma muestra el sprite correspondiente (ID 38 normal o ID 10104 de PokéAPI para Alola). Se evita presentar ambas rutas simultáneamente a un solo Vulpix.
- El campo `Form` de la plantilla pk3DS Gen7 corresponde a **la forma del Pokémon resultante**; `-1` hereda la forma. Cuando hay método genérico y método específico de la misma especie/formulario, el específico tiene prioridad.
- Métodos y objetos se presentan en español. Los argumentos numéricos que representan objetos se resuelven mediante el catálogo del propio juego. Por ejemplo, objeto `325` → **Tela Terrible** (Dusclops → Dusknoir por los métodos 19 y 20 modificados). No se afirma que esos métodos sean el comportamiento original de WikiDex, pues son modificaciones de la plantilla.
- Los Pokémon sin evoluciones aplicables no muestran el encabezado ni la sección «Cómo evoluciona».
- La última lectura de **Equipo**, igual que Cajas, permanece en el estado local cuando se desconecta el emulador o se reinicia el servidor. Ambos se muestran como información guardada, **no en vivo**. Cambiar de Ultra Sol a Ultra Luna elimina el equipo y cajas del otro juego para que no se mezclen.
- Se mantienen aislados los dos perfiles locales y el vínculo Soul Link. No se modifican la ROM, el save ni el Worker de Cloudflare.

Fuentes consultadas para la nomenclatura y las reglas base: WikiDex (Vulpix, Vulpix de Alola, Ninetales de Alola y Tela Terrible); pk3DS Gen7 EvolutionEditor7 para índices de métodos; PokéAPI `pokemon.csv` y repositorio de sprites para los identificadores regionales. La plantilla local sigue prevaleciendo sobre el método de referencia.
