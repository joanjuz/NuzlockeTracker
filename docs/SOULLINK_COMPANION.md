# Soul Link — sincronización de compañero (v0.22.0 experimental)

## Qué cambia

El tracker conserva su interfaz, lectura local y modo demo. En `··· → Sincronizar compañero` puedes **crear** una pareja o **unirte** mediante un código privado. Cuando el otro jugador haya aceptado, aparece **Compañero** junto al nombre del juego. Este botón alterna entre tus datos y la **última sesión guardada** de tu pareja (Ultra Sol ↔ Ultra Luna).

En la vista de compañero reutiliza Equipo, Cajas, Rutas, Muertos, Análisis y detalles; las acciones que cambiarían la partida quedan desactivadas. Se conservan tus propias vistas sin mezclarlas. El botón de compañero aparece tras vincular ambos jugadores, aun cuando el compañero todavía no ha enviado datos.

**Importante:** la vista es una copia del último estado compartido, no una sincronización de las ROM ni un combate cooperativo. El compañero nunca puede editar tu partida ni modificar tu emulador. Tampoco enlaza automáticamente capturas y muertes entre partidas; esas reglas se implementarán después.

## Despliegue inicial de Cloudflare (lo realiza quien administra el Worker)

Necesitas una cuenta de Cloudflare, Node.js 22 y acceso a PowerShell. El código se encuentra en `cloudflare/companion-worker`. No se necesitan servicios de pago para una prueba pequeña dentro de la cuota gratuita, que está sujeta a los límites vigentes de Cloudflare.

En PowerShell, desde la carpeta del repositorio:

```powershell
cd D:\Progra\NuzlockeTracker\cloudflare\companion-worker
npx wrangler login
npx wrangler d1 create pokemon-tracker-companion
Copy-Item .\wrangler.toml.example .\wrangler.toml
```

1. La creación de D1 muestra un identificador `database_id`. Abre `wrangler.toml` y sustituye `PEGA_AQUI_EL_UUID_DE_D1` por ese UUID. `wrangler.toml` está ignorado por Git.
2. Aplica la migración de SQL **remota**, publica el Worker y define una clave de creación aleatoria de **al menos 16 caracteres**:

```powershell
npx wrangler d1 migrations apply pokemon-tracker-companion --remote
npx wrangler deploy
npx wrangler secret put CREATE_KEY
```

Al definir la clave, el CLI la solicita interactivamente. **No pegues la clave en el chat, en los commits ni en archivos del repositorio.** Conserva su valor en un gestor de contraseñas. Tras el despliegue aparece una URL parecida a `https://pokemon-tracker-companion.nombre.workers.dev`. Abre `URL/health`, que debería mostrar `{"ok":true,"service":"companion-v1"}`.

No necesitas GitHub Pages. Cloudflare Worker atiende la autenticación HTTPS y D1 almacena una última sesión por jugador. No abras puertos de tu casa ni uses enlaces LAN anteriores.

## Primer jugador (ejemplo Ultra Sol)

1. Ejecuta `Iniciar.bat` desde **la nueva carpeta Git** `D:\Progra\NuzlockeTracker`, abre Lime3DS con Ultra Sol 1.0 y conecta el tracker. Tu instalación anterior permanece intacta.
2. Abre `··· → Sincronizar compañero`.
3. Pega la URL pública HTTPS del Worker, tu nombre y selecciona **Ultra Sol 1.0**.
4. Introduce la clave `CREATE_KEY` únicamente en el formulario local y pulsa **Crear pareja**. El formulario borra el campo de clave al finalizar.
5. Envía al otro jugador **solo el código de invitación** por un canal privado. El código caduca a las 24 horas y solo puede canjearse una vez. El servicio conserva un token privado distinto por jugador.

## Segundo jugador (Ultra Luna)

1. Obtiene el código de invitación y la URL pública del **mismo Worker**.
2. Ejecuta su propio `Iniciar.bat` con Ultra Luna 1.0, abre `··· → Sincronizar compañero`.
3. Introduce URL, nombre, juego **Ultra Luna 1.0** y el código de invitación; pulsa **Unirme a mi compañero**. **No necesita la clave CREATE_KEY**.

El cliente revisa cambios aproximadamente cada **20 segundos** y solo envía nuevas sesiones válidas. Se conservan las últimas sesiones cuando se desconecta el emulador o se cierra la computadora; la copia local `runtime/companion-cache.json` permite visualizar el último estado recibido si falla Internet. En esta primera versión las cajas remotas muestran únicamente las cajas que la pareja haya leído previamente; para incluir las 32, usa **Leer 32 cajas** en la aplicación del jugador que comparte.

## Privacidad y eliminación

- El Worker exige un secreto de creación; los datos de cada pareja solo son accesibles mediante su token personal. Los tokens se guardan como SHA-256 en D1.
- Se transfieren, para reproducir las fichas, especies, motes, niveles, PS, estadísticas, habilidades, objetos, movimientos, IV/EV, rutas de encuentro, identificación interna de Pokémon, cajas previamente leídas y registro de Muertos/Miss. **No** se transfieren la ROM, archivo de guardado, dump de RAM, PID, diagnósticos ni rutas de tu PC.
- El token privado y caché quedan en `runtime/companion-credentials.json` y `runtime/companion-cache.json`, ignorados por Git. No compartas estos archivos.
- Desde la interfaz puedes usar **Desvincular**: revoca ambas credenciales y elimina de D1 las sesiones compartidas de esa pareja (el otro jugador deberá limpiar también su configuración local si desea volver a vincularse).
- El Worker no habilita CORS para otros sitios; la aplicación Python local realiza las solicitudes HTTPS. No necesita abrir puertos en el firewall.
- `CREATE_KEY` puede reemplazarse desde Cloudflare. Evita URL de Worker no confiables: el dueño de una URL puede almacenar los datos que envíes.

## Pruebas locales

```powershell
python -m unittest discover -s tests -q
node tests/test_analysis.js
node tests/test_progress_ui.js
node tests/test_mini_sprites.js
node --test cloudflare/companion-worker/tests.mjs
```

La última prueba usa `node:sqlite` experimental de Node 22 y no realiza solicitudes a Cloudflare. No se publicarán cambios directamente en `master`: rama `feature/soullink-companion-sync` → PR a `development` después de probar con dos computadoras reales.
