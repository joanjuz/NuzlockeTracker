# Sprites HD y calidad de Overlay OBS

Esta mejora está en la rama `feature/obs-hd-custom-sprites` y **no cambia RAM, equipos ni cajas** de Gen6/Gen7.

## Por qué mejoró la nitidez

Antes OBS solicitaba incondicionalmente `pokemon_N.gif`. Incluso para PNG estáticos (con hasta 16.7 millones de colores y transparencia de 8 bits), el servidor generaba una versión GIF limitada a una paleta. El nuevo endpoint público `/api/overlay/public` indica `image_format` por cada Pokémon; OBS usa:
- **PNG** en tamaño original para imágenes estáticas, sin cuantización a GIF.
- **GIF** para sprites con animación GIF.
- **WebP animado** para GIF/APNG/WebP de alta calidad cuando se proporcionan fuentes animadas compatibles. Para GIF se sigue respetando su formato animado original.
- Rutas `/overlay/media/pokemon_1.png`, `.gif` y `.webp`. Las rutas antiguas continúan disponibles; los GIF de compatibilidad pueden ser miniaturas cuando la fuente original supera 512 píxeles.

El renderizado de motes y barras sigue siendo nativo del navegador Chromium. La escala `2×`, `3×` o `4×` usa `zoom`, de modo que texto, bordes y barras se calculan y dibujan al tamaño mayor en la fuente de navegador. Ajusta en OBS el **tamaño de la fuente de navegador** para evitar recortes; por ejemplo, 1920×1080 si usas 2×.

## Importar sprites personalizados

Desde **Editor OBS → Composición y sprites → Importar sprites personalizados**, selecciona hasta 30 imágenes por lote. La aplicación copia esos archivos a tu carpeta local `sprites_personalizados` y los recarga automáticamente (normalmente en el siguiente ciclo de 0,5 s). No requiere instalar programas adicionales.

También puedes copiar manualmente archivos a `sprites_personalizados`, situada junto a la carpeta `layout`. Se aceptan:
- `PNG` y `APNG` (transparencia), `WEBP` (estático o animado), `GIF` (animado), `JPG/JPEG`, `BMP`.
- Ejemplos de nombres: `25.png`, `025.webp`, `pikachu.png`, `25-1.png` (forma), `37-alola.png`, `10103.webp` (identificador de forma), `25-shiny.gif` (cuando hay bandera shiny en los datos del Pokémon).
- El sistema acepta nombres sin importar mayúsculas/minúsculas y normaliza el nombre de especie para compararlo. Las rutas no pueden contener barras ni saltos de carpeta. No se importan SVG ni HTML: pueden contener contenido activo o referencias externas y no se necesita arriesgar OBS.
- Tamaño máximo por archivo: 8 MB, hasta 2048×2048 píxeles y 2,5 megapíxeles por fotograma; animaciones de hasta 120 fotogramas y 16 megapíxeles acumulados. GIF nativo admite hasta 512×512 debido a compatibilidad de salida heredada.
- Prioridad: sprite personalizado válido > caché local > sprite incorporado > descarga de PokeAPI > fondo transparente. Si un archivo está corrupto, se ignora sin bloquear el tracker.

Los PNG originales no se reescriben ni se pierden colores. Cuando un Pokémon se marca muerto, se convierte a escala de grises **solo el archivo que utiliza el overlay**, sin modificar el original.

## Configuración visual nueva

- **Escala para OBS**: 1× a 4× (predeterminado 1× para preservar escenas existentes; 2× recomendado para escenas nuevas).
- **Tipo de escalado**: píxel nítido para pixel art o suave para arte HD.
- **Sombra y margen**: personalizables.
- **Barras de vida**: altura, borde, redondeo, colores y PNG personalizados hasta 4096×1024 o 8 MB; nuevo ajuste de duración del cambio de PS (0–1500 ms).
- **Tipografías**: admite fuentes importadas como antes.
- **GIF heredado**: las rutas PNG/GIF anteriores siguen existiendo, por lo que enlaces de escenas existentes no se eliminan.

### Qué comprobar antes de integrar en master
1. Importar PNG de 512×512 o 1024×1024 y comparar color/transparencia frente a versión anterior.
2. Importar GIF y WebP animado y comprobar que la animación continúa después de una actualización de PS.
3. Cambiar entre modos píxel nítido y suave; probar 1× y 2× con una fuente OBS grande para evitar recortes.
4. Bajar la vida durante una batalla y comprobar que barra, mote y sprite se actualizan sin parpadeos ni datos ajenos en la API pública.
5. Reemplazar el sprite del mismo Pokémon sin reiniciar el tracker y observar el resultado.
