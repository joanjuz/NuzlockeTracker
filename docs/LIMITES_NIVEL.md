# Límites de nivel por partida

Los límites de nivel son **manuales**: el jugador define cada etapa y su nivel máximo. El tracker no incluye límites oficiales ni predeterminados de ningún juego, romhack o desafío, y no los deduce de la RAM. Los avisos son informativos: no impiden subir de nivel ni cambian nada en la partida.

## En la interfaz

- **Progreso** (barra de secciones): la etapa vigente con su límite, «Etapa N de M» y una barra de avance; «Etapa anterior» y «Siguiente etapa»; un selector para elegir la etapa vigente (o ninguna); la casilla «Mostrar el límite en la cabecera y en las fichas», y el equipo comparado con el límite.
- **Etapas**: tabla para añadir, renombrar, cambiar el nivel, reordenar (↑ ↓) y eliminar. Los cambios son un borrador hasta pulsar «Guardar cambios», que aplica la lista entera de una vez; «Descartar» la deja como estaba. Cada error aparece junto a su fila. Un límite más bajo que el de la etapa anterior se avisa, pero se puede guardar.
- **Cabecera**: un indicador «Límite Nv. N · etapa», con «· X por encima» si algún Pokémon del equipo lo supera; «Sin etapa vigente» si hay etapas pero ninguna elegida. Al pulsarlo se abre Progreso. No aparece si la partida no tiene etapas o si se ocultan los límites.
- **Fichas del equipo**: «+N sobre el límite» en los Pokémon que lo superan (los huevos no cuentan).
- **Listas de etapas** (al final de Progreso): «Exportar lista…» guarda las etapas guardadas en un JSON y «Importar lista…» abre uno con vista previa. Ver [Listas de etapas reutilizables](#listas-de-etapas-reutilizables).
- Si se elimina la etapa vigente, la partida queda «Sin etapa vigente» y Progreso indica cuál se eliminó; hay que elegir otra explícitamente.
- Cambiar de sección conserva el borrador (la pestaña muestra «sin guardar»). Cambiar o crear una partida, recargar o cerrar la ventana con cambios sin guardar pide confirmación antes de descartarlos.
- En la vista del compañero de Soul Link, Progreso no está disponible: los límites son de tu partida y no se comparten.

## Dónde se guardan

En el registro de la aventura de cada partida y juego (`…-progress.json`, el mismo archivo que las rutas, muertes y marcas), bajo la clave opcional `level_caps`. Cada partida y cada juego de una partida tienen sus propios límites. Se escriben con el mismo método que el resto del registro: archivo temporal, `fsync`, reemplazo atómico y copia `.bak` de la versión anterior.

```json
"level_caps": {
  "version": 1,
  "stages": [
    {"id": "3f2a9c1b7e04", "name": "Primer gimnasio", "cap": 14},
    {"id": "9d81c0aa52f6", "name": "Segundo gimnasio", "cap": 20}
  ],
  "current": "3f2a9c1b7e04",
  "show": true,
  "updated_at": "2026-11-11T20:00:00+00:00",
  "removed_current": null
}
```

| Campo | Reglas |
|---|---|
| `stages` | Hasta 64 etapas, en orden. `name`: de 1 a 60 caracteres sin caracteres de control (se recortan los espacios de los extremos). `cap`: entero de 1 a 100. `id`: identificador estable y único (`[A-Za-z0-9_-]`, hasta 32), asignado por el tracker al crear la etapa. |
| `current` | ID de la etapa vigente o `null`. Sigue al ID, no a la posición: reordenar no cambia la etapa vigente. |
| `show` | Mostrar u ocultar los límites. |
| `removed_current` | Si se elimina la etapa vigente, `current` pasa a `null` (no se elige otra) y aquí queda la etapa eliminada hasta que se elija una nueva. |

Los límites decrecientes están permitidos; el resumen los informa en `decreasing`. Sin la clave, una partida no tiene límites. Las partidas anteriores cargan igual.

## Órdenes (`POST /api/command`)

| Acción | Cuerpo | Efecto |
|---|---|---|
| `level_caps_set` | `stages` (lista completa; las etapas nuevas sin `id`) y, opcional, `current` (ID de la lista o `null`) | Sustituye la lista de una vez: orden, nombres, límites, altas y bajas. Sin `current` se conserva la vigente si sigue en la lista. Admite hasta 32 KB; las demás órdenes mantienen 4096 bytes. |
| `level_caps_current` | `stage`: ID o `null` | Cambia la etapa vigente. |
| `level_caps_show` | `show`: booleano | Muestra u oculta los límites. |

Cada orden se valida antes de encolarla: si no es válida responde 400 y no cambia nada. El trabajador la vuelve a validar antes de aplicarla.

El estado incluye un resumen de solo lectura, `level_caps`: `status` (`none`, `ok` o `unsupported`), etapas, vigente con su posición, límite y nombre, total, `decreasing`, `removed_current` y `rejected_kept`. La lectura de RAM, la detección de muertes y los encuentros no lo usan.

## Listas de etapas reutilizables

Sirven para llevar las mismas etapas de una partida a otra o compartirlas. Es un formato propio, versionado e independiente de Definitive Game Data y de la copia «Guardar sesión…».

```json
{
  "format": "progressive-tracker-stage-list",
  "version": 1,
  "stages": [
    { "name": "Primer gimnasio", "cap": 20 },
    { "name": "Liga", "cap": 60 }
  ]
}
```

- **Contenido**: solo `format`, `version` y `stages` (nombre y límite, en orden). **No** incluye identificadores internos, etapa vigente, la opción de mostrar, muertes, encuentros, partidas, tokens ni rutas locales; es seguro compartirlo. El tracker no trae listas oficiales ni inventa datos.
- **Reglas**: hasta 64 etapas, nombres de 1 a 60 caracteres, límites enteros de 1 a 100; los límites decrecientes se permiten y se avisan. Tamaño máximo del archivo: 32 KB. Se rechaza cualquier campo que no sea de este formato, un `version` mayor que 1 (de un tracker más nuevo), un JSON dañado y una lista vacía.
- **Exportar**: incluye la lista **guardada** (no el borrador). En la aplicación de escritorio se abre «Guardar como» (`limites-de-nivel.json` sugerido, sin nombre de partida); en un navegador se descarga el archivo. Es de solo lectura: no cambia nada.
- **Importar**: 1) elige el archivo; 2) se muestra una vista previa con nombres, límites, orden y advertencias, **sin cambiar nada**; 3) si la partida ya tiene etapas hay que marcar «Entiendo que se reemplazará la lista actual» (la lista se reemplaza entera, no se mezcla); 4) se aplica con la orden atómica `level_caps_set`. Se crean identificadores nuevos, **no se elige ninguna etapa vigente** (se indica cuál era la anterior) y la opción de mostrar los límites de la partida no cambia. Si falla, la lista anterior queda intacta y la vista previa permanece para reintentar o cancelar. Cancelar, Esc o cerrar no cambian nada.
- **Cambios sin guardar**: con un borrador sin guardar en el editor de etapas, importar queda desactivado (con la explicación) para no descartarlo en silencio. Si el borrador aparece o la lista de la partida cambia mientras se revisa la vista previa, la importación se rechaza.
- Cada partida y juego tiene su propia lista; importar en una no afecta a las demás. La exportación del escritorio usa la acción nativa `save_export('level_caps')`; Soul Link, OBS, la RAM y Definitive Game Data no cambian.

## Propuesta de Definitive Randomizer

Si los [datos importados de Definitive Randomizer](DEFINITIVE_GAME_DATA.md) incluyen el estado de su parche **Player Level Caps**, Progreso muestra una **propuesta**. Son los límites que ese parche aplica en la ROM exportada (bloquea la experiencia y el Caramelo Raro por encima del límite): una **restricción mecánica del juego**, no las etapas del desafío. El tracker nunca los aplica por su cuenta y no sabe qué puntos ha completado el jugador.

- **Importar los datos no cambia los límites.** La tarjeta «Propuesta de Definitive Randomizer» resume cuántos puntos hay y entre qué niveles.
- **Revisar propuesta…** abre una vista previa con cada punto, su nivel, el nombre del catálogo del Randomizer (o la condición, si no tiene nombre), la comparación fila a fila con las etapas actuales y los datos técnicos: productor, juego, estado de las dos copias del parche, cómo se evalúa, huellas y hash de la tabla.
- **Aceptar** copia los puntos como etapas de esta partida. Si ya había etapas, hay que marcar «Entiendo que se reemplazarán las etapas actuales»; la lista se reemplaza entera, no se mezcla. Se crean identificadores nuevos, **ninguna etapa queda vigente** (se indica cuál era la anterior) y la opción de mostrar los límites no cambia.
- **Etapa final de Nv. 100**: opcional y desmarcada. Añade «Después del último punto (techo del parche)». No es un punto del parche, sino su techo; al marcarla o desmarcarla la confirmación se pide de nuevo.
- **Conservar los límites actuales** (o Esc) cierra sin cambiar nada. **Descartar propuesta** la aparta sin tocar las etapas; «Volver a mostrarla» la recupera.
- **Cambios sin guardar**: con un borrador en el editor de etapas no se puede revisar la propuesta. Si durante la revisión cambia la partida, el juego, los datos importados o la lista de etapas, la propuesta deja de poder aceptarse y el servidor también la rechaza.
- Solo un parche **instalado** en las dos copias y con la misma tabla genera propuesta. Los demás estados (no detectado, no reconocido, copias que no coinciden, formato anterior), un bloque no válido o de una versión más nueva solo se informan. Un parche con más de 64 puntos se rechaza entero: **no se recorta**.
- **Retirar los datos importados no borra las etapas aceptadas** ni su procedencia.

La procedencia se guarda en un archivo aparte por partida y juego (`…-level-caps-source.json`, junto al registro de la aventura), con escritura atómica. El bloque `level_caps` versión 1 y el formato de las listas de etapas no cambian, de modo que una partida sigue abriéndose con versiones anteriores del tracker.

```json
{
  "format": "progressive-tracker-level-caps-source",
  "version": 1,
  "accepted": {
    "source": "definitive-game-data", "blockVersion": 1,
    "producer": {"id": "DefinitiveRandomizer", "version": "…"}, "game": "Ultra Sun 1.0",
    "dataFingerprint": "…", "capsFingerprint": "…", "tableSha256": "…",
    "checkpoints": 21, "finalStage": false, "listRevision": "…", "acceptedAt": "2026-11-12T05:00:00+00:00"
  },
  "dismissed": null
}
```

`listRevision` identifica la lista tal como quedó al aceptar; si después se edita a mano, Progreso indica que ya no es la propuesta. Un archivo dañado se informa y no impide cargar la partida; uno de una versión más nueva se conserva sin tocar.

| Acción (`POST /api/command`) | Cuerpo | Efecto |
|---|---|---|
| `level_caps_accept_proposal` | `game`, `dataFingerprint`, `capsFingerprint`, `tableSha256`, `listRevision`, `finalStage` (booleano) y `replace` (booleano) | Sustituye la lista por los puntos de la propuesta **cargada en el servidor** (el cliente no envía etapas). Se rechaza si algo de lo revisado ya no coincide o si falta `replace` habiendo etapas. |
| `level_caps_dismiss_proposal` | Los mismos identificadores y `dismissed` (booleano) | Aparta o recupera la propuesta. No toca las etapas. |

El resumen `level_caps` añade `revision` (huella corta de la lista guardada) y el estado incluye `level_caps_source` (`accepted`, `dismissed`, `matchesCurrent`, `error`).

## Datos dañados y versiones futuras

- Un bloque `level_caps` dañado **no** pone en cuarentena el registro: se aparta sin cambios en `level_caps_rejected` para revisarlo, el resto (muertes, encuentros, rutas y marcas) se carga normalmente y se muestra un aviso. Se pueden configurar límites nuevos.
- Un bloque con `version` mayor que 1 (de un tracker más nuevo) se conserva intacto, no se modifica y se informa como `unsupported`.
- Si el archivo completo no se puede leer, se aplica la recuperación habitual desde `.bak`.

## Compatibilidad

Soul Link comparte solo los campos de progreso de su lista (`schema_version: 1` sin cambios): los límites no se envían al compañero. El estado público de OBS, la lectura de RAM, los datos de Definitive Game Data que usa el tracker y los CSV de pk3DS no cambian. La copia **Guardar sesión…** incluye los límites dentro de `progress`.
