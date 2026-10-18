# Soul Link directo: una aplicación hace de host

En **Sincronizar compañero**, elige **Conexión directa**. Se mantienen la vista de
la partida del compañero y los avisos manuales de muerte por ruta. Cloudflare
sigue disponible como alternativa en el selector de conexión.

## Conectar dos equipos

1. Abre el tracker en ambos equipos y selecciona la partida/perfil correcto.
2. En el host, escribe tu nombre, juego y la **IPv4 del adaptador de tu red local
   o VPN**. Usa el puerto `8770`, o elige otro puerto disponible. Pulsa **Ser host**.
3. Si Windows pregunta, permite ese puerto únicamente en la red privada o VPN
   que usas con tu compañero. El tracker no modifica automáticamente el firewall.
4. Copia la invitación `nuzlocke://IP:PUERTO/join#…` y envíala de forma privada.
5. En el segundo tracker, elige conexión directa, tu nombre/juego y pega la
   invitación completa. Pulsa **Unirme al host**. La invitación se usa dentro del
   tracker; no es necesario abrirla en un navegador.

Cada tracker comparte únicamente la sesión del perfil activo. El host debe
permanecer abierto. Un tracker sin una lectura actual conserva la última sesión
válida compartida; el aviso explica que todavía no puede actualizarla.

**Para jugar por Internet**, ambos equipos necesitan una ruta entre ellos, por
ejemplo una VPN privada cifrada. Estar en redes domésticas distintas no crea esa
ruta automáticamente. Este modo no abre puertos en el router, no atraviesa NAT
por sí solo y no usa un servidor de retransmisión externo del tracker. La propia
VPN puede requerir su infraestructura. Evita publicar este puerto en Internet.

Se admiten IPv4 privadas `10.*`, `172.16–31.*`, `192.168.*`, el rango de VPN
`100.64–127.*` y el rango `26.*` usado por adaptadores Radmin VPN. Usa `26.*`
solo con el adaptador/ruta Radmin correspondiente. `127.*` sirve únicamente para
dos aplicaciones en el mismo equipo. No se admiten nombres DNS, IPv6, direcciones
públicas generales, enlaces de metadatos ni la dirección comodín `0.0.0.0`.

## Privacidad y control

- El servicio directo usa HTTP sobre una red de confianza. Para redes remotas o
  no confiables utiliza una VPN cifrada; HTTP por sí solo no cifra la sesión.
- La invitación tiene un secreto aleatorio de 256 bits y solo admite un compañero.
  Al unirse, se invalida y se sustituye por una credencial de sesión distinta.
  Trátala como una contraseña hasta que tu compañero se una.
- Solo se comparten equipo, cajas leídas, estadísticas, rutas y muertes. Se
  excluyen credenciales de la aplicación, diagnósticos, PID, rutas del equipo,
  archivos de partida y volcados de RAM.
- El puerto del host sirve exclusivamente el protocolo Soul Link. No permite
  abrir la interfaz del tracker, cambiar su configuración ni registrar muertes
  en el tracker remoto. Cada muerte Soul Link sigue requiriendo aceptación local.
- Las credenciales y sesiones directas se conservan en memoria. No se abre un
  puerto al iniciar la aplicación. Al cerrar, cambiar de perfil o desvincular se
  cierra la conexión. Para reconectar después, crea una invitación nueva.
- Desvincular desde el invitado invalida su acceso en el host cuando hay conexión.
  Si el host está desconectado, la desvinculación local sigue funcionando; el host
  debe cerrar/desvincular su sesión para invalidar inmediatamente una credencial
  que pudiera seguir existiendo allí.

## Si no conecta

Verifica que la IP pertenece al adaptador correcto del host, que el host sigue
abierto, que el puerto coincide y que el firewall permite conexiones desde la
red/VPN del compañero. No uses `127.0.0.1` para un compañero en otro equipo.
Si una invitación ya se usó o el host se cerró, desvincula y crea otra.

## Comprobaciones de desarrollo

`python -m unittest tests.test_companion_direct -v` prueba dos aplicaciones reales
en loopback: intercambio bidireccional, muertes manuales, filtrado de datos,
invitación de un solo uso, cierre del puerto y límites de autenticación/mensajes.
No requiere Cloudflare ni una cuenta externa. La verificación entre dos equipos
con VPN/firewall reales sigue siendo una prueba manual de integración.


## Juegos compatibles

La sincronización permite Pokémon X, Pokémon Y, Rubí Omega, Zafiro Alfa,
Ultra Sol y Ultra Luna, con los perfiles 1.0 disponibles en el tracker.
Cada jugador selecciona su propio juego; los dos pueden jugar títulos distintos.
El juego de una sesión debe coincidir con el configurado para ese jugador.
Se conservan los límites de cada generación: 31 cajas y 721 especies en Gen6;
32 cajas y 807 especies en Gen7. La sincronización solo comparte la información
permitida del tracker, sin escribir en las partidas.

La conexión directa funciona entre dos aplicaciones actualizadas. Para Cloudflare,
el código del Worker incluido también admite estos seis juegos. Un Worker
instalado anteriormente que solo acepte Ultra Sol/Ultra Luna debe actualizarse
por separado antes de usar Gen6; generar el ejecutable no despliega el Worker.
