# Overlay para OBS — Pokémon Tracker

Pokémon Tracker hospeda las fuentes de navegador en un servidor local 127.0.0.1, activo mientras el programa está abierto. No se suben partidas a Cloudflare ni se requiere otro programa.

## Instalar en OBS

En Pokémon Tracker abre **OBS**, utiliza los botones **Copiar** y pega cada URL como **Fuente de navegador**. Los enlaces de la primera ventana utilizan normalmente el puerto 8765, y la segunda usa 8766. Si están ocupados, el editor dará el puerto realmente asignado.

| Elementos | Enlace ejemplo |
| --- | --- |
| Tres capas | http://127.0.0.1:8765/overlay?layer=all |
| Seis sprites | http://127.0.0.1:8765/overlay?layer=sprites |
| Seis motes | http://127.0.0.1:8765/overlay?layer=names |
| Seis barras | http://127.0.0.1:8765/overlay?layer=hp |
| Solo mote del Pokémon 1 | http://127.0.0.1:8765/overlay?layer=names&slot=1 |
| Solo barra del Pokémon 1 | http://127.0.0.1:8765/overlay?layer=hp&slot=1 |

Cambia el valor slot=1 por cualquier posición entre 1 y 6 para crear **18 elementos independientes** y moverlos donde quieras en OBS. También puedes utilizar solo las tres filas, o la composición completa. El fondo de las fuentes es transparente. Recomendación inicial: 960 × 180 px por fila.

## Personalización

La pestaña **OBS** incorpora previsualización y auto-guardado. Permite ordenar las capas, elegir distribución en fila, columna o cuadrícula, tamaño y espacio entre Pokémon.

**Sprites:** reutiliza los GIF y PNG de la carpeta layout, junto con los sprites personalizados existentes. Respeta la escala de grises por muerte.

**Motes:** Oxanium, Arial, Segoe UI, Verdana, Georgia, monospace, o cualquier fuente que importe el usuario en formato TTF, OTF, WOFF o WOFF2 (hasta 3 MB). Se personalizan tamaño, color, contorno, grosor y ancho de posición.

**PS:** barra configurable con tres colores por umbral, estilos sólido/degradado/franjas, alto, borde y redondeo, relleno invertido, brillo, etiquetas (valor, porcentaje, ambos o ninguno), color y tamaño del texto. Se actualiza desde la lectura del juego, incluidos PS de combate.

## Privacidad, persistencia y compatibilidad

El overlay **solo escucha en localhost**. Publica exclusivamente especie, mote, vida actual/máxima, porcentaje, estado de muerte y si la lectura está desactualizada. No expone cajas, ROM, PID ni tokens Soul Link.

Las opciones del editor se guardan por perfil bajo AppData/PokemonTracker/runtime/obs-overlay.json, y las tipografías bajo runtime/obs-fonts. Estos archivos no se distribuyen en el ejecutable.

OBS debe estar en la **misma computadora**; una URL con 127.0.0.1 no funcionará desde otro equipo. El tracker debe permanecer abierto. Los PS pueden aparecer antes de las animaciones del emulador. Los sprites GIF pueden requerir refresco según la versión de OBS. ORAS y X/Y siguen fuera del alcance de esta fase.
