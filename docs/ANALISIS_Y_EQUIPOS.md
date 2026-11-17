# Análisis avanzado y equipos

Las herramientas de esta página son informativas: leen los datos que el Tracker ya tiene y no escriben en la RAM, la ROM ni la partida guardada.

## Gráfico de efectividad defensiva

En **Análisis → Defensa del equipo**, **Presentación** alterna entre **Gráfico** y **Tabla**. La tabla detallada y la simplificada siguen disponibles.

El equipo analizado aparece arriba. El resumen destaca amenazas, resistencias y cobertura pendiente; las barras usan el rojo y los neutros del Tracker. **Cobertura ofensiva del equipo** abre los movimientos y multiplicadores sin ocupar toda la pantalla de entrada.

El gráfico dibuja una barra horizontal por cada uno de los 18 tipos atacantes y reparte a los integrantes del equipo en seis grupos:

| Grupo | Significado |
| --- | --- |
| ×4 | Muy débiles (×4 o más) |
| ×2 | Débiles (más de ×1 y menos de ×4, incluidas las reducciones de Filtro o Roca Sólida) |
| ×1 | Neutrales |
| ×½ | Resisten |
| ×¼ | Resisten mucho (×¼ o menos) |
| ×0 | Inmunes |

Junto a cada barra se muestran los recuentos generales (débiles, resisten, inmunes y neutrales). Al abrir un tipo se listan los integrantes de cada grupo con su multiplicador exacto.

**Orden** permite ordenar por orden de tipos, mayor debilidad, mayor resistencia (resistencias e inmunidades) o alfabéticamente, y se aplica también a la tabla. **Habilidades compatibles** activa o desactiva las habilidades que el análisis reconoce.

Los multiplicadores proceden del mismo motor que la tabla (`web/analysis.js`); `web/insights.js` solo agrupa y ordena sus resultados.

## Vista de análisis de cajas

En **Cajas**, el selector **Vista** alterna entre **Vista normal** (la de siempre, con Living Dex) y **Vista de análisis**. El análisis abre una galería de **Tarjetas**; **Presentación → Tabla** conserva una alternativa tabular. Ambas son de solo lectura.

Cada tarjeta muestra sprite, apodo y especie, nivel conocido, tipos, habilidad, naturaleza, BST, seis barras base, movimientos y ubicación. Al pulsar un Pokémon se abre la ficha del ejemplar leído.

- **Estadísticas base y BST** pertenecen a la especie y forma, sin aplicar naturaleza. Se resuelven con DGD de la forma exacta, CSV de especie normal o una caché incluida de referencia X/Y, ORAS o USUM. La tarjeta identifica la procedencia. La referencia no describe cambios de una ROM randomizada; si tampoco conoce la forma, muestra «No disponible». BST requiere las seis bases.
- **Estadísticas actuales** pertenecen al ejemplar y se muestran por separado en **Valores actuales**, cuando existen (active **Incluir equipo actual**). La naturaleza aparece aparte y no modifica las barras base. El nivel y las estadísticas actuales de PC siguen sin leerse.
- **Filtros:** tipo, habilidad, **Solo disponibles** (excluye muertos y huevos), búsqueda por nombre, habilidad, movimientos, objeto u origen, y la caja elegida o todas las cajas leídas.
- **Orden:** BST, PS, Ataque, Defensa, Ataque Especial, Defensa Especial y Velocidad base, nivel actual, tipo o nombre, en sentido descendente o ascendente. Los valores desconocidos quedan siempre al final.

La línea de estado distingue cajas leídas y lectura parcial. Se muestran como máximo 240 tarjetas o filas, con aviso para afinar filtros; las cajas no leídas no se consideran vacías.

### Aplicar mega como simulación

Una megapiedra compatible permite **Aplicar mega** en cajas, análisis y equipo virtual. Cambian los datos usados para el análisis (forma, bases, tipos y habilidad); **Quitar mega** vuelve a la lectura original. Los sprites mega y sus especies normales están incluidos para trabajar sin conexión.

La proyección utiliza DGD de la forma exacta cuando existe y referencia por juego cuando no; el botón informa de esa procedencia. No demuestra que el jugador pueda activar la mega ni modifica el juego. No fabrica PS ni estadísticas actuales. La comparación **Actual** mantiene el equipo leído; **Virtual** puede incluir la simulación. Las selecciones mega duran la sesión de análisis, no se añaden al archivo de equipos guardados y se reinician al cambiar de juego o vista de compañero. No se validan reglas de combate como el número de megas permitidas.

## Asistente de equipos

En **Análisis**, el selector superior alterna entre **Equipo actual** (el análisis de siempre) y **Asistente de equipos**. El asistente permite armar equipos virtuales de hasta seis integrantes con los Pokémon que tienes. Es una simulación: no cambia el equipo dentro del juego ni envía órdenes al emulador.

### Candidatos

- Pokémon del equipo actual y de las cajas leídas. Cada ejemplar aparece una sola vez, aunque una lectura antigua de cajas lo repita.
- Los Pokémon marcados como muertos se excluyen salvo que actives **Incluir muertos**. Los huevos no se ofrecen.
- Los datos que no proceden de una lectura en vivo y verificada (sin conexión, o cajas sin verificar en esta conexión) se etiquetan como **Lectura guardada**.
- Se puede buscar por apodo o especie, filtrar por tipo y procedencia, y ordenar por ubicación, BST, cada estadística base, nivel, tipo o nombre.

### Selección

Pulsa un hueco para abrir sugerencias visuales. **Elegir con sugerencias** abre la misma guía, sin incorporar nada automáticamente. Cada opción muestra sprite, tipos, BST, motivo, beneficios y costes; **Ver motivos** amplía la explicación. **Elegir** añade solo ese ejemplar y propone el siguiente paso; puedes cerrar en cualquier momento. **Ver más opciones** amplía la lista, incluidas alternativas cuyos riesgos también se evalúan.

**Explorar Pokémon disponibles** abre búsqueda, filtros y ordenación. Pulsar un candidato lo añade o quita. **Usar equipo actual** respeta el filtro de muertos y **Vaciar** empieza de cero. Los integrantes se pueden subir, bajar o quitar; los ausentes conservan su hueco. **Guardar y abrir equipos** despliega las acciones de persistencia.

### Cobertura

El informe se recalcula con cada cambio:

- **Debilidades compartidas:** tipos a los que son débiles dos o más integrantes, con quiénes lo resisten o son inmunes.
- **Tipos sin resistencia ni inmunidad**, **Resistencias** e **Inmunidades**.
- **Sin ataque supereficaz:** tipos contra los que ningún movimiento conocido es supereficaz.
- **Tipos que resisten todos tus ataques.**
- **Posibles redundancias:** tipos repetidos entre integrantes y tres o más ataques del mismo tipo.
- El gráfico de defensa por tipo y la cobertura ofensiva por tipo del análisis normal.

La cobertura ofensiva usa los movimientos que cada Pokémon conoce ahora. Sin movimientos conocidos, el informe lo indica en lugar de suponer cobertura.

Un equipo virtual pertenece a un juego: al cambiar de juego o abrir la vista del compañero se empieza un borrador nuevo.

### Equipos guardados

Un equipo virtual se puede guardar con un nombre (hasta 60 caracteres). Las acciones son **Guardar equipo** / **Guardar cambios**, **Renombrar**, **Duplicar**, abrir desde la lista **Equipo guardado** y **Eliminar…**, que pide confirmación. Al abrir otro equipo con cambios sin guardar también se pregunta antes de descartarlos.

- Se guardan en el equipo local, en un archivo por partida y por juego (`state<juego>-virtual-teams.json`, junto al progreso de esa partida). Otra partida u otro juego no los ven. Como máximo 50 equipos.
- Cada equipo conserva nombre, hasta seis integrantes en su orden, fechas de creación y modificación, juego y partida de procedencia.
- De cada integrante solo se guarda su identificador de ejemplar (el mismo que usa el registro de muertes, estable al evolucionar, cambiar de apodo o de caja), la especie y el apodo. No se guardan credenciales ni datos de Soul Link.
- Los equipos guardados no forman parte del estado que se comparte con Soul Link, OBS o la exportación de sesión, y no se envían a Internet.
- Al abrir un equipo, cada integrante se busca en el equipo y en las cajas leídas. Si no aparece se muestra como **No localizado**: conserva su nombre guardado, no cuenta en la cobertura y nunca se sustituye por otro Pokémon. Si vuelve a leerse, se localiza de nuevo. Si evolucionó, se indica qué especie era.
- El archivo tiene `schema_version` 1. Un archivo dañado se aparta en una copia con nombre único y se empieza una lista nueva. Si no se puede preservar el original, queda en solo lectura y se avisa. Un archivo de una versión más nueva también se conserva sin cambios y queda en solo lectura.
- En la vista del compañero no se cargan ni se guardan equipos.

Al abrir o editar una composición aparece **Comparación con el equipo actual**, con recuentos de integrantes localizados, balance defensivo, cobertura y ganancias/pérdidas. Funciona también con equipos incompletos; los ausentes conservan su hueco y se avisa de que no entran en el cálculo. «Usar equipo actual» respeta la opción de incluir muertos.

API local (requiere el token de sesión para escribir): `GET /api/teams` y `POST /api/teams` con `action` `save`, `rename`, `duplicate` o `delete` (`confirm: true`). GET entrega un `scope` efímero que POST debe devolver: una solicitud anterior a un cambio de partida o juego se rechaza con 409. Si no se pudieron cargar los equipos, el guardado queda bloqueado; reabrir el asistente permite reintentar. Este identificador no se guarda ni se comparte en Soul Link.

### Recomendaciones

Con al menos un integrante, el informe empieza con una lectura del equipo y con sugerencias de cambio. Son reglas fijas sobre los datos del Tracker: no usan servicios externos y, con los mismos datos, dan siempre el mismo resultado.

**Medidas separadas** (sirven para comparar cambios, no son una nota del equipo):

| Medida | Qué cuenta |
| --- | --- |
| Balance defensivo | Por cada tipo atacante suma resistencias (×½: 1; ×¼: 1,5) e inmunidades (2) y resta debilidades (×2: 1; ×4: 2). Resta 2 más por cada tipo al que son débiles dos o más integrantes y nadie resiste |
| Tipos con ataque supereficaz | Cuántos de los 18 tipos reciben un ataque supereficaz de algún movimiento conocido |
| Redundancias | Integrantes que repiten tipo y ataques del mismo tipo a partir del tercero |
| Tipos distintos | Tipos diferentes entre los integrantes |

**Lectura defensiva y ofensiva:** frases como «3 integrantes son débiles a Fuego y ninguno lo resiste ni es inmune», «2 integrantes son débiles a Tierra; Skarm es inmune» o «Ningún Pokémon del equipo dispone de un ataque supereficaz contra Eléctrico».

**Incorporaciones posibles** (si quedan espacios) y **Sustituciones posibles:** cada candidato de las cajas o del equipo se prueba como incorporación y como sustituto de cada integrante, de uno en uno. Cada sugerencia indica:

- A quién se propone sustituir y a quién incorporar.
- El motivo: inmunidades nuevas, resistencias a tipos que nadie resistía, debilidades compartidas que se reducen, cobertura supereficaz nueva.
- Lo que se perdería o empeoraría: debilidades compartidas nuevas o mayores, inmunidades o resistencias perdidas, cobertura perdida.

Las recomendaciones principales requieren beneficio y saldo positivo. Cada candidato aparece una vez entre las sustituciones. **Añadir al borrador**, **Aplicar al borrador** y **Elegir** requieren una decisión explícita y solo cambian el equipo virtual. La comparación muestra métricas emparejadas y resúmenes de mejoras/riesgos, con el detalle completo disponible.

El orden principal agrupa beneficios cercanos de cobertura y sinergia en bandas de dos puntos (`defensa + 1,5 × cobertura ofensiva`). Una banda superior siempre prevalece. Dentro de una banda, la calidad combina BST, distribución útil para los movimientos conocidos, aguante físico/especial, Velocidad y nivel disponible; después desempatan la cobertura exacta y redundancias. Esto evita anteponer una preevolución débil a una opción equivalente más sólida, sin convertir el sistema en «el mayor BST gana».

La calidad secundaria usa `0,35 × BST + 1,2 × perfil de bases + 0,1 × nivel conocido`. El perfil promedia ataque útil según categoría, raíz de PS×Defensa, raíz de PS×Defensa Especial y Velocidad; no suma un ataque que ningún movimiento use. Sin bases suficientes no se estima calidad. Cuando ambas composiciones tienen bases completas, el detalle muestra sus promedios antes/después.

Se evalúan hasta 966 candidatos (32 cajas y seis puestos de equipo), sin búsqueda de combinaciones múltiples. No se sugieren muertos ni huevos. No calcula daño, estadísticas actuales hipotéticas, efectos de objetos ni reglas de la partida. Las bases de referencia y los pesos son orientativos, especialmente con ROMs randomizadas.

### Asesor de movimientos

Debajo de las recomendaciones, el asesor analiza los movimientos que conocen los integrantes del equipo virtual:

- **Ataques por tipo:** los movimientos ofensivos agrupados por el tipo con el que golpean (con habilidades compatibles, por ejemplo Piel Feérica convierte los ataques de tipo Normal).
- **Redundancias:** tipos con tres o más ataques en el equipo y Pokémon con dos o más ataques del mismo tipo.
- **Tipos enemigos con poca cobertura:** tipos sin ningún ataque supereficaz y tipos cubiertos por un único movimiento.
- **Tipos de movimiento recomendados:** tipos que el equipo todavía no usa y que añadirían cobertura supereficaz, ordenados por cuánta cobertura nueva aportan. Por ejemplo: «Tienes 4 ataques de tipo Acero. Te vendría bien un movimiento de tipo Tierra para mejorar la cobertura frente a Eléctrico».
- **Quién tiene sitio:** integrantes con espacios de movimiento libres.

Cada dato lleva su nivel de evidencia:

| Etiqueta | Significado |
| --- | --- |
| Movimiento conocido | Leído del Pokémon (RAM o lectura guardada) |
| Disponible en datos verificables | El Pokémon puede aprenderlo según datos importados de esta partida |
| Sugerencia genérica de tipo | Solo se recomienda un tipo de movimiento |
| Información no disponible | No hay datos de aprendizaje para esta partida |

El Tracker no incluye tablas de aprendizaje (nivel, MT o tutores) y Definitive Game Data v1 no las exporta. Además, una ROM randomizada puede tener aprendizajes distintos del juego original. Por eso hoy el asesor solo sugiere tipos y nunca afirma que un Pokémon pueda aprender un movimiento concreto. La categoría «Disponible en datos verificables» se activa únicamente si un Pokémon del estado trae la lista `learnable_moves`, reservada para una importación futura que incluya aprendizajes.

El asesor no cambia movimientos en el juego.
