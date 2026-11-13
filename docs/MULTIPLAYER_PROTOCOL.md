# Sala Soul Link: contrato v2 (base de implementación)

El protocolo de sala amplía el modelo a 2, 3 o 4 miembros. Este primer incremento
contiene el modelo y la persistencia; todavía no habilita salas en la interfaz.
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
