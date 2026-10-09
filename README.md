# Pokemon Tracker

Tracker local para **Pokemon Ultra Sol / Ultra Luna 1.0** en Lime3DS.

> Version estable: **v0.20.2**, validada en ambos juegos.

## Funcionalidades

- Lee en vivo el equipo y las cajas desde la memoria del emulador.
- Muestra las estadisticas, movimientos, objetos, habilidades y sprites del equipo.
- Actualiza los PS durante el combate en Ultra Sol y Ultra Luna 1.0.
- Permite cambiar de juego sin reiniciar el servidor.
- Incluye secciones de rutas, Pokemon debilitados y analisis ofensivo/defensivo.
- Incluye modo de demostracion sin emulador.

## Sincronización Soul Link (experimental)

Desde los tres puntos (`···`) puedes vincular tu partida de Ultra Sol con la de tu compañero en Ultra Luna, y ver su última sesión en Equipo, Cajas, Rutas, Muertos y Análisis. Requiere desplegar un Cloudflare Worker + D1: instrucciones en [`docs/SOULLINK_COMPANION.md`](docs/SOULLINK_COMPANION.md). No necesita abrir puertos LAN ni exponer tu emulador.

## Requisitos

- Windows y Python 3 (para lectura de memoria real con Lime3DS).
- Lime3DS con una version compatible del juego.
- Navegador web moderno. No requiere Node.js para ejecutar el tracker.

## Uso

1. Abre Lime3DS con Ultra Sol o Ultra Luna 1.0.
2. Ejecuta `Iniciar.bat`, ubicado en la raiz del proyecto.
3. Se abrira la interfaz web local. En **Conexion**, selecciona el juego y pulsa **Conectar**.

Para iniciar la demostracion sin Lime3DS, ejecuta `Iniciar_Demo.bat`.
El servidor escucha solo en `127.0.0.1` y utiliza un puerto local disponible.

## Pruebas

```powershell
py -3 -m unittest discover -s tests
node tests/test_analysis.js
node tests/test_progress_ui.js
node tests/test_mini_sprites.js
```

Node.js solo es necesario para ejecutar las pruebas JavaScript, no para usar la aplicacion.

## Desarrollo

- `master`: version estable.
- `development`: integracion de nuevas funciones.
- `feature/*`: trabajo en funcionalidades individuales mediante pull requests.
- `backup/nuztracker-react-20261008`: respaldo de la version React/Tauri anterior.

El historial tecnico anterior se encuentra en [`docs/HISTORIAL_VERSIONES.md`](docs/HISTORIAL_VERSIONES.md).
Los datos personales y registros locales se guardan en `runtime/`, que no se sube a Git.

## Fuentes y licencias

Vease `LICENSE.txt` y los avisos de atribucion presentes en `data/` y `web/fonts/`.
## Dos jugadores Soul Link en una PC

Para ejecutar Ultra Sol y Ultra Luna simultáneamente en la misma computadora, usa `Iniciar.bat` para el primer jugador y `Iniciar_Segundo_Jugador.bat` para el segundo. Los procesos usan distintos puertos locales y carpetas `runtime/`; selecciona el PID de cada Lime3DS en **Conexión** para evitar mezclarlos. Consulta [la guía de dos instancias](docs/SOULLINK_2_INSTANCIAS.md).

## Companion v0.23.0

La sincronización reacciona a cambios en la partida y consulta el estado del compañero cada cinco segundos. Las 32 cajas se leen automáticamente al conectar y se revisan en segundo plano. Se comparte un único enlace de invitación con el Worker y el código (sin credenciales administrativas); la URL pública predeterminada está configurada en `companion/sync.py`. `CREATE_KEY` continúa siendo una clave de administración privada.

## Soul Link Companion v0.23.1

La sección **Rutas** incorpora **Muerte** (sin icono ni confirmación) debajo de cada sprite para registrar manualmente Pokémon en **Muertos**; no mata automáticamente a su pareja Soul Link. **Cajas** conserva la última lectura al desconectar o reiniciar el tracker, diferenciándola de la RAM en vivo. Se retiró el texto de lectura automática, pero el escaneo en segundo plano se mantiene.

## Aplicación de escritorio para Windows (experimental)

La nueva rama `feature/app-escritorio-windows` permite compilar `PokemonTracker.exe`: ventana WebView2 propia (sin CMD y sin navegador externo), selector de perfil principal/segundo jugador, datos persistentes en `%LOCALAPPDATA%\\PokemonTracker\\runtime` y traspaso local no destructivo de los perfiles anteriores. El ZIP portable incluye solamente ejecutable, dependencias y recursos de uso (sin BAT, tests, código de Cloudflare ni herramientas). Consulta [guía Windows](docs/DESKTOP_WINDOWS.md). Para compilar en Windows: `powershell -ExecutionPolicy Bypass -File tools/build_windows.ps1` con Python 3.13 instalado. La compilación y ZIP también se publican como artefacto de GitHub Actions en el PR experimental. Los BAT siguen en el repositorio hasta validar el `.exe`.

### Reparación Python.NET en el EXE

La primera build `--onedir` podía bloquear `Python.Runtime.dll` por la marca de seguridad de Windows al extraer ZIP. La compilación de escritorio pasa a `--onefile`, sin `_internal`, y GitHub Actions valida ahora la importación real de `webview.platforms.winforms` además de los endpoints. El archivo `runtime` no se incluye ni se sobrescribe.


### Sprites animados en OBS

La carpeta `sprites_personalizados` admite `25.gif`, `94.gif`, `37-alola.gif` y los nombres `.png` previos. El tracker genera `layout/pokemon_1.gif`…`pokemon_6.gif` para fuentes de imagen animadas de OBS y conserva los seis `.png` como vistas estáticas. Si falta GIF se usa un fotograma estático. Muertos en escala de grises por fotograma; Revivir restaura los colores. Ver [instrucciones de escritorio](docs/DESKTOP_WINDOWS.md).
