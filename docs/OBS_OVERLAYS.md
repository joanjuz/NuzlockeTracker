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
| Objetos equipados | http://127.0.0.1:8765/overlay?layer=items |
| Solo objeto del Pokémon 1 | http://127.0.0.1:8765/overlay?layer=items&slot=1 |
| Cementerio | http://127.0.0.1:8765/overlay?layer=graveyard |
| Datos (nivel, tipos, shiny, sexo) | http://127.0.0.1:8765/overlay?layer=info |
| Estadísticas de la partida | http://127.0.0.1:8765/overlay?layer=stats |
| Cualquier fuente con un perfil fijo | añade `&preset=Nombre` al enlace |

Cambia el valor slot=1 por cualquier posición entre 1 y 6 para crear **18 elementos independientes** y moverlos donde quieras en OBS. También puedes utilizar solo las tres filas, o la composición completa. El fondo de las fuentes es transparente. Recomendación inicial: 960 × 180 px por fila.

## Personalización

La pestaña **OBS** tiene guardado automático, sin la antigua vista previa interna. Permite ordenar las capas, elegir distribución en fila, columna o cuadrícula, tamaño y espacio entre Pokémon.

**Sprites:** reutiliza los GIF y PNG de la carpeta layout, junto con los sprites personalizados existentes. Cuando un Pokémon está registrado en Muertos, su sprite se muestra en escala de grises. El overlay aplica el gris directamente aunque el archivo exportado tarde en regenerarse (por ejemplo, con sprites HD animados), y lo quita al revivirlo.

**Conjuntos de sprites:** cada subcarpeta de `sprites_personalizados` es un conjunto (por ejemplo `HD/` o `Pixel/`). En «Conjunto de sprites» eliges cuál usa OBS; si a un conjunto le falta un Pokémon, se usa el de la carpeta principal y, si tampoco está, el sprite normal. Las importaciones van al conjunto elegido; escribe un nombre en «Crear conjunto al importar» para crear uno nuevo al importar.

**Iconos de objetos propios:** coloca imágenes en `sprites_personalizados/objetos/` (o en `objetos/` dentro de un conjunto) nombradas con el número del objeto, su nombre en inglés de PokeAPI o su nombre en español: `234.png`, `leftovers.png` o `restos.png`. Tienen prioridad sobre los iconos descargados y también se ven en la ventana principal. Admiten PNG, GIF y WebP animados.

**Cementerio:** fuente aparte (`layer=graveyard`) con los Pokémon caídos de la partida activa en una cuadrícula y con el sprite en gris. Puedes elegir cuántos mostrar (hasta 60), las columnas, el tamaño del sprite, el orden (recientes o antiguos primero), el título con el total y si se ven el mote, la especie, el nivel y la ruta de captura. Usa el conjunto de sprites elegido.

**Variantes shiny y hembra:** dentro de un conjunto, las subcarpetas `shiny/` y `female/` (o `Hembra/`) se usan solas cuando el Pokémon es variocolor o hembra; si falta el archivo, se usa el sprite normal del conjunto.

**Perfiles de estilo:** guarda la configuración actual con un nombre («Combate», «Exploración»…) y aplícala con un clic. Con «Fijar enlaces a este perfil», los enlaces copiados llevan `&preset=Nombre` y esa fuente de OBS usa siempre ese perfil, aunque cambies la configuración actual. Los perfiles se guardan por partida. Un perfil fija la apariencia (tamaños, colores, capas, orden del cementerio…); el conjunto de sprites y las imágenes importadas (barra, contador, marco y lápida) son comunes a todos los perfiles, porque los comparten todas las fuentes de OBS.

**Vista previa:** el editor muestra arriba la fuente elegida sobre un fondo a cuadros (para ver la transparencia) y se actualiza mientras cambias los ajustes.

**Estilo de muerte:** al morir, el sprite puede pasar a gris, ocultarse o cambiar por una lápida. Para usar tu propia lápida, coloca `lapida.png` (o GIF/WebP) en `sprites_personalizados` o en el conjunto elegido. Opcionalmente, una animación de fundido o sacudida se reproduce una sola vez, en el momento de la muerte.

**Marco por hueco:** importa un PNG transparente que se dibuja detrás de cada sprite del equipo.

**Datos del Pokémon:** capa `layer=info` con nivel, tipos (con su color), estrella si es variocolor y símbolo de sexo; cada dato se puede ocultar. También puede ir dentro de la composición.

**Estadísticas de la partida:** capa `layer=stats` con capturas, muertes, Pokémon vivos en el equipo y rutas perdidas, en fila o en columna.

**Copia de seguridad:** «Exportar ajustes» guarda en un archivo la configuración, los perfiles, los PNG importados y las fuentes; «Importar ajustes» la restaura en otra partida u otro equipo. Si el conjunto de sprites o la fuente no existen en el destino, se usa la carpeta principal y la fuente del sistema. Si las fuentes o imágenes son muy grandes, la exportación omite las que no caben (hasta unos 40 MB) y lo avisa.

**Motes:** Oxanium, Arial, Segoe UI, Verdana, Georgia, monospace, o cualquier fuente que importe el usuario en formato TTF, OTF, WOFF o WOFF2 (hasta 3 MB). Se personalizan tamaño, color, contorno, grosor y ancho de posición.

**Objetos:** muestra el objeto que lleva cada Pokémon en ese momento (Restos, Cinta Elección…); se vacía cuando lo consume o se lo quitas. Se usa como fuente aparte con `layer=items` o dentro de la composición, debajo de los motes, activando «Incluir objetos en composición». Tamaño y color configurables. «Mostrar objeto como» permite elegir **nombre, icono o icono y nombre**; el icono va encima del nombre y su tamaño es ajustable. Los iconos son los sprites de objetos de PokeAPI: se descargan una vez y quedan en la caché local de sprites; si un icono no existe o no hay conexión, se muestra el nombre. Las configuraciones guardadas antes de estas opciones siguen igual (solo nombre).

**PS:** barra configurable con tres colores por umbral, estilos sólido/degradado/franjas, alto, borde y redondeo, relleno invertido, brillo, etiquetas (valor, porcentaje, ambos o ninguno), color y tamaño del texto. Se actualiza desde la lectura del juego, incluidos PS de combate. Puedes **importar dos PNG transparentes** (marco y relleno, hasta 2 MB cada uno) y activar cada uno por separado. El relleno PNG se recorta sin deformar la imagen a medida que cambia el porcentaje. Los PNG importados se guardan en `runtime/obs-hp-images/`. Usa imágenes con centro transparente para el marco.

## Privacidad, persistencia y compatibilidad

El editor y toda la API privada del tracker **solo escuchan en localhost**. El acceso remoto opcional abre un segundo servidor de **solo lectura** en la IPv4 exacta que indiques. Publica exclusivamente especie, mote, objeto equipado, nivel, tipos, si es variocolor, sexo, estadísticas de la partida (capturas, muertes, vivos y rutas perdidas), los datos visibles del cementerio (mote, especie, nivel y ruta de los caídos), vida actual/máxima, porcentaje, estado de muerte y si la lectura está desactualizada. No expone cajas, ROM, PID ni tokens Soul Link.

Las opciones del editor se guardan por perfil bajo AppData/PokemonTracker/runtime/obs-overlay.json, y las tipografías bajo runtime/obs-fonts. Estos archivos no se distribuyen en el ejecutable.

Por defecto OBS debe estar en la **misma computadora**; una URL con 127.0.0.1 no funcionará desde otro equipo.

### Compartir el overlay por Radmin VPN

1. En la computadora que ejecuta Pokémon Tracker, abre Radmin VPN y localiza **su propia IP IPv4** (ejemplo: `26.10.20.30`). **No escribas la IP del compañero**.
2. En la pestaña OBS, introdúcela en **Mi dirección IPv4 de Radmin VPN** y pulsa **Activar / actualizar IP**.
3. En **Usar enlaces de**, escoge **Compartir por Radmin VPN**. Los botones **Copiar** mostrarán las URL reales, por ejemplo: `http://26.10.20.30:8767/overlay?layer=hp`. Si el puerto 8767 ya estaba ocupado se usará otro y aparecerá en la URL; el segundo perfil prefiere 8768.
4. El compañero, conectado a **la misma red Radmin VPN**, agrega esa dirección como **Fuente de navegador** en OBS. Si no conecta, comprueba que Windows Firewall permita conexiones entrantes privadas de `PokemonTracker.exe` en ese puerto y que la VPN siga activa.
5. Para cambiar la IP, escribe la nueva dirección y pulsa **Activar / actualizar IP**. Después copia los enlaces nuevos. Para cortar el acceso pulsa **Desactivar**. Por seguridad el acceso remoto **no se activa automáticamente al reiniciar**.

**Seguridad:** solo se comparte la vista OBS: sprites, motes, porcentajes/PS y ajustes de presentación. No se exponen `/api/session`, cajas, contraseñas, tokens Soul Link, comandos, ni la interfaz de edición. Otros participantes con acceso a esa VPN y a la dirección podrían visualizar el overlay. No expongas este puerto al Internet público ni configures `0.0.0.0`. El tracker debe permanecer abierto. Los PS pueden aparecer antes de las animaciones del emulador. Los sprites GIF pueden requerir refresco según la versión de OBS. ORAS y X/Y siguen fuera del alcance de esta fase.
