# Análisis avanzado y equipos

Las herramientas de esta página son informativas: leen los datos que el Tracker ya tiene y no escriben en la RAM, la ROM ni la partida guardada.

## Gráfico de efectividad defensiva

En **Análisis → Defensa del equipo**, **Presentación** alterna entre **Gráfico** y **Tabla**. La tabla detallada y la simplificada siguen disponibles.

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

En **Cajas**, el selector **Vista** alterna entre **Vista normal** (la de siempre, con Living Dex) y **Vista de análisis**. La vista de análisis es una tabla de solo lectura: no mueve Pokémon ni envía órdenes al juego.

Cada fila muestra sprite, apodo y especie, nivel, tipos, habilidad, naturaleza, las seis estadísticas base, el BST, los movimientos conocidos y la caja y posición originales. Al pulsar un Pokémon se abre su ficha.

- **Estadísticas base y BST** son datos de la especie y solo existen si la partida importó Definitive Game Data o el CSV de estadísticas de pk3DS. Sin esos datos se muestra «No disponible»; el BST solo se calcula cuando están las seis estadísticas.
- **Estadísticas actuales** son las del ejemplar en la partida. Aparecen debajo de la base, marcadas como «actual», y solo se conocen para el equipo (active **Incluir equipo actual**). El nivel tampoco se lee en las cajas.
- **Filtros:** tipo (primario o secundario), habilidad, **Solo disponibles** (excluye muertos y huevos), búsqueda por apodo o especie, y la caja elegida o todas las cajas leídas con **Mostrar todas las cajas leídas**.
- **Orden:** BST, PS, Ataque, Defensa, Ataque Especial, Defensa Especial y Velocidad base, nivel actual, tipo o nombre, en sentido descendente o ascendente. Los valores desconocidos quedan siempre al final.

La línea de estado indica cuántas cajas se han leído. Si faltan cajas, la lectura sigue en curso o las cajas no están verificadas, se avisa de que el resultado es parcial. La tabla dibuja como máximo 240 filas e indica cuántas quedan fuera.

## Asistente de equipos

En **Análisis**, el selector superior alterna entre **Equipo actual** (el análisis de siempre) y **Asistente de equipos**. El asistente permite armar equipos virtuales de hasta seis integrantes con los Pokémon que tienes. Es una simulación: no cambia el equipo dentro del juego ni envía órdenes al emulador.

### Candidatos

- Pokémon del equipo actual y de las cajas leídas. Cada ejemplar aparece una sola vez, aunque una lectura antigua de cajas lo repita.
- Los Pokémon marcados como muertos se excluyen salvo que actives **Incluir muertos**. Los huevos no se ofrecen.
- Los datos que no proceden de una lectura en vivo y verificada (sin conexión, o cajas sin verificar en esta conexión) se etiquetan como **Lectura guardada**.
- Se puede buscar por apodo o especie, filtrar por tipo y procedencia, y ordenar por ubicación, BST, cada estadística base, nivel, tipo o nombre.

### Selección

Pulsa un candidato para añadirlo y vuelve a pulsarlo para quitarlo. **Usar equipo actual** copia el equipo de la partida y **Vaciar** empieza de cero. Cada integrante se puede subir, bajar o quitar. Con seis integrantes hay que quitar uno para añadir otro.

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
- El archivo tiene `schema_version` 1. Un archivo dañado se aparta con el sufijo `.corrupt-<fecha>` y se empieza una lista nueva. Un archivo de una versión más nueva se conserva sin cambios y la lista queda en solo lectura.
- En la vista del compañero no se cargan ni se guardan equipos.

API local (requiere el token de sesión para escribir): `GET /api/teams` y `POST /api/teams` con `action` `save`, `rename`, `duplicate` o `delete` (`confirm: true`).

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

Solo se muestran cambios con algún beneficio y cuyo saldo conjunto es positivo, ordenados por ese saldo; cada candidato aparece una vez entre las sustituciones. **Añadir al borrador** y **Aplicar al borrador** modifican únicamente el equipo virtual. **Completar con sugerencias** rellena los espacios libres con la mejor incorporación de cada paso y se detiene cuando ninguna aporta; el resultado es un borrador que se puede editar antes de guardar.

Límites deliberados: no se sugieren Pokémon muertos ni huevos; se comparan como máximo 300 candidatos y nunca combinaciones de varios cambios a la vez; el BST no interviene. Las sugerencias no consideran niveles, estadísticas, objetos ni las reglas de la partida, así que son opciones para valorar y no «el mejor equipo».
