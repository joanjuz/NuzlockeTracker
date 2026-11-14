# Soul Link para 2–4 jugadores

> Conexión anterior conservada en Opciones de conexión. El flujo principal actual
> es [Soul Link](SOUL_LINK.md): invitación común, hasta cuatro personas y partida
> privada por defecto. Este documento describe el contrato previo de compatibilidad.

En cada Tracker abre Opciones (…) → Sincronizar compañero. En Conexión elige
**Sala de 2–4 · red local/VPN**. Los dos modos anteriores de pareja continúan
disponibles: Direct de dos jugadores y Cloudflare de dos jugadores.

## Crear y unirse

1. El anfitrión introduce su nombre, juego, IP privada y puerto, elige 2, 3 o 4
   jugadores y pulsa Crear sala. Solo entonces se abre el puerto de la sala.
2. Comparte la invitación completa por un medio privado. Caduca a los diez minutos
   y solo admite una entrada. Crear otra o Revocar invitación anula la anterior.
3. Cada invitado pega el enlace, elige su nombre y juego y pulsa Unirme al host.
   El anfitrión pulsa Invitar al siguiente jugador para la siguiente plaza.

El anfitrión debe ser accesible en la misma red o una VPN privada cifrada y permitir
el puerto en su firewall. Direct usa HTTP, por lo que exige red de confianza.
Esta opción no atraviesa NAT ni configura routers. Cloudflare conserva su flujo
actual de dos personas; no se ha desplegado un servicio nuevo de cuatro personas.

## Capturas enlazadas y avisos

Cada tarjeta muestra jugador, juego, conexión, última lectura y equipo. Ver partida
abre las vistas individuales de solo lectura; ← Mi partida recupera tu vista.
Los controles de conexión/progreso locales permanecen desactivados en vista remota.

En Capturas enlazadas por ruta cada jugador elige **su propia captura**. Hay un grupo
activo por ruta y región, con hasta cuatro integrantes. Equipo, cajas, Muertos y
marcas de intercambio conservan la identidad de la captura; las copias repetidas
se muestran una vez. Si hay varias capturas, elige explícitamente cuál pertenece
al grupo. Otra selección sustituye la anterior; Sin enlace la elimina. No se
reemplaza automáticamente una captura que desaparezca de las lecturas.

Se distinguen espera, Miss, muerte, intercambio, captura fuera de lectura y
desconexión. X/Y, ORAS y USUM tienen mapas separados; no se emparejan IDs de
regiones distintas ni capturas recibidas de otra región, huevos o regalos por
coincidencia. El registro compartido conserva eventos recientes y selecciones.
Se comparte el progreso disponible de cada jugador, sin exigir avance idéntico.

Activa Avisos Soul Link para recibir propuestas de muertes nuevas, sin avisos
retroactivos. La propuesta exige captura elegida en ambos jugadores; puedes
ignorarla o confirmar Marcar muerte. Nunca se aplica una muerte automáticamente.
La API comprueba sala, época, partida, enlace y muerte remota al confirmar, y no
acepta avisos de otra partida o sala. Reanimar no reanima automáticamente a otros.
Las muertes registradas como respuesta Soul Link no generan avisos de rebote.

## Desconexión, reinicio y otro reto

Un jugador sin conexión conserva plaza y última lectura, claramente indicadas.
Si vuelve mientras mantiene su conexión, se sincroniza de nuevo. Si reinició el
Tracker, el host usa Invitar a reconectar en su tarjeta: la nueva invitación exige
la misma partida y revoca la credencial anterior. Eliminar plaza es una acción
explícita del host. Salir no asigna la plaza a otra persona silenciosamente.

Al reiniciar no se abren puertos ni se recuperan credenciales. La última sala queda
como historial de solo lectura. Si reinicia el host, crea otra sala e invita de nuevo.
Para otro reto, usa un perfil de partida independiente o, estando desconectado,
Usar otro reto en el juego seleccionado. Esto separa los enlaces Soul Link y no
borra el progreso local. Las partidas y archivos v1 no se migran destructivamente.

## Límites comprobados

Pruebas del modelo, transporte loopback y Chromium con cuatro procesos de la app
en modo demo; diseño de cuatro columnas, dos columnas y una columna móvil. No son
pruebas jugables con ROMs/saves ni verificación nativa WebView2 o Internet entre
redes distintas. Muchas cajas aumentan el tráfico: se intercambian estados completos
acotados, no deltas de memoria. El host debe mantenerse abierto. Cada lectura
individual admite 650 KB y la respuesta agregada 2.8 MB. Las versiones de sala
deben admitir `capture-links-v1`; se rechazan huéspedes/hosts incompatibles.

Detalles técnicos: [MULTIPLAYER_PROTOCOL.md](MULTIPLAYER_PROTOCOL.md).
