# Límites de nivel por partida

Los límites de nivel son **manuales**: el jugador define cada etapa y su nivel máximo. El tracker no incluye límites oficiales ni predeterminados de ningún juego, romhack o desafío, y no los deduce de la RAM. Los avisos son informativos: no impiden subir de nivel ni cambian nada en la partida.

## En la interfaz

- **Progreso** (barra de secciones): la etapa vigente con su límite, «Etapa N de M» y una barra de avance; «Etapa anterior» y «Siguiente etapa»; un selector para elegir la etapa vigente (o ninguna); la casilla «Mostrar el límite en la cabecera y en las fichas», y el equipo comparado con el límite.
- **Etapas**: tabla para añadir, renombrar, cambiar el nivel, reordenar (↑ ↓) y eliminar. Los cambios son un borrador hasta pulsar «Guardar cambios», que aplica la lista entera de una vez; «Descartar» la deja como estaba. Cada error aparece junto a su fila. Un límite más bajo que el de la etapa anterior se avisa, pero se puede guardar.
- **Cabecera**: un indicador «Límite Nv. N · etapa», con «· X por encima» si algún Pokémon del equipo lo supera; «Sin etapa vigente» si hay etapas pero ninguna elegida. Al pulsarlo se abre Progreso. No aparece si la partida no tiene etapas o si se ocultan los límites.
- **Fichas del equipo**: «+N sobre el límite» en los Pokémon que lo superan (los huevos no cuentan).
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

## Datos dañados y versiones futuras

- Un bloque `level_caps` dañado **no** pone en cuarentena el registro: se aparta sin cambios en `level_caps_rejected` para revisarlo, el resto (muertes, encuentros, rutas y marcas) se carga normalmente y se muestra un aviso. Se pueden configurar límites nuevos.
- Un bloque con `version` mayor que 1 (de un tracker más nuevo) se conserva intacto, no se modifica y se informa como `unsupported`.
- Si el archivo completo no se puede leer, se aplica la recuperación habitual desde `.bak`.

## Compatibilidad

Soul Link comparte solo los campos de progreso de su lista (`schema_version: 1` sin cambios): los límites no se envían al compañero. El estado público de OBS, la lectura de RAM, Definitive Game Data y los CSV de pk3DS no cambian. La copia **Guardar sesión…** incluye los límites dentro de `progress`.
