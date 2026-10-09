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