# Catálogos de nombres

Nombres obtenidos de PKHeX, proyecto de kwsch y colaboradores.
Se incluyen sus recursos y licencia GPL-3.0 en LICENSE.txt.
Los nombres son etiquetas por ID; no describen los cambios del randomizer.

Recursos descargados el 8 de octubre de 2026 desde:
https://github.com/kwsch/PKHeX

- PKHeX.Core/Resources/text/other/es/text_Species_es.txt
- PKHeX.Core/Resources/text/other/es/text_Moves_es.txt
- PKHeX.Core/Resources/text/other/es/text_Abilities_es.txt
- PKHeX.Core/Resources/text/items/text_Items_es.txt

Se conservan los índices originales, incluida la entrada cero.

Lugares: PKHeX.Core/Resources/text/locations/gen7/text_sm_*_es.txt (kwsch/PKHeX, GPL-3.0). Decodificación MetLocation/EggLocation/MetLevel/MetDate: PKHeX.Core/PKM/PK7.cs.

Catálogo de movimientos 0.13: PokeAPI/pokeapi, data/v2/csv/{moves,move_changelog,move_names,move_flavor_text,type_names,version_groups,languages}.csv.
Descripciones españolas de USUM (o la última versión anterior disponible), estadísticas de referencia y enlace de consulta a WikiDex.
PP gen7: kwsch/PKHeX, PKHeX.Core/Moves/MoveInfo7.cs (GPL-3.0).
Rutas: IDs Met0 de Locations7.cs y etiquetas de las tablas gen7 incluidas; contraste con https://www.wikidex.net/wiki/Alola.
No se copian explicaciones extensas de WikiDex. Descarga de fuentes: 8 de octubre de 2026.

0.14: orden de rutas inspirado en la lista umoon de Bassel-T/nuzlocke.app/src/lib/data/routes.json.
Las subzonas se agrupan manteniendo todos los IDs PK7. Las zonas no incluidas en la referencia
se intercalan próximas a sus áreas. Tipos de especies y formas: PKHeX personal_uu / PersonalInfo7.
Tabla de tipos: PokeAPI data/v2/csv/type_efficacy.csv. Interfaz de análisis y reglas de cobertura:
referencia wavebeem/pkmn.help, src/misc/data-matchups.ts y data-types.ts; licencia MIT incluida.

## Tipografía de la interfaz
Oxanium — The Oxanium Project Authors.
https://github.com/google/fonts/tree/main/ofl/oxanium
Fuente original sin modificar, licencia SIL Open Font License 1.1 en web/fonts/OFL.txt.

## Perfiles y candidatos de combate 0.18
https://github.com/kcblack42/Citra-Tracker-v2/blob/main/citra-updater.py
getGame/getaddresses y hpnum de generación 7. Consulta 2026-10-09.
Base de equipo compartida US/UM 0x33F7FA44. Candidatos sin validar con el usuario.


## Preparación Gen6 experimental (X/Y y ORAS)

- Nombres de lugares (Kalos y Hoenn): recursos españoles de PKHeX `PKHeX.Core/Resources/text/locations/gen6/text_xy_{00000,30000,40000,60000}_es.txt`; distribuidos con `LICENSE.txt` (GPL-3.0).
- Direcciones candidatas X/Y `0x08CE1CE8` y ORAS `0x08CF727C`, lectura de bloques PK6: `kcblack42/Citra-Tracker-v2/citra-updater.py` (`getaddresses`, `Pokemon6`, constantes de slots), consultado 2026-10-09.
- No existen datos propios que verifiquen todavía boxes PC ni PS durante batalla Gen6. Ver `docs/COMPATIBILIDAD_GEN6.md`.
