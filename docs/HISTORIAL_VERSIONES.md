# 0.20 — Ultra Sol en combate, sprites y cambio rápido de juego

Ultra Sol 1.0: la captura real confirma el mismo bloque de PS de combate que
Ultra Luna (`0x3000975C`, stride 816). Se activa la lectura en vivo con la misma
validación estricta de equipo: especie, PS máximos, nivel y habilidad.

Sprites: las tarjetas del equipo ahora usan el mismo fallback remoto que cajas y
rutas. Si un PNG todavía no está en `data/sprites`, se intenta PokeAPI y solo se
muestra el número si también falla la red.

Cambio Ultra Sol ↔ Ultra Luna: una nueva solicitud de Conectar/Desconectar cancela
inmediatamente una búsqueda de RAM anterior. Así el servidor no queda bloqueado
hasta 60–90 s buscando el juego que ya se cerró. No hace falta reiniciar el servidor.

# 0.19 — PS de combate y búsqueda dinámica

Ultra Luna 1.0: PS de combate activados cuando el equipo completo coincide en
especie, PS máximos, nivel y habilidad, y dos lecturas son iguales. Tu captura
confirmó Misa 219 → 183 → 193, mientras la lectura habitual permanecía en 219.
Al salir de combate los bloques dejan de ser válidos y se usa la lectura normal.
La etiqueta PS de combate indica cuándo se usa esta fuente, también para Muertos.

Validado con la captura de un combate individual. Dobles, SOS, transformaciones,
cambios de habilidad u orden no están confirmados: si falla la comprobación del
equipo, se conserva la lectura normal. No se asignan PS a un Pokémon por aproximación.

Ultra Sol 1.0: búsqueda dinámica de estructuras PK7, sin depender de la dirección
fija de Luna. Probada con memoria simulada; falta confirmar con tu ROM.
Las cajas se aceptan tras encontrar Pokémon válidos; de lo contrario, el equipo
puede conectar y las cajas mostrarán Dirección de cajas sin validar.
Si falla: espera al resultado (hasta 90 segundos), usa ··· → Guardar diagnóstico
y envía diagnostico_conexion.json. El informe conserva la causa del fallo.
PS de combate de Ultra Sol siguen pendientes de su propia captura.

Conserva la carpeta runtime al actualizar con el tracker cerrado.

# 0.18 — Ultra Sol 1.0 y diagnóstico de combate

En Conexión elige Ultra Sun 1.0 antes de conectar. La base de equipo procede de
Citra-Tracker-v2, que agrupa Ultra Sun y Ultra Moon. Equipo y cajas conservan sus
validaciones de estructura/checksum. Falta confirmar la lectura con tu ROM.
Las rutas usan el catálogo compartido de Alola. Sol guarda su historial aparte en
runtime/state-ultra-sun-progress.json; Luna conserva state-progress.json.
La demo sigue siendo Ultra Luna.

## Captura de combate (Windows, sin GDB)
1. Abre la partida fuera de combate y ejecuta Diagnostico_Combate.bat.
2. Indica juego, Pokémon y PS máximos.
3. Entra en combate individual normal. Pausa Lime3DS en el menú de movimientos
   y escribe los PS actuales cuando la consola lo pida.
4. Reanuda, recibe daño o cura al MISMO Pokémon y pausa al terminar el turno.
   Introduce los nuevos PS. Repite con otro valor diferente al anterior.
5. Termina el combate, pausa fuera de él y completa la última captura.
6. Envía runtime/combate-FECHA-HORA.json (la consola indica la ruta completa).

No cambies de Pokémon ni uses transformaciones; evita aliados/SOS para esta prueba.
Reanuda Lime3DS manualmente al acabar. También se guarda informe si falla la captura.
Solo se lee RAM del juego. Los candidatos NO se aplican al tracker ni a Muertos.
Los PS en directo siguen pendientes de validar estas lecturas.
Conserva tu carpeta runtime al actualizar.

# 0.17 — Revivir y una interfaz más limpia

- Muertos incluye Revivir bajo cada Pokémon. Quita el registro y devuelve el color
  a los sprites de cajas y rutas. No modifica los PS del juego.
- Si sigue a 0 PS, espera una lectura válida con PS positivos antes de volver a
  registrar una muerte. Esta espera se conserva al cerrar y abrir la aplicación.
- Menos texto, sin subtítulos repetidos. Las notas de cálculo están en Qué incluye.
- Fuente Oxanium incluida para uso sin internet (licencia SIL OFL en web/fonts).

Actualización: cierra el tracker y copia tu carpeta runtime anterior a esta versión
para conservar Muertos y Miss. Inicio de demo en Linux: `bash Iniciar_Demo.sh`.

# 0.16 — Muertos y encuentros Miss

- Muertos registra la primera lectura válida de un Pokémon del equipo a 0 PS.
  No lo bloquea, no lo retira del equipo y no duplica el registro si vuelve a morir.
- Sus sprites en cajas y rutas aparecen en blanco y negro. El historial conserva
  la ficha del momento del registro y el origen incluso si ya no está en las lecturas.
- Cada ruta incluye Marcar Miss / Quitar Miss. Miss sustituye la silueta vacía;
  si hay otros Pokémon en esa ruta, conserva sus sprites y añade la marca.
- El historial se guarda en runtime/state-progress.json; la demo usa
  runtime/demo-state-progress.json por separado. Al actualizar, conserva estos archivos.
  Es un registro por carpeta del tracker; para otra aventura usa otra carpeta.
- Solo se detectan muertes que el tracker alcance a leer mientras está conectado.
  No puede recuperar una muerte pasada si el Pokémon ya fue curado antes de la lectura.

Demo sin emulador: `bash Iniciar_Demo.sh`. Para probar Muertos: Conexión →
Escenario → Daño y Pokémon debilitados. Volver a Equipo completo mantiene el registro.

# 0.15 — paleta roja, temas y defensa simplificada

En el menú ··· puedes elegir apariencia clara u oscura. La primera visita sigue el tema
 del sistema; la selección se conserva en este navegador y dirección local.
Paleta basada en #DF2531, blanco y negro, con variantes transparentes del rojo.
Rutas y cajas presentan sprites sin tarjetas de fondo, sobre una sombra circular.

En Análisis → Defensa del equipo → Vista de defensa, elige Simplificada para ver
solo el número de Pokémon débiles, resistentes e inmunes frente a cada tipo.
Usa las mismas habilidades y cálculos que la vista Por Pokémon; no cuenta neutrales.

Inicio en Linux sin emulador: `bash Iniciar_Demo.sh`. Extrae el ZIP en una carpeta nueva.

# 0.14 — orden de historia, análisis y cajas con sprites

Inicio de demo en Linux: `bash Iniciar_Demo.sh`. En Windows: Iniciar.bat para lectura real
o Iniciar_Demo.bat. Extrae en una carpeta nueva. No necesitas Node.js para usar el tracker.

## Rutas y navegación

La secuencia base es la lista umoon de Bassel-T/nuzlocke.app (src/lib/data/routes.json).
Respeta posiciones como Ruta 11 antes de Ruta 10 y Ruta 15 antes de Ruta 14.
Se añadieron las otras zonas del PK7 próximas a sus áreas y se unificaron subzonas:
Ciudad Hauoli, Colina Saltagua, Cueva Sotobosque, etc. Las 109 IDs originales se conservan
como IDs de asignación dentro de 90 tarjetas ordenadas, sin separar rutas numeradas de otras zonas.
No hay un límite de dos sprites por ruta: se muestran todos los Pokémon distintos registrados.
La demo muestra tres Pokémon en Ruta 1.

La Casa Æther y el Centro de Restauración de Fósiles aparecen en el orden de referencia,
pero comparten lugares registrados con otras áreas en PK7. Sus tarjetas no reciben una
atribución automática; el tooltip lo explica. El Inicial tampoco puede distinguirse de otras
capturas únicamente a partir del lugar de encuentro. No se inventan esas atribuciones.
Los lugares vacíos siguen reflejando las lecturas del equipo y cajas, no un historial completo.

Pulsar fuera de una ficha Pokémon/movimiento cierra esa ficha. Pulsar fuera del menú de opciones
lo cierra. Escape también permite cerrar los menús. Los detalles de movimiento conservan el
contexto del Pokémon al cerrarse.

## Análisis

La nueva pestaña tiene tres modos:
- Defensa del equipo: multiplicadores por tipo atacante, miembro del equipo y recuentos de
  debilidades, resistencias e inmunidades.
- Ataque: elige un Pokémon; se leen automáticamente sus movimientos y se muestra la mejor
  cobertura ofensiva por tipo defensor.
- Ataque doble: elige dos miembros distintos; se considera la mejor opción entre ambos repertorios.
  No representa dos golpes sumados ni multiplicados.

Puede mostrar defensores de un tipo o las 153 combinaciones de dos tipos además de los 18 simples.
Los movimientos de estado se excluyen de la cobertura ofensiva. Se contemplan Plancha Voladora,
Liofilización y Mil Flechas. La casilla de habilidades aplica las compatibles sin condiciones:
imunidades elementales, Levitación, Sebo, Ignífugo, Pompa, Piel Seca, Peluche (fuego), Superguarda,
Filtro/Roca Sólida/Armadura Prisma; en ataque, Intrépido y las conversiones de Normal de las Pieles.
No incluye clima, contacto, condiciones temporales, objetos, daño, STAB ni todas las habilidades.

Los tipos de especie y forma son de personal_uu de PKHeX; la tabla de tipos viene de PokéAPI.
La presentación y las reglas de cobertura se inspiran en wavebeem/pkmn.help.
El repertorio viene de RAM, pero su tipo proviene del catálogo de movimientos de referencia USUM.
Si el randomizer cambia tipos o categorías, se necesita el catálogo de la ROM para reflejarlos;
no se afirma que esos datos se hayan extraído de la ROM. El backend admite metadatos de catálogo.

## Cajas

Cada Pokémon tiene un sprite, su mote y debajo caja y posición. Pulsar abre su detalle.
Se conservan la búsqueda, lectura global y actualización de la caja seleccionada.
Los sprites de demo son locales; especies sin sprite local intentan cargar uno público como antes.

## Verificación y fuentes

71 pruebas Python pasan y 13 comprobaciones JavaScript de multiplicadores y cobertura.
Se comprobó además la lógica de interfaz: tres Pokémon por ruta, defensa, ataque doble,
apertura de detalles y cierre al pulsar fuera. La apariencia final debe revisarse en tu navegador.

Referencias:
- https://github.com/Bassel-T/nuzlocke.app/blob/main/src/lib/data/routes.json
- https://github.com/wavebeem/pkmn.help/blob/main/src/misc/data-matchups.ts
- https://github.com/wavebeem/pkmn.help/blob/main/src/misc/data-types.ts
- https://github.com/kwsch/PKHeX/blob/master/PKHeX.Core/PersonalInfo/Info/PersonalInfo7.cs
- https://github.com/kwsch/PKHeX/blob/master/PKHeX.Core/Resources/byte/personal/personal_uu

---

# 0.13 — fichas de movimientos y cuadrícula de rutas

En Linux ejecuta `bash Iniciar_Demo.sh` después de extraer el ZIP en una carpeta nueva.
En Windows: Iniciar.bat para datos reales, Iniciar_Demo.bat para revisar la interfaz.

## Movimientos

Pulsa un Pokémon del equipo o de una caja. En su detalle, pulsa uno de sus movimientos:
se abre una ficha con tipo, categoría (Estado/Físico/Especial), potencia, precisión, PP base,
prioridad y descripción en español. Volver al Pokémon cierra únicamente la ficha del movimiento.
Incluye un enlace a WikiDex para la explicación ampliada.

El catálogo local contiene los 728 movimientos de USUM, descripciones de la versión y PP de
séptima generación. No requiere internet para las fichas. Los textos provienen de PokéAPI;
los PP de generación 7 se contrastan con PKHeX. Se deshacen cambios posteriores presentes en
el historial de PokéAPI para los otros campos. Los datos son referencias de juego base:
no se leen potencia, tipo, precisión ni descripción modificados del randomizer.
La ficha lo indica. Los PP restantes y aumentos de PP sí se decodifican del PK7 real.
El máximo mostrado es de referencia y puede diferir si la ROM cambió los PP base.

## Rutas

La pestaña Rutas registra previamente 17 rutas numeradas y otras zonas/subzonas de Alola
(109 entradas) para Ultra Moon 1.0. Una tarjeta tiene sprites arriba y el nombre debajo.
Si hay varios Pokémon, muestra todos; si no hay ninguno registrado, muestra una silueta.
Las tarjetas de rutas no abren detalles. Consulta un Pokémon desde Equipo o Cajas.
Hay filtros de rutas numeradas/otras zonas y búsqueda por nombre.

Se agrupan las lecturas del equipo y las cajas cargadas, evitando contar dos veces un mismo Pokémon.
Leer 32 cajas completa la revisión de las cajas. Un espacio vacío no garantiza que nunca se capturó
allí un Pokémon: no incluye Pokémon liberados ni un historial persistente de encuentros.
Los orígenes especiales o de otros juegos se muestran aparte, sin asignarlos a una ruta de Alola.
El registro por juego está separado en tracker/reference.py y data/Routes_UltraMoon.json;
cada futuro juego implementado debe aportar su propio catálogo de rutas e IDs.

En la demo, Ruta 1 contiene Volcarona y Milotic para revisar varios sprites por zona.
Se incluyen los seis sprites de la demo. Para especies sin imagen local se intenta descargar
la imagen pública de PokeAPI desde el navegador; sin red se muestra el número de especie.
Las fichas de movimientos y los nombres de rutas siguen funcionando sin red.

## Fuentes y comprobación

- Datos: https://github.com/PokeAPI/pokeapi/tree/master/data/v2/csv
- PP de séptima generación: https://github.com/kwsch/PKHeX/blob/master/PKHeX.Core/Moves/MoveInfo7.cs
- IDs de zonas: https://github.com/kwsch/PKHeX/blob/master/PKHeX.Core/Game/Locations/Locations7.cs
- Nombres de Alola y consulta ampliada: https://www.wikidex.net/wiki/Alola
- Scripts para reconstruir el catálogo: tools/download_move_sources.py y tools/build_move_catalog.py.

68 pruebas locales pasan. Se comprobó además la lógica JavaScript de navegación, ficha de movimiento,
rutas vacías y varios sprites. La revisión visual en un navegador real sigue pendiente.

---

# 0.12 — navegación y lugares de encuentro

- Barra superior con identidad Progressive, juego, mini equipo y pestañas Equipo, Cajas, Lugares y Conexión.
- Menú de opciones con vista compacta y descarga de diagnóstico.
- Controles de conexión y escenarios demo en su propia sección.
- Lugar de encuentro en tarjetas y detalles; nivel y fecha de encuentro en detalles; origen de huevo si existe.
- Lugares agrupa el equipo y las cajas leídas. Evita repetir un mismo Pokémon usando su constante de cifrado, especie y mote.
- La búsqueda de cajas también encuentra nombres de lugares.

Los campos met_location_id, egg_location_id, met_level, met_date y origin_version
se decodifican del PK7 ya capturado. Los nombres españoles de Alola se incluyen sin descarga externa.
Los Pokémon de juegos de origen anteriores muestran su ID y versión de origen para evitar asignarles
un nombre de Alola incorrecto. Los valores sin lugar o fecha válida se muestran como desconocidos.
En huevos o Pokémon recibidos, el lugar registrado no equivale necesariamente al lugar de captura salvaje.
Esta vista no determina el primer encuentro por ruta ni guarda un historial completo de capturas.

Referencia de navegación: https://github.com/Bassel-T/nuzlocke.app
Se revisaron GameHeading.svelte y NavHeading.svelte para la organización de navegación,
mini equipo y acciones secundarias. La implementación y los estilos del tracker son propios.
Datos de lugares y estructura: https://github.com/kwsch/PKHeX

En Linux: `bash Iniciar_Demo.sh`. En Windows: Iniciar.bat (real) o Iniciar_Demo.bat.
62 pruebas locales pasan. Los lugares se contrastaron además con la captura anterior del usuario.
La apariencia requiere la revisión visual del usuario en su navegador.

---

# 0.11.1 — modo de demostración en Linux y Windows

Para auditar la interfaz sin Lime3DS ni ROM:

```bash
cd pokemon_tracker
bash Iniciar_Demo.sh
```

También puedes ejecutar `python3 server.py --demo`. Necesitas Python 3.9 o posterior
y un navegador; no necesitas Node.js, pip, Tkinter ni instalar paquetes.
En Windows usa Iniciar_Demo.bat. El lector real de memoria sin GDB sigue siendo exclusivo de Windows;
el modo demo no lo ejecuta.

El navegador se abre automáticamente. Si no lo hace, copia la dirección local de la terminal.
Mantén la terminal abierta y usa Ctrl+C para cerrar. `bash Iniciar_Demo.sh --no-browser`
permite abrir manualmente la dirección local.

El selector DEMO muestra equipo completo, PS bajos/debilitados, equipo vacío, conexión perdida
y nombres largos. Usa las tarjetas para abrir detalles IV/EV; prueba Caja 1 (ocupada), Caja 4 (vacía),
Leer 32 cajas, Cancelar y búsqueda global. Los valores son simulados y siempre están identificados.
Conectar restaura la demo; Desconectar simula datos antiguos. El JSON demo se guarda aparte en
runtime/demo-state.json. Las tarjetas muestran los seis sprites incluidos, sin conexión externa.

Los archivos editables son web/index.html, web/style.css y web/app.js.
Puedes cambiar estilos y recargar el navegador; no necesitas compilar.

58 pruebas locales pasan, incluyendo escenarios y ejecución demo sin acceder al emulador.
La apariencia todavía debe revisarse en tu navegador.

---

# Pokémon Tracker 0.11 — interfaz JavaScript y backend separado

## Inicio en Windows

1. Extrae el ZIP completo en una carpeta nueva.
2. Abre Lime3DS 2119.1, carga tu partida de Ultra Moon 1.0 y desactiva GDB.
3. Ejecuta Iniciar.bat. Requiere Python 3 de 64 bits; no requiere instalar paquetes ni Node.js.
4. Se abrirá el navegador con el tracker. Selecciona Windows sin GDB y pulsa Conectar.
5. Mantén abierta la ventana del servidor. Ctrl+C lo cierra.

Si el navegador no se abre, copia la dirección local que muestra la ventana.
Interfaz_Anterior.bat abre la interfaz anterior de Tkinter como alternativa.

## Interfaz

- Seis tarjetas con PS, cinco estadísticas, habilidad, objeto y cuatro nombres de movimientos.
- Pulsa una tarjeta para ver naturaleza, IV y EV.
- Cajas: selecciona de 1 a 32. La caja seleccionada se actualiza periódicamente.
- Leer 32 cajas crea una caché para la búsqueda global. Cancelar detiene la lectura después de la operación en curso.
- Búsqueda por especie, mote, habilidad, objeto o movimientos; ignora acentos y mayúsculas.
- Las cajas fuera de la seleccionada conservan su última lectura. Reconectar borra la caché.
- Al perder conexión se conservan las tarjetas con aviso de datos antiguos y se intenta reconectar.
- Guardar diagnóstico descarga un JSON con el último error.
- Se incluyen los seis sprites del equipo original. Otras especies muestran su número si no tienen un PNG local en data/sprites. No se descargan recursos externos.

## Arquitectura y JSON

tracker/service.py mantiene la lectura y comparación de datos sin importar ninguna biblioteca gráfica.
server.py sirve HTML/CSS/JavaScript y transmite estados por WebSocket. Solo escucha en 127.0.0.1.
Los conectores de memoria y GDB siguen separados del lector de Pokémon y de la interfaz.

runtime/state.json contiene el último estado publicado. Se escribe mediante reemplazo atómico
solo si cambia el estado; la interfaz recibe ese mismo objeto sin tener que consultar el archivo.
El protocolo WebSocket usa una revisión ascendente. Las tarjetas conservan su elemento y solo
actualizan su contenido cuando cambia el Pokémon. Un cambio de conexión no redibuja el equipo.

Campos principales de schema_version 1:
- revision: contador de cambios publicados.
- connection: status y message.
- stale: true si el último equipo ya no está confirmado por una lectura actual.
- party: seis entradas Pokémon o null.
- boxes: diccionario de números de caja a 30 entradas Pokémon o null.
- selected_box: caja que se lee periódicamente.
- scan: active y completed para la lectura global.

Cada Pokémon conserva los ID numéricos e incluye nombres de especie, habilidad, objeto y move_names,
además de PS, nivel, estadísticas, IV, EV, naturaleza y forma. En cajas no hay estadísticas de combate
ni nivel: esos campos quedan en null. Los nombres provienen del catálogo español incluido.
Los tipos o datos modificados por el randomizer no se infieren a partir de las especies.

Endpoints locales: GET /api/state, GET /api/session, GET /api/diagnostic,
POST /api/command y WebSocket /ws. Los comandos requieren el token de sesión y origen local.
No publica información en internet. Requiere un navegador moderno y Python 3.9 o posterior.

## Verificación

55 pruebas locales: decodificación, conectores, caché de estado, búsqueda,
lectura de cajas, serialización, rutas HTTP, validación de comandos y entrega WebSocket.
El conector sin GDB y la reconexión interna se confirmaron previamente con el usuario en 0.10.2.
La interfaz nueva aún requiere la prueba real del usuario en Windows; no se verificó visualmente en este entorno.

---
Historial de versiones anteriores:

# 0.10.2 — corrección del inicio del equipo

La firma del primer Pokémon está en +68 del bloque de equipo, no en +64.
Se corrigieron la búsqueda inicial y la comprobación de reconexión.
El diagnóstico recibido encontró dos firmas pero las rechazó por este desplazamiento.
46 pruebas locales pasan; falta confirmar la conexión en Windows con el emulador real.

Extrae esta versión en una carpeta nueva, ejecuta Iniciar.bat, carga la partida
con GDB desactivado y selecciona Windows sin GDB. Pulsa Conectar / reconectar.
Si falla, guarda y adjunta el nuevo diagnóstico.

# 0.10.1 — búsqueda ampliada y diagnóstico

Corrige mensajes de progreso que ocultaban el error final. La búsqueda ahora
consulta también regiones menores de 64 MB y valida candidatos encontrados
con el puntero principal del equipo, sin exigir los dos punteros auxiliares.
Siguen siendo obligatorios los checksums PK7 y la validación del bloque de caja.

Usa Windows sin GDB, carga una partida y conecta. Si falla:

1. Espera hasta que termine la búsqueda (máximo aproximado 60 segundos / 4 GiB).
2. Lee el error final, que ya no será sobrescrito por progreso antiguo.
3. Pulsa Guardar diagnóstico de conexión y adjunta el JSON.

El diagnóstico contiene PID, nombre del proceso, regiones/bytes examinados,
número de firmas, errores de lectura y causas de rechazo con direcciones host.
No contiene bloques de memoria, Pokémon, archivos de partida ni credenciales.
45 pruebas aprobadas con memoria simulada y estados locales. No se ha validado
aún la localización de RAM en Windows real. Esta entrega busca resolver el
fallo informado y obtener evidencia precisa si persiste.

---

# Primer conector sin GDB — versión 0.10

Windows + Python 3 de 64 bits, Lime3DS 2119.1 y Ultra Moon 1.0.
Conector experimental: implementado y probado con memoria simulada; falta
validar las llamadas WinAPI y la localización de RAM en el PC del usuario.

## Prueba sin GDB

1. Cierra el tracker anterior.
2. Desactiva GDB en Lime3DS y reinicia Lime3DS para esta primera prueba.
3. Inicia Ultra Moon normalmente y carga tu partida, con Pokémon en el equipo.
4. Abre Iniciar.bat de esta carpeta. Selecciona Windows sin GDB.
5. Deja PID vacío si solo hay un Lime3DS abierto. Pulsa Conectar.
6. Espera la búsqueda de RAM; el estado indica MB revisados. Máximo aproximado
   45 segundos y 2 GiB. No necesitas pulsar Continuar juego en este modo.
7. Compara equipo y una caja contra el juego. Si coinciden, prueba las 32 cajas
   y el reinicio interno sin cerrar Lime3DS.

Si hay varios procesos, el mensaje enumera sus PID. Introduce el correspondiente
y vuelve a conectar. El ejecutable debe llamarse lime3ds*.exe.
El puerto GDB es ignorado por este conector. No necesita paquetes adicionales.
Si OpenProcess rechaza el acceso, comprueba que Lime3DS y Python se ejecuten
con el mismo nivel de permisos; no solicita privilegios adicionales por defecto.

## Cómo funciona

ReadProcessMemory + VirtualQueryEx, permisos PROCESS_VM_READ y QUERY_INFORMATION.
No usa WriteProcessMemory, inyección, sockets GDB, pausa ni reanudación del juego.
Se limita a procesos cuyo nombre comienza con lime3ds y termina en .exe.

El código de Lime3DS relaciona LINEAR_HEAP_VADDR (0x30000000) con el buffer FCRAM.
La búsqueda examina regiones legibles grandes, encuentra tres punteros internos
del contenedor del equipo y deriva la base del buffer. Requiere un bloque PK7
válido ocupado y valida el contenido de la primera caja. Los checksums reducen
falsos positivos; una caja vacía no prueba por sí sola la correspondencia.

La traducción se restringe a RAM lineal y lecturas acotadas. No es un lector
genérico de todas las direcciones virtuales de 3DS ni de otros emuladores.
No se guardan direcciones host fijas para reutilizarlas en otra ejecución.
Si cambia la firma del contenedor o se cierra el proceso, se invalida el
conector y el flujo de reconexión intenta localizar la RAM nuevamente.
No se garantiza aún ese flujo en un reinicio real de Lime3DS.

## Respaldo GDB

El selector permite usar GDB como antes: habilitar GDB en Lime3DS, iniciar,
Conectar y Continuar juego. Los dos conectores usan el mismo perfil,
decodificador y UI. La versión 0.9 sigue siendo el respaldo validado.

## Pruebas nuevas

42 pruebas en total. Incluyen descubrimiento de firma que cruza un bloque de
búsqueda, traducción huésped/host, firma inválida, reinicio simulado, proceso
cerrado y límites de lectura. Se ejecutaron en Linux con memoria simulada;
no prueban que Windows acepte la API ni que el proceso real tenga esa región.

Fuentes:
https://github.com/Lime3DS/lime3ds-archive/blob/master/src/core/memory.cpp
https://learn.microsoft.com/en-us/windows/win32/api/memoryapi/nf-memoryapi-readprocessmemory
https://learn.microsoft.com/en-us/windows/win32/api/memoryapi/nf-memoryapi-virtualqueryex

---

# Pokémon Tracker 0.10

Tracker independiente para Lime3DS 2119.1 y Pokémon Ultra Moon 1.0.
El equipo y las cajas fueron confirmados por el usuario en su ROM randomizada.
Sigue usando GDB para lectura de memoria; no modifica el juego.

## Inicio en Windows

Requiere Python 3 con Tcl/Tk. Extrae el ZIP completo y abre Iniciar.bat.
No necesita paquetes de pip ni conexión a Internet para los nombres.

1. Activa GDB en Lime3DS e inicia el juego.
2. Pulsa Conectar / reconectar en el tracker. Puerto inicial: 24689.
3. Pulsa Continuar juego y carga la partida.
4. En Equipo la actualización automática está activada por defecto.
5. En Cajas PC elige una caja y pulsa Leer caja. Puedes activar lectura cada 3 s.

La actualización automática consulta solo la pestaña activa. Esto reduce las
lecturas simultáneas y no convierte las cajas guardadas en una vista global en vivo.

## Equipo

Muestra apodo, especie, nivel, HP, stats, naturaleza, objeto, habilidad,
movimientos por nombre e IV/EV. Conserva la selección al actualizar.
El orden de IV/EV aparece junto a los datos.
Los stats se leen del juego, sin recalcularlos con tablas oficiales.

Abrir captura permite revisar un .bin de 2904 o 2914 bytes sin emulador.
La captura antigua de 2904 bytes no contiene todos los stats del sexto Pokémon.

## Cajas y búsqueda

Selector de 1 a 32, con 30 slots cada una. Las cajas muestran datos PK7:
especie, apodo, naturaleza, objeto, habilidad, movimientos, IV y EV.
No se inventan nivel, HP ni estadísticas de combate para los Pokémon de caja.
Todavía no se leen nombres personalizados de cajas ni cuántas están desbloqueadas.

La búsqueda ignora mayúsculas y tildes. Permite varias palabras y busca en especie,
apodo, movimiento, habilidad, objeto e ID de especie. Por defecto consulta la caja
seleccionada; En todas las cajas leídas consulta las capturas conservadas.

Leer las 32 cajas ejecuta un recorrido secuencial y mantiene la interfaz disponible.
Mientras recorre cajas, las lecturas del equipo esperan. Cancelar recorrido detiene
los siguientes pasos; la caja en curso puede terminar y se conserva lo ya leído.
La vista muestra cobertura (por ejemplo 8/32) y la hora de la caja seleccionada.

Guardar caja crea un .boxbin de 6960 bytes. Abrir captura asigna sus datos al número
de caja seleccionado: el formato bruto no contiene ese número y no lo verifica.
Las búsquedas en capturas no implican que el contenido del juego siga igual.

## Reconexión y estado

Después de una conexión inicial correcta, la pérdida de transporte activa reintentos
cada 2 a 30 segundos si Reconectar automáticamente está marcado. No intenta conectar
al iniciar la aplicación sin una conexión previa.

Si el juego ya había sido reanudado, una reconexión automática envía continuar.
Conectar manualmente siempre requiere pulsar Continuar juego. Desconectar desactiva
los reintentos para respetar una desconexión intencional.

Al reconectar se borra la caché de cajas, evitando buscar capturas de otra sesión.
El equipo anterior queda marcado pendiente de actualizar. Si la conexión se pierde,
los datos anteriores se conservan y se marcan como tales. Un fallo de checksum
descarta la nueva lectura sin cerrar una conexión de transporte sana.

La reconexión depende de que Lime3DS vuelva a aceptar clientes GDB. Algunas situaciones
pueden requerir desactivar/reactivar GDB o reiniciar el emulador. No se puede prometer
recuperación automática en todos los reinicios. El nuevo flujo requiere prueba en PC.

## Alcance y arquitectura

Solo hay un conector implementado: Lime3DS GDB, conectado a 127.0.0.1.
La interfaz MemoryReader, el perfil de juego y el decodificador son independientes.
No se implementó todavía lectura de memoria del proceso sin GDB.

Los catálogos de nombres están incluidos en español. No se necesitan catálogos de
ROM para los nombres. Las tablas modificadas de tipos, potencia y efectos no se
muestran ni forman parte de esta entrega. Los módulos de catálogo opcional permanecen
como base de desarrollo, sin controles que distraigan en la interfaz.

Perfil RAM: equipo en 0x33F7FA44, stride 484, PK7 a +128 y stats a +472.
Cajas en 0x33015AB0, 232 bytes por slot, 30 slots por caja. El checksum valida PK7;
no asegura que todas las lecturas correspondan al mismo instante del juego.

## Pruebas

python -m unittest discover -s tests -v

42 pruebas aprobadas: protocolo, 24 órdenes de bloques, checksum, captura del sexto
slot, nombres, cajas, búsquedas con tildes, cancelación y estados de reconexión.
El descifrado fue contrastado con captura1.bin; no se distribuyen datos de la partida.
La nueva interfaz no pudo probarse gráficamente en este entorno. La búsqueda global
y la reconexión se verificaron con pruebas locales; falta validarlas en Lime3DS real.

## Licencia y fuentes

GPL-3.0, véase LICENSE.txt. Nombres de PKHeX (kwsch y colaboradores), referencias en
data/FUENTES.md. Referencias técnicas:
https://github.com/Lime3DS/lime3ds-archive/blob/master/src/core/gdbstub/gdbstub.cpp
https://github.com/kcblack42/Citra-Tracker-v2/blob/main/citra-updater.py
https://github.com/drgoku282/PKMN-NTR/blob/master/PKMN-NTR/Helpers/LookupTable.cs
https://github.com/kwsch/PKHeX/blob/master/PKHeX.Core/PKM/PK7.cs

## Versión 0.7: tarjetas y recuperación de reinicio interno

El equipo se presenta en seis tarjetas con sprite, apodo, especie, nivel, barra
de HP, habilidad, naturaleza y stats principales. Pulsa una tarjeta para ver
las cinco estadísticas, objeto, movimientos, IV y EV. Fondo oscuro y tablas de
cajas con el mismo estilo. Las imágenes muestran la especie base, no la forma
ni el estado shiny. Los tipos no se infieren de tablas oficiales.

Se incluyen los seis sprites del equipo validado. Para otras especies se
intenta obtener el sprite en segundo plano de PokeAPI/sprites y se conserva
en data/sprites. Sin Internet o si la carpeta no permite escritura, aparece
el número de especie: la lectura del juego sigue funcionando.
Fuente de sprites: https://github.com/PokeAPI/sprites

La supervisión GDB consulta capacidades cada 2 segundos cuando ya hay una
sesión en ejecución. Antes envía c (continuar) para liberar un posible halt
tras reiniciar el juego sin cerrar el emulador. Esto también reanuda una pausa
puesta desde GDB; el tracker no está pensado para usarse junto a otro depurador.
No se envía pausa, kill ni escritura de memoria. El socket sigue siendo uno
y todas las operaciones de GDB se serializan.

La corrección se probó con el estado de sesión simulado: continuar se envía
también al mantener el mismo socket. Falta validar el reinicio real dentro de
Lime3DS. Si su servidor deja de escuchar, sigue siendo necesario reactivar GDB.
Prueba: con el tracker conectado reinicia Ultra Moon desde Lime3DS sin cerrar
el emulador y verifica que la ejecución y las lecturas vuelvan.

La interfaz rediseñada no pudo inspeccionarse gráficamente en este entorno.

## 0.8: actualización sin reconstruir tarjetas

SnapshotStore compara datos en el backend; la UI conserva las seis tarjetas.
Si el equipo es idéntico, no reconstruye filas, tarjetas ni detalles. Cuando
cambia un Pokémon se actualizan sus campos sobre los mismos widgets. Las cajas
comparan la captura y los filtros antes de reconstruir la tabla. Los detalles
no reemplazan su texto si no cambia, conservando su posición de lectura.
Esto separa comparación y presentación en módulos dentro de la misma aplicación;
no crea todavía otro proceso ni una segunda ventana de UI.

La captura del error de reinicio confirmó WinError 10061: conexión rechazada.
Eso significa que el servidor GDB no acepta conexiones; el cliente no puede
reabrirlo en el emulador. El mensaje ahora indica reactivar GDB y volver a iniciar
el juego. La recuperación automática continúa cuando el servidor esté disponible.
No se da por solucionado el reinicio interno que deja GDB sin escuchar.

## 0.9: estadísticas completas y movimientos visibles

Cada tarjeta muestra Ataque, Defensa, At. especial, Def. especial y Velocidad,
además de HP, objeto y los cuatro movimientos por nombre. El área de tarjetas
tiene desplazamiento vertical para evitar que el contenido quede recortado.
Ver detalles abre una pestaña amplia con naturaleza, objeto, movimientos, IV, EV
y stats. La lectura del equipo continúa mientras esa pestaña está activa.
Los widgets siguen siendo persistentes para conservar la solución al parpadeo.

No se cambiaron los offsets de RAM: la captura mostraba solo tres estadísticas
y el panel inferior fuera de vista. Si algún número difiere de la pantalla del
juego, se necesita comparar ambos para investigar el estado de combate o lectura.
La nueva distribución queda pendiente de verificación visual en el PC del usuario.
