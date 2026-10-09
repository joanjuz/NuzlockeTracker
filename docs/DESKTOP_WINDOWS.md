POKEMON TRACKER - APLICACION PARA WINDOWS (VERSION EXPERIMENTAL)

INICIAR
1. Descarga PokemonTracker-Windows-x64.zip desde los artefactos de GitHub Actions.
2. Extrae el ZIP en una carpeta nueva. Esta edición usa un EXE independiente:
   solo necesitas PokemonTracker.exe para ejecutarla; LEEME.txt y LICENSE.txt
   son documentación. La primera apertura puede tardar más por extracción temporal.
3. Ejecuta PokemonTracker.exe con doble clic. No exige instalar Python, abrir .bat
   ni ejecutar un servidor en la consola: la ventana usa Microsoft Edge WebView2.
4. Selecciona "Jugador principal" o "Segundo jugador". Puedes abrir una instancia
   por cada perfil a la vez. Si abres dos Lime3DS, usa su PID correcto en Conexión.
5. Requisitos: Windows 10/11 x64, Microsoft Edge WebView2 Runtime instalado.

PERFILES, PARTIDAS Y SOUL LINK
- El ZIP no incluye ROM, partidas de emulador, tokens, claves ni datos privados.
- Tus datos se guardan en %LOCALAPPDATA%\PokemonTracker\runtime (fuera del ZIP).
- Si el EXE está ubicado en dist/PokemonTracker/ dentro del repositorio antiguo,
  se copia automáticamente el directorio runtime al iniciar por primera vez.
- Si lo extraes desde GitHub a otra carpeta, usa el botón
  "Importar sesión de la versión anterior..." ANTES de abrir un jugador.
  Selecciona la carpeta runtime del proyecto anterior, normalmente:
  D:\Progra\NuzlockeTracker\runtime
- El traspaso COPIA las credenciales Soul Link, perfiles de ambos jugadores,
  configuraciones y plantillas pk3DS y el último Equipo/Cajas; no elimina
  los originales ni sobrescribe datos ya existentes.
- Si el perfil anterior ya fue creado en %LOCALAPPDATA%, el importador no lo
  reemplaza para prevenir la pérdida de progreso. Haz una copia de seguridad.
- Cada ventana tiene su propio puerto localhost (127.0.0.1).
- El emulador puede cambiar de PID tras cerrarse; vuelve a elegirlo en Conexión.
- Si quieres abrir directamente un perfil desde un acceso directo, usa
  PokemonTracker.exe --profile principal
  o PokemonTracker.exe --profile segundo-jugador

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
