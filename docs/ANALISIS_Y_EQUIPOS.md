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
