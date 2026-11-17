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
