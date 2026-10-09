POKEMON TRACKER - APLICACION PARA WINDOWS (VERSION EXPERIMENTAL)

INICIAR
1. Descarga PokemonTracker-Windows-x64.zip desde los artefactos de GitHub Actions.
2. Extrae el ZIP en una carpeta nueva. Esta edición usa un EXE independiente:
   solo necesitas PokemonTracker.exe para ejecutarla; LEEME.txt y LICENSE.txt
   son documentación. La primera apertura puede tardar más por extracción temporal.
3. Ejecuta PokemonTracker.exe con doble clic. No exige instalar Python, abrir .bat
   ni ejecutar un servidor en la consola: la ventana usa Microsoft Edge WebView2.
4. La ventana abre directamente con tu sesión guardada, sin selector de jugadores.
   Al abrir una segunda ventana del EXE, se utiliza automáticamente el otro
   perfil local existente para Soul Link. Si hay dos Lime3DS, conecta cada PID.
5. Requisitos: Windows 10/11 x64, Microsoft Edge WebView2 Runtime instalado.

PERFILES, PARTIDAS Y SOUL LINK
- El ZIP no incluye ROM, partidas de emulador, tokens, claves ni datos privados.
- Tus datos se guardan en %LOCALAPPDATA%\PokemonTracker\runtime (fuera del ZIP).
- Si el EXE está ubicado en dist/PokemonTracker/ dentro del repositorio antiguo,
  se copia automáticamente el directorio runtime al iniciar por primera vez.
- El primer inicio intenta detectar y copiar el runtime del proyecto antiguo,
  cuando la carpeta del repositorio es accesible desde la ubicación del EXE
  o se encuentra como NuzlockeTracker junto a la carpeta de descarga.
  Si no está junto al ejecutable, cierra la app y copia manualmente el runtime
  antiguo a %LOCALAPPDATA%\PokemonTracker\runtime antes de usarla.
  Ejemplo del origen: D:\Progra\NuzlockeTracker\runtime
- El traspaso COPIA las credenciales Soul Link, perfiles de ambos jugadores,
  configuraciones y plantillas pk3DS y el último Equipo/Cajas; no elimina
  los originales ni sobrescribe datos ya existentes.
- Si el perfil anterior ya fue creado en %LOCALAPPDATA%, el importador no lo
  reemplaza para prevenir la pérdida de progreso. Haz una copia de seguridad.
- Cada ventana tiene su propio puerto localhost (127.0.0.1).
- El emulador puede cambiar de PID tras cerrarse; vuelve a elegirlo en Conexión.
- Opcional: en accesos directos avanzados se admite --profile principal
  o --profile segundo-jugador, pero estos nombres no se muestran en pantalla.

DISTRIBUCION LIMPIA
- La distribución ahora incluye un único PokemonTracker.exe, sin carpeta _internal.
- El ejecutable autoextrae sus dependencias temporalmente; así las DLL no
  conservan individualmente el bloqueo de archivos descargados de Internet.
- El paquete excluye .bat, tests, scripts de diagnóstico, Git y la fuente del Worker.
- El repositorio conserva los .bat temporalmente como alternativa para depuración;
  no los borres todavía hasta verificar que la versión de escritorio funciona.
- Para actualizar, extrae la versión nueva en otra carpeta. Los datos guardados
  en %LOCALAPPDATA% no se reemplazan.

SOLUCIONAR PROBLEMAS
- Instala o repara Microsoft Edge WebView2 Runtime si aparece un error de ventana.
- Si no abre, revisa %LOCALAPPDATA%\PokemonTracker\desktop-error.log.
- El test de compilación ahora carga Python.NET/WinForms y comprueba el servidor,
  por lo que detecta el error Python.Runtime.Loader.Initialize antes de publicar.
- Windows SmartScreen puede avisar porque la compilación experimental no está
  firmada digitalmente. Comprueba la procedencia del artefacto y no desactives
  protecciones del sistema sin verificarlo.
- No borres el runtime antiguo hasta confirmar que el nuevo inicia y sincroniza.

Esta version experimental todavía necesita validarse en Windows con Lime3DS,
Ultra Sol y Ultra Luna y las plantillas pk3DS reales.

LAYOUT PARA OBS
- Al abrir, se crea la carpeta layout junto al ejecutable, cuando es posible
  escribir allí; de lo contrario se usa %LOCALAPPDATA%\PokemonTracker\layout.
- Dentro aparecen seis archivos con nombres fijos: pokemon_1.png ... pokemon_6.png.
- Los sprites se actualizan al cambiar el equipo. Las posiciones vacías usan
  un PNG transparente 96x96. Los sprites se descargan de PokéAPI y se cachean
  después de la primera lectura. La conexión perdida conserva el último equipo.
- Para dos ventanas, los sprites del segundo perfil van a layout\perfil_2\.
- OBS puede cargar cada PNG por su ruta como Fuente de imagen. Según la versión
  de OBS, puede ser necesario refrescar la fuente para que relea el archivo.

SPRITES PERSONALIZADOS (LAYOUT PARA OBS)
- Coloca los PNG en la carpeta 'sprites_personalizados' junto al ejecutable.
  Si Windows impide escribir junto al EXE, usa:
  %LOCALAPPDATA%\PokemonTracker\sprites_personalizados
- El nombre debe ser el número de la especie en la Pokédex nacional, con
  extensión .png: 25.png (Pikachu), 94.png (Gengar), 448.png (Lucario).
- Formas de Alola: usa 37-alola.png (Vulpix), 38-alola.png (Ninetales),
  50-alola.png (Diglett). También acepta el ID específico del sprite
  como 10103.png si no existe 37-alola.png.
- Recomendado PNG con transparencia, hasta 512x512 y 500 KB por sprite.
- Prioridad: personalizado -> sprite habitual en caché/paquete -> PokeAPI.
  No es necesario personalizar todos los Pokémon.
- Cuando un Pokémon se registra como muerto (automática o manualmente),
  el PNG de layout pasa a escala de grises, manteniendo su transparencia.
  «Revivir» restaura el color del sprite. Los originales no se alteran.
- Las imágenes personalizadas se recargan automáticamente sin reiniciar.
  Esta mejora afecta al layout de seis PNG; no reemplaza las imágenes de
  la interfaz principal del tracker.

AZAHAR: ACCESO DENEGADO
- Si aparece WinError 5, Windows rechazó OpenProcess para leer RAM.
  Inicia Azahar y Pokémon Tracker con los mismos permisos habituales,
  sin elevar solo Azahar. Verifica el PID si hay varios emuladores.
- No intentamos saltarnos los controles de permisos ni forzar acceso.
  Aunque se resuelva el permiso, el mapa RAM de Azahar sigue pendiente
  de validación real para Ultra Sol/Luna.

DIAGNOSTICOS
- En Azahar/Citra el lector intenta búsqueda dinámica para Ultra Sol y Ultra Luna.
- El botón «Guardar diagnóstico» guarda directamente un .json en
  %LOCALAPPDATA%\\PokemonTracker\\runtime\\diagnosticos, sin depender de
  descargas del navegador. En el segundo perfil se usa su carpeta de runtime.
- El estado de PS en batalla puede reflejar el cambio antes de que termine
  la animación del juego; no se añade retraso artificial.

ANIMACIONES EN EL LAYOUT (GIF)
- Se admiten sprites personalizados animados .gif además de .png:
  sprites_personalizados\\25.gif, 94.gif, 448.gif, 37-alola.gif, etc.
- Se usa el ID de la Pokédex Nacional. Para Alola se acepta 37-alola.gif
  o el ID propio del sprite (10103.gif). El formato de nombres .png anterior
  no cambia. Si están los dos, el GIF animado tiene prioridad.
- El layout genera simultáneamente seis PNG (pokemon_1.png ...
  pokemon_6.png) y seis GIF (pokemon_1.gif ... pokemon_6.gif).
- Con OBS, añade cada pokemon_N.gif como **Fuente de imagen** si quieres
  movimiento; los pokemon_N.png siguen siendo compatibles con overlays
  estáticos y muestran el primer fotograma del GIF.
- Si un Pokémon no tiene GIF personalizado se genera un GIF estático con su
  imagen predeterminada para mantener siempre las mismas rutas en OBS.
- La muerte convierte todos los fotogramas de la animación a escala de grises;
  Revivir devuelve todos los colores. Los archivos personalizados nunca se
  modifican. Los GIF de salida siempre se repiten en bucle.
- Límites de seguridad: máximo 5 MB por GIF, 512x512, 120 fotogramas
  y 12 millones de píxeles acumulados; los GIF dañados se ignoran y
  se usa la imagen PNG u oficial correspondiente.
- GIF solo tiene transparencia binaria; los PNG conservan niveles de alpha
  completos. En OBS, la recarga de GIF al cambiar de equipo puede variar
  según la versión; si no se refresca, recarga la fuente una vez.
- No se necesita conexión a Internet para usar los sprites personalizados.

GUARDAR SESIÓN Y DIAGNÓSTICO (VENTANA NATIVA)
- Menú ··· → Guardar sesión… abre el selector de archivos de Windows.
  Puedes elegir la carpeta y el nombre del archivo JSON exportado.
  Incluye equipo, cajas, progreso, contador de muertes y juego.
  No incluye tokens de Soul Link, claves ni datos privados del Worker.
- Pestaña Conexión → Guardar diagnóstico… abre el mismo selector de Windows.
  Exporta juego, estado de conexión y detalles de detección de RAM.
  No exporta los datos del equipo ni las cajas.
- Cancelar el diálogo no genera archivos ni cambia la sesión.
- La sincronización, la configuración y los datos del tracker continúan
  guardándose automáticamente en AppData. Exportar es una copia opcional,
  no reemplaza los guardados internos.
- Los diálogos de Guardar como necesitan ejecutarse desde PokemonTracker.exe
  mediante la interfaz nativa WebView2; el servidor web de respaldo no
  muestra diálogos nativos del sistema.
- El icono que se ve en la aplicación se sirve como /app-icon.png desde
  el propio servidor local empaquetado; no necesita Internet.
