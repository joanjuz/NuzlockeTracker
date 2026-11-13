# Sala Soul Link: contrato v2 (base de implementación)

El protocolo de sala amplía el modelo a 2, 3 o 4 miembros. El modelo, la persistencia y el transporte local v2 están implementados;
los controles visuales se incorporan en un incremento separado.
Direct v1 y Cloudflare v1 conservan sus contratos actuales de dos jugadores.

Cada sala tiene UUID de sesión y época, capacidad y anfitrión. Cada jugador tiene
UUID estable de perfil y UUID de partida por juego. El servidor asigna la identidad
al autenticar la credencial; un mensaje no puede elegir al jugador que sustituye.
La secuencia de estado debe crecer (entero 0..2^53-1). Una repetición idéntica es
idempotente; una secuencia antigua o reutilizada con otro contenido se rechaza.
El epoch impide aplicar mensajes de otra encarnación del anfitrión.

Las invitaciones usan secretos aleatorios de 256 bits, caducan a los diez minutos,
son de un solo uso y pueden revocarse. Crear una invitación invalida la anterior.
Una reconexión dirigida exige la misma identidad, partida y juego y cambia la
credencial. Salir revoca la credencial pero conserva la plaza; eliminar una plaza
es una acción explícita del anfitrión. Los nuevos miembros no heredan identidades.
El anfitrión decide la membresía y distribuye estados; nunca decide comandos de
partida ni escribe en el emulador de otro jugador.

Los estados usan exclusivamente `companion.snapshot.shared_state`. Un latido sin
lectura actual conserva la última lectura y marca `source_live=false`. A los veinte
segundos sin latido el miembro pasa a desconectado. La primera lectura establece
la línea base sin generar alertas retroactivas. Muertes, reanimaciones y rutas Miss
posteriores generan eventos informativos, con historial limitado a cien entradas.
El historial nunca sustituye al estado completo ni da permiso para marcar una
muerte local. Los eventos de respuesta Soul Link se identifican para evitar rebotes.

`companion-multiplayer.json` almacena solo versión de esquema, identidad, partidas
y última sala saneada. Nunca guarda invitaciones ni credenciales. La carga pone
todos los miembros sin conexión y sin lectura actual. No abre puertos. Un archivo
corrupto o de versión futura se conserva y bloquea la creación silenciosa de otra
identidad. Los archivos v1 no se modifican; no hay migración destructiva.

Límites: cuatro estados individuales de hasta 650 KB; respuesta agregada hasta
2.8 MB, miembros y eventos acotados, textos mediante la lista blanca existente.
Este contrato no demuestra conectividad por Internet ni compatibilidad jugable;
las pruebas del modelo usan estados sintéticos y no ROMs ni saves originales.

## Transporte y acciones locales v2

El listener de Direct se reutiliza con rutas exclusivas `/v2/join`, `/v2/exchange`
y `/v2/leave`. Una sala rechaza v1; una pareja v1 rechaza v2. El enlace de sala es
`nuzlocke://IP:puerto/room#secreto`. No se permite proxy, redirección, IP pública,
DNS, Origin de navegador ni acceso al servidor de administración. HTTP requiere
LAN de confianza o VPN cifrada, como Direct v1. No hay descubrimiento ni NAT traversal.

La API local autenticada añade `room_host`, `room_join`, `room_invite`,
`room_revoke`, `room_remove` y `room_new_run`. El host elige capacidad 2/3/4.
Los invitados no pueden administrar plazas ni invitaciones. La salida usa `leave`;
`refresh` fuerza sincronización. Cambiar de pareja/sala exige salir primero.
Nueva partida exige desconectarse y rota solo el run_id del juego seleccionado.

Cada credencial identifica un único jugador. Se valida sesión, época, run_id y
secuencia en cada intercambio y salida. Un campo player_id del remitente no tiene
autoridad. Cada snapshot enviado mantiene el límite v1; solo la respuesta agregada
admite 2.8 MB. Ocho peticiones autenticadas por segundo como máximo por miembro;
el cliente normal transmite como máximo una vez por segundo y sondea cada cinco.

Después de un fallo se marca la vista recibida offline. Al reiniciar no se restaura
la conexión; se puede consultar caché. Si el host sigue abierto, una invitación
dirigida permite recuperar la plaza con la identidad/partida persistidas. Si el host
reinicia, debe crear otra sala e invitar explícitamente a los demás. No se restaura
una credencial antigua ni se reutiliza una invitación consumida.

Pruebas: `python -m unittest tests.test_multiplayer_direct tests.test_companion_direct
tests.test_companion -v`; cuatro puentes independientes y listeners reales loopback,
respuesta de cuatro estados mayor de 650 KB, aislamiento de identidad autenticada,
reconexión tras recrear el puente, pérdida de fuente actual, cierre del host, límites,
CSRF/Origin, rutas de administración rechazadas y regresión de pareja v1.
