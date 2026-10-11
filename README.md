# Progressive Tracker

**Progressive Tracker** (antes *Pokémon Tracker*) es una aplicación local para Windows que lee los datos de Pokémon desde la memoria del emulador, organiza aventuras Nuzlocke y Soul Link y genera fuentes visuales para OBS.

> **Versión de descarga:** **v0.24.0**, con soporte de Gen6 y Gen7 y mejoras OBS HD. La versión descargable es una aplicación **portable**: no hace falta instalar Python ni Node.js.

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

Desde el editor OBS de la aplicación puedes copiar URLs para **Fuentes de navegador** y personalizar sprites, texto y PS. Las URL son locales, normalmente en `127.0.0.1` con el puerto elegido por el tracker. Se admite compartir, de manera opcional y controlada, una vista de solo lectura por Radmin VPN.

Los gráficos OBS HD están cubiertos por pruebas automatizadas; se recomienda verificar el resultado visual real de cada escena, sobre todo las animaciones y el escalado.

## Desarrollo

La rama **`master`** contiene la versión principal; los cambios se preparan en `feature/*` y se integran mediante pull requests.

Para ejecutar en modo desarrollo, utiliza Python 3.13 y las dependencias pertinentes. Para compilar la aplicación portable en Windows:

```powershell
powershell -ExecutionPolicy Bypass -File tools/build_windows.ps1
```

Las compilaciones y pruebas se ejecutan en GitHub Actions. El flujo de release genera el ZIP desde Windows, ejecuta pruebas, verifica que el EXE se inicia y publica la descarga junto a su hash SHA-256.

## Documentación

- [Instalación de la versión portable](docs/INSTALACION_PORTABLE_WINDOWS.txt)
- [Notas de la versión v0.24.0](docs/releases/v0.24.0.md)
- [Instrucciones de escritorio y resolución de problemas](docs/DESKTOP_WINDOWS.md) (incluye documentación histórica)
- [Compatibilidad Gen6](docs/COMPATIBILIDAD_GEN6.md)
- [Gráficos OBS HD](docs/OBS_HD_CUSTOM_SPRITES.md)
- [Soul Link Companion](docs/SOULLINK_COMPANION.md)
- [Historial de versiones](docs/HISTORIAL_VERSIONES.md)

## Seguridad y atribuciones

El tracker **no escribe en la RAM del emulador** ni edita ROMs o partidas. Las credenciales Soul Link, sesiones privadas y demás archivos de `runtime` no se incluyen en las descargas. Consulta [LICENSE.txt](LICENSE.txt) y las atribuciones correspondientes de sprites, datos y fuentes incluidas en el repositorio.
