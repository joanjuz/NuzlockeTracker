# Soul Link: protocolo privado y admisión común

El protocolo 3 separa la participación Soul Link de mostrar una partida completa.
Los protocolos anteriores de pareja y sala mantienen sus contratos durante la
transición. La interfaz principal se incorpora por separado; este incremento
añade el modelo, transporte, almacenamiento y ciclo de vida sin activar el flujo.

## Membresía y acceso

Una sala admite hasta cuatro personas, incluido su creador. La invitación de 256
bits es una autorización de ingreso reutilizable, estable después de cada entrada,
válida hasta revocación, regeneración o cierre. Estar llena impide nuevos ingresos;
no transfiere plazas reservadas. Cada ingreso recibe un secreto distinto, ligado a
sesión, época, jugador y partida. La invitación nunca autoriza intercambios ni salida.

Una desconexión reserva identidad y plaza. Recuperarla exige la credencial individual,
el mismo perfil/partida y la misma sala/época; rota la credencial y vuelve a privacidad
activada. Cerrar la app conserva esa posibilidad sin abrir puertos ni reconectar al
arrancar. Salir voluntariamente libera la plaza y revoca su credencial. La identidad
de esa participación queda retirada en la sala y no puede reclamarse con la invitación.
Una nueva entrada tras salir crea otra participación, sin heredar enlaces ni eventos;
no borra el progreso ni las identidades de partida de los juegos. Los identificadores
retirados tienen un límite de 4096 por sala para acotar memoria.

Eliminar una plaza revoca esa conexión; para excluir a alguien que todavía conoce
la invitación común hay que revocarla. No se simula una prohibición de cuentas:
el acceso se basa en la posesión del enlace, no en una identidad externa acreditada.
El host administra membresía pero no tiene acceso privilegiado a vistas privadas.

## Privacidad y datos mínimos

`sharing` es falso por defecto. Con ese permiso desactivado el cliente no envía
un snapshot completo y el servidor rechaza uno no nulo. Solo viajan la identidad
de membresía y las capturas elegidas expresamente para Soul Link: ruta, clave de
captura, especie/origen/lugar, estado y fecha de muerte/respuesta. No se incluyen
apodos, niveles, PS, estadísticas, habilidades, objetos, movimientos, cajas o rutas
ajenas a los enlaces. La participación no exige activar la vista completa.

El permiso, el snapshot opcional, los enlaces y el estado mínimo están unidos a
la misma secuencia. Mensajes antiguos no restauran permisos anteriores. Repetir
una secuencia idéntica no renueva presencia ni el permiso temporal de una vista.
Desactivar la compartición elimina el snapshot del servidor al procesar el mensaje;
las demás aplicaciones lo retiran al sincronizarse. Las vistas completas caducan
como máximo a los doce segundos de su último intercambio autorizado, sin que
consultar la API o repetir respuestas prolongue ese plazo. Fallar la conexión o
reiniciar elimina las vistas completas de la aplicación receptora.

Las cachés persistidas nunca contienen snapshots remotos completos, tampoco mientras
estén autorizados. Se purgan las cachés remotas heredadas al entrar por primera vez
en el nuevo flujo, conservando datos locales, perfil e identificadores de partida.
Una aplicación ajena puede haber guardado datos mientras estaba autorizada; no se
promete borrar copias externas ni revocación instantánea sin comunicación. El
permiso futuro sí se cierra y las aplicaciones propias tienen una caducidad acotada.

Los enlaces y las confirmaciones manuales usan el estado mínimo. La confirmación
local debe seguir vinculada a sala, época, partida local/remota, captura y muerte
vigentes; una respuesta Soul Link no produce rebote ni orden remota de juego.

## Transporte y persistencia

Rutas peer exclusivas `/v3/join`, `/v3/resume`, `/v3/exchange` y `/v3/leave`.
Invitación `nuzlocke://IP:puerto/soul#secreto`; IPv4 privada, sin proxy ni redirección,
sin Origin de navegador, API administrativa ni exposición de archivos locales.
Se mantienen límites de JSON, snapshots y ocho peticiones autenticadas por segundo.
El mensaje mínimo admite 32 KB; los snapshots y agregado conservan los límites
anteriores. Validadores reconstruyen exclusivamente campos permitidos.

`companion-soul.json` contiene identidad y caché mínima offline. `soul-connection.bin`
guarda aparte la credencial individual y su destino exacto; Windows usa DPAPI
CurrentUser, POSIX permisos 0600. Nunca va a status, caché, invitación, logs o paquete.
Archivos corruptos/futuros se conservan; olvidar credenciales no reescribe una
identidad cuyo formato no se comprende. Crear un host que falla no destruye una
conexión anterior recuperable. Fallar el guardado de una entrada nueva permite
olvidar ese intento antes de volver a entrar con otra participación.

Direct sigue requiriendo LAN de confianza o VPN cifrada: HTTP no proporciona cifrado
propio ni NAT traversal. No se despliega infraestructura ni se cambia Cloudflare.
Esta descripción no acredita Internet, WebView2 nativo ni jugabilidad.
