# Progressive Tracker

Soul Link permite una sala de hasta cuatro personas con un enlace común y vista
de partida opcional por jugador. [Guía de Soul Link](docs/SOUL_LINK.md).

## v1.4.0: límites de nivel manuales

Define las etapas de tu aventura con su nivel máximo, sigue tu avance en la nueva
sección **Progreso** y recibe avisos cuando un Pokémon del equipo supera el límite
vigente. Puedes exportar tus etapas a un archivo JSON y reutilizarlas en otra partida.
Los avisos son informativos y el Tracker no incluye límites oficiales. Consulta las
[notas de la versión](docs/releases/v1.4.0.md) y los
[límites de nivel](docs/LIMITES_NIVEL.md).

## v1.3.0: datos de Definitive Randomizer por partida

Importa Definitive Game Data v1 de Ultra Sol o Ultra Luna, revisa diferencias y
conserva el catálogo en la partida seleccionada. Puedes reemplazarlo o retirarlo
sin cambiar ROMs ni memoria del emulador. Consulta las
[notas de la versión](docs/releases/v1.3.0.md).

## v1.2.0: perfiles de estilo para OBS, lápidas y datos del Pokémon

Guarda varios estilos de overlay y fija uno por fuente de OBS, elige cómo se ve un
Pokémon caído (gris, oculto o lápida, con animación), añade nivel, tipos, shiny y
sexo, estadísticas de la partida y un marco por hueco, y respalda toda la
configuración de OBS en un archivo. Consulta las [notas de la versión](docs/releases/v1.2.0.md).

## v1.1.0: conjuntos de sprites, cementerio en OBS e iconos de objetos

Cada subcarpeta de `sprites_personalizados` es un conjunto de sprites que eliges en
el editor OBS. Hay una fuente nueva de cementerio con los Pokémon caídos, iconos de
objetos propios y en la ventana principal, y la Partida principal ya se puede
eliminar. Consulta las [notas de la versión](docs/releases/v1.1.0.md).

## v1.0.0: objetos en OBS, Soul Link más seguro y registro de diagnóstico

OBS puede mostrar el objeto que lleva cada Pokémon (nombre, icono o ambos) y el
sprite de un Pokémon caído vuelve a verse en blanco y negro. Los datos del
compañero de Soul Link se validan antes de mostrarse, el progreso se protege
frente a archivos dañados y la aplicación guarda un registro de diagnóstico local
sin secretos. Consulta las [notas de la versión](docs/releases/v1.0.0.md).

## v0.25.0: partidas, Soul Link directo y vidas OBS

La barra superior permite crear, seleccionar y eliminar partidas con datos independientes.
El botón Eliminar partida borra la seleccionada y protege las partidas abiertas y la principal.
Soul Link puede conectar directamente dos trackers en una red local o VPN, con
una aplicación como host. OBS incorpora muertes o vidas restantes, icono PNG
personalizado y vidas perdidas ocultas o en gris. Ultra Luna usa búsqueda dinámica
sin cambiar su nombre a Ultra Sol. La conexión muestra los procesos abiertos y
comprueba que su juego coincida; revalida la caché de la instancia, prueba una
sonda acotada y recurre a la búsqueda completa cuando hace falta. Las cajas Gen7
se publican tras validar las 32 con lecturas repetidas: un PC vacío sin confirmar
se mantiene pendiente y conserva la última lectura guardada.

Consulta [partidas independientes](docs/PERFILES_PARTIDAS.md),
[límites de nivel](docs/LIMITES_NIVEL.md),
[contadores OBS](docs/CONTADORES_OBS.md) y
[conexión Soul Link directa](docs/SOULLINK_DIRECTO.md). El ejecutable local se genera con `tools/build_windows.ps1`;
la distribución publicada se encuentra en GitHub Releases.

**Progressive Tracker** (antes *Pokémon Tracker*) es una aplicación local para Windows que lee los datos de Pokémon desde la memoria del emulador, organiza aventuras Nuzlocke y Soul Link y genera fuentes visuales para OBS.

> **Versión actual:** **v1.4.0**, con límites de nivel manuales y las funciones de v1.3.0. La descarga oficial está en GitHub Releases. Es una aplicación **portable**: no hace falta instalar Python ni Node.js.

## Descargar para Windows

**[Descargar la última versión (GitHub Releases)](https://github.com/joanjuz/NuzlockeTracker/releases/latest)**

1. Abre la versión más reciente y, en **Assets**, descarga **`PokemonTracker-Windows-x64.zip`**.
2. Extrae el ZIP en una carpeta nueva.
3. Ejecuta **`PokemonTracker.exe`** en Windows 10/11 de 64 bits.
4. Abre Lime3DS y selecciona juego/PID en **Conexión**.

Requiere **Microsoft Edge WebView2 Runtime**. El EXE no está firmado digitalmente. **Nunca descargues una ROM desde este proyecto**: no se incluyen juegos ni partidas.

Los datos se conservan en `%LOCALAPPDATA%\PokemonTracker\runtime`. Antes de actualizar, cierra la aplicación y haz una copia de seguridad de esta carpeta.

## Juegos compatibles

| Generación | Juego (versión 1.0) | Equipo | Cajas | PS durante combate |
| --- | --- | --- | --- | --- |
| 6 | Pokémon X / Y | Sí | 31 | Sí |
| 6 | Pokémon Rubí Omega / Zafiro Alfa | Sí | 31 | Sí |
| 7 | Pokémon Ultra Sol / Ultra Luna | Sí | 32 | Sí |

Las funciones principales se han validado con **Lime3DS en Windows**. La compatibilidad con Azahar, Citra, otras revisiones y todas las ROM personalizadas no está garantizada.

## Características

- Equipo y PC con lectura de RAM **solo lectura**, búsqueda y actualización automática de cajas.
- **Living Dex** por orden nacional con Poké Balls o sprites de especies ausentes.
- Rutas, capturas, MISS, muertes, revivir, fósiles, regalos, huevos, intercambios e historial.
- Información de movimientos, estadísticas, IV/EV y análisis de tipos ofensivo/defensivo.
- Importación informativa de CSV de **pk3DS Progressive** (movimientos, estadísticas base y evoluciones).
- **Soul Link Companion** opcional y visualización del equipo, cajas y progreso del compañero. No registra muertes locales automáticamente por eventos remotos.
- Overlays transparentes para **OBS**, con sprites, motes y barras de vida independientes, estilos, fuentes y escalado HD.
- Sprites personalizados PNG, APNG, GIF, WebP y otros formatos estáticos admitidos, con recarga en caliente.

## OBS

Desde el editor OBS de la aplicación puedes copiar URLs para **Fuentes de navegador** y personalizar sprites, texto y PS. Hay capas para sprites, motes, PS, objetos equipados (nombre o icono), contador de muertes o vidas y un **cementerio** con los Pokémon caídos. Cada subcarpeta de `sprites_personalizados` funciona como un conjunto de sprites que se elige en el editor, y en `objetos/` puedes poner iconos de objetos propios. Detalles en [OBS_OVERLAYS.md](docs/OBS_OVERLAYS.md). Las URL son locales, normalmente en `127.0.0.1` con el puerto elegido por el tracker. Se admite compartir, de manera opcional y controlada, una vista de solo lectura por Radmin VPN.

Los gráficos OBS HD están cubiertos por pruebas automatizadas; se recomienda verificar el resultado visual real de cada escena, sobre todo las animaciones y el escalado.

## Desarrollo

La rama **`master`** contiene la versión principal; los cambios se preparan en `feature/*` y se integran mediante pull requests.

Para ejecutar en modo desarrollo, utiliza Python 3.13 y las dependencias pertinentes. Para compilar la aplicación portable en Windows:

```powershell
powershell -ExecutionPolicy Bypass -File tools/build_windows.ps1
```

Los lanzadores de desarrollo están en `tools/`: `tools\Iniciar.bat` (lectura real), `tools\Iniciar_Demo.bat` (o `bash tools/Iniciar_Demo.sh` en Linux), `tools\Iniciar_Segundo_Jugador.bat` y los diagnósticos `tools\Diagnostico_Gen6.bat` y `tools\Diagnostico_Combate.bat`. Cada uno cambia a la raíz del repositorio antes de ejecutar Python, así que pueden abrirse con doble clic.

Para crear una prueba de regresión con tu partida real, abre el emulador con el juego cargado y ejecuta `python tools/capture_ram_fixture.py --label equipo-ruta-1`: guarda solo los bytes que el tracker decodifica, con motes, entrenador e identificadores anonimizados, en `tests/fixtures/ram/`.

Las compilaciones y pruebas se ejecutan en GitHub Actions. El flujo de release genera el ZIP desde Windows, ejecuta pruebas, verifica que el EXE se inicia y publica la descarga junto a su hash SHA-256.

## Documentación

- [Instalación de la versión portable](docs/INSTALACION_PORTABLE_WINDOWS.txt)
- [Notas de la versión v1.2.0](docs/releases/v1.2.0.md)
- [Notas de la versión v1.1.0](docs/releases/v1.1.0.md)
- [Notas de la versión v1.0.0](docs/releases/v1.0.0.md)
- [Notas de la versión v0.25.0](docs/releases/v0.25.0.md)
- [Notas de la versión v0.24.0](docs/releases/v0.24.0.md)
- [Instrucciones de escritorio y resolución de problemas](docs/DESKTOP_WINDOWS.md) (incluye documentación histórica)
- [Compatibilidad Gen6](docs/COMPATIBILIDAD_GEN6.md)
- [Firma de código del ejecutable](docs/FIRMA_CODIGO.md)
- [Gráficos OBS HD](docs/OBS_HD_CUSTOM_SPRITES.md)
- [Soul Link Companion](docs/SOULLINK_COMPANION.md)
- [Historial de versiones](docs/HISTORIAL_VERSIONES.md)

## Seguridad y atribuciones

El tracker **no escribe en la RAM del emulador** ni edita ROMs o partidas.

**Conexiones de red.** El tracker funciona en local y solo se conecta a Internet para:

- Descargar sprites de Pokémon e iconos de objetos desde el repositorio público de PokeAPI en GitHub; se guardan en una caché local.
- Comprobar una vez al día si hay una versión nueva, consultando la última release pública de este repositorio en GitHub. Solo muestra un aviso con el enlace; no descarga ni instala nada. Se desactiva con la variable de entorno `POKEMON_TRACKER_NO_UPDATE_CHECK=1`.
- Soul Link, si lo activas: con tu compañero directamente (red local o VPN) o a través del Worker de Cloudflare, enviando solo el estado compartido de la partida.
- La vista de OBS por VPN, si la activas, que sirve en solo lectura las fuentes del overlay.

No envía telemetría, ni datos de la partida a terceros, ni el registro de diagnóstico, que se queda en tu equipo. Las credenciales Soul Link, sesiones privadas y demás archivos de `runtime` no se incluyen en las descargas. Consulta [LICENSE.txt](LICENSE.txt) y las atribuciones correspondientes de sprites, datos y fuentes incluidas en el repositorio.
