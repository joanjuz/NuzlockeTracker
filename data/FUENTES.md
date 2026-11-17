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

## Iconos de objetos (OBS)

- `data/ItemSprites.json`: índice interno de objeto Gen6/Gen7 → nombre de sprite, generado con `tools/build_item_sprites.py` a partir de `items.csv` e `item_game_indices.csv` de PokeAPI (https://github.com/PokeAPI/pokeapi, licencia en `data/LICENSE_PokeAPI.md`).
- Las imágenes no se distribuyen: se descargan bajo demanda desde https://github.com/PokeAPI/sprites (`sprites/items/`) a la caché local del usuario, igual que los sprites de Pokémon.

## Bases de especies y simulación mega — caché local Gen6/Gen7

`SpeciesReference_Gen6Gen7.json` es una referencia **incluida con la aplicación**:
no hace peticiones al abrir cajas ni análisis y funciona sin conexión. No pretende
describir una ROM randomizada. La prioridad es Definitive Game Data de la forma
exacta, CSV de especie normal si existe y después esta referencia. Un CSV sin
columna de forma no se aplica a formas regionales o mega. Las formas desconocidas
no reutilizan silenciosamente estadísticas de la especie normal.

- Bases, tipos, habilidades e índices internos de forma: `kwsch/PKHeX`, commit
  [`6c9583883c7551ac74a4b74180cead249d4277b8`](https://github.com/kwsch/PKHeX/tree/6c9583883c7551ac74a4b74180cead249d4277b8),
  `PKHeX.Core/Resources/byte/personal/personal_xy`, `personal_ao`, `personal_uu`.
  Se distinguen X/Y, ORAS y USUM, incluidos cambios entre generaciones. Formato
  contrastado con `PersonalInfo6XY.cs`, `PersonalInfo6AO.cs`, `PersonalInfo7.cs`:
  seis bases en offsets 0–5 (Velocidad precede a At. Esp. en binario), tipos 6–7,
  habilidades 0x18–0x1A, índice de formas 0x1C y cantidad 0x20. GPL-3.0 del proyecto,
  ya conservada en `LICENSE.txt`; autoría kwsch y colaboradores.
- Asociación de las 47 megapiedras de Gen6/Gen7 a especie y forma:
  `smogon/pokemon-showdown`, commit
  [`f827a1d41064e0dec4c19c6ea0394fcf0c23479c`](https://github.com/smogon/pokemon-showdown/blob/f827a1d41064e0dec4c19c6ea0394fcf0c23479c/data/items.ts),
  campos `megaStone`, `num` y `gen` de `data/items.ts`. Solo se conservan asociaciones
  de generaciones hasta 7 y se exige que la forma exista en el juego. Licencia MIT
  y atribución Guangcong Luo y colaboradores en `LICENSE_PokemonShowdown.txt`.
- IDs opcionales de sprites mega: `PokeAPI/pokeapi`, commit
  [`8d8a49d9295bbc951d882004570ca496866fd9d8`](https://github.com/PokeAPI/pokeapi/blob/8d8a49d9295bbc951d882004570ca496866fd9d8/data/v2/csv/pokemon.csv),
  `pokemon.csv`. Se guardan solo identificadores, sin imágenes ni descarga nueva
  de sprites. Licencia BSD-3-Clause existente en `LICENSE_PokeAPI.md`.

Generador reproducible stdlib: `python tools/build_species_reference.py`.
Cada descarga está fijada a commit y su URL/SHA-256 figura en el JSON. La caché
contiene 922 formas X/Y, 949 ORAS y 1116 USUM; no hay dependencia de PokeAPI en
tiempo real. La naturaleza no modifica estas bases. Las estadísticas actuales
del ejemplar permanecen separadas y no se calculan al simular una mega.

Una megapiedra equipada permite ofrecer una **proyección informativa** de esa
forma, no prueba que el jugador pueda megaevolucionar ni activa nada en el juego.
La forma importada DGD prevalece para bases, tipos y habilidad; si falta, la
proyección queda marcada `reference_only` y la UI debe advertir que es referencia.

Los sprites pequeños de las 47 formas mega y sus 45 especies normales están
incluidos para que esta simulación no dependa de descargas al pulsar el botón.
Procedencia: PokeAPI/sprites, commit `c0542f7c51215d9672439012838c99f520596cbd`,
directorio `sprites/pokemon/`. Son 92 PNG (102 324 bytes en total).
URLs y SHA-256 por archivo en `MegaSpriteSources.json`; actualización explícita
mediante `python tools/cache_mega_sprites.py`, nunca al abrir la interfaz.
El repositorio de sprites permite descargar sus recursos para aplicaciones;
se conserva la atribución a PokeAPI y a sus colaboradores. Los personajes e imágenes
de Pokémon pertenecen a Nintendo, Creatures y GAME FREAK; esta distribución no
implica patrocinio ni autorización de sus titulares.
