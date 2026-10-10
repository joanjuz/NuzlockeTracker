# Diagnóstico Gen6 — Pokémon X/Y y ORAS

Este paquete es una **herramienta independiente para Windows** que investiga el almacenamiento PC y los PS en combate usando la memoria del emulador. **Solo lee memoria; no modifica el juego, el guardado ni el tracker**.

## Ejecución
1. Extrae el ZIP `Diagnostico-Gen6-Windows.zip` en una carpeta diferente de Pokémon Tracker.
2. Abre Lime3DS/Citra/Azahar con Pokémon X, Y, Rubí Omega o Zafiro Alfa 1.0.
3. Ejecuta **`Diagnostico_Gen6.bat`**. Se abrirá una ventana de consola. El paquete ya incluye `Diagnostico_Gen6.exe` y **no necesita instalar Python**.
4. Selecciona el juego y, si tienes un solo emulador abierto, deja el PID vacío.
5. Carga la partida, fuera de combate y fuera del PC; pulsa Enter. Debería reconocer tu equipo (especies y PS).
6. Para **localizar las cajas**, elige un Pokémon que ahora esté en el equipo. Sigue la instrucción de **depositarlo en Caja 1, casilla 1**, cierra el PC, y continúa. El programa buscará su identificador cifrado en la RAM y verificará la estructura de 31 cajas. Cuando acabes puedes devolver el Pokémon a tu equipo.
7. Para los **PS en combate**, utiliza un Pokémon que continúe en el equipo; indica sus PS máximos. Entra en combate y, con el menú de movimientos abierto, **pausa Lime3DS** y escribe sus PS actuales. El programa buscará todas las direcciones que contienen ese valor. Reanuda, recibe daño o recupérate y repite en dos turnos distintos; **no cambies de Pokémon** durante estas tres lecturas.
8. Reanuda Lime3DS al finalizar.

Al terminar se guarda un JSON en la carpeta **`runtime`** que queda junto al ejecutable, con nombre parecido a `diagnostico_gen6_20261010_XXXXXX.json`. Envíalo para analizar los candidatos. No contiene ROM, partida, contraseña, memoria cruda ni apodos, pero sí puede incluir PID y direcciones de memoria.

La búsqueda de PS puede tardar algunos minutos; la de cajas examina como máximo 128 MiB de RAM. Si una etapa falla o cancelas, igualmente se guarda el diagnóstico parcial.

### Estado del proyecto

Esta herramienta no activa automáticamente los PS/cajas Gen6 del tracker. Primero hay que confirmar direcciones mediante dos o tres lecturas que cambien como lo hace el juego. PR #14 permanece experimental y `master` no se modifica.
