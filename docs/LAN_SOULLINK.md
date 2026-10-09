# v0.21.0 (experimental) - LAN Soul Link 2 vs 2

## Qué incluye

- Una sala local, visible desde otros dispositivos en la **misma LAN**.
- Dos parejas: **A-SUN + A-MOON** frente a **B-SUN + B-MOON**.
- Una tarjeta por jugador con los seis Pokémon y PS durante combate en vivo.
- Un emulador Lime3DS y un tracker local por jugador; no hay lectura remota de RAM.
- La sala muestra ``Sin señal`` si un cliente deja de enviar datos y ``Tracker desconectado`` si el emulador no está conectado.
- El servidor solo recibe especie, apodo, nivel, PS y tipo de juego. No recibe cajas, IV/EV, movimientos, ubicación, ruta, progreso interno, IDs de memoria ni rutas del PC.

**Importante:** mostrar parejas de jugadores no enlaza automáticamente Pokémon específicos. Esta versión tampoco causa muertes cruzadas, altera la ROM ni sincroniza combates entre juegos. Las reglas de Soul Link siguen gestionándose por los jugadores. Registro de encuentros y enlaces de Pokémon quedan para la siguiente fase.

## Iniciar el anfitrión

En la computadora del anfitrión (que puede jugar también), ejecuta `LAN_Host.bat`.

- Puerto predeterminado: **8765/TCP**.
- Permite ese puerto en el firewall de Windows **solo en red privada** (no red pública).
- Usa `ipconfig` para localizar tu dirección **IPv4 de Wi-Fi o Ethernet**.
- La consola muestra cuatro claves privadas, una por puesto, y un enlace de espectador con otra clave. No publiques claves ni capturas de la consola.
- Para espectadores: reemplaza `IP_DEL_ANFITRION` por la IP IPv4 y abre `http://IP:8765/#CLAVE_ESPECTADOR` en un navegador conectado a la misma red.

## Conectar cada jugador

1. Cada jugador abre Lime3DS con **Ultra Sol 1.0** o **Ultra Luna 1.0**.
2. Cada jugador ejecuta `Iniciar.bat` y pulsa **Conectar**. Deja la ventana abierta.
3. Cada jugador ejecuta `LAN_Join.bat` en su computadora, donde tenga el tracker actualizado.
4. Pega la URL de su tracker **127.0.0.1** mostrada al iniciar (el puerto cambia cada vez que lo abres).
5. Indica la URL de la sala, por ejemplo `http://192.168.1.25:8765/`.
6. Elige el puesto correspondiente (A-SUN, A-MOON, B-SUN, B-MOON) e introduce **solo la clave de ese puesto** recibida del anfitrión, además del nombre que quieras mostrar.
7. El anfitrión también debe ejecutar `LAN_Join.bat` si participa como jugador. **La ventana del anfitrión no publica automáticamente su propio equipo.**
8. Para detener el envío, cierra el cliente con Ctrl+C; después de ~12 segundos aparecerá sin señal.

### Ejemplo

| Pareja A | Pareja B |
| --- | --- |
| A-SUN: jugador 1 (Ultra Sol) | B-SUN: jugador 3 (Ultra Sol) |
| A-MOON: jugador 2 (Ultra Luna) | B-MOON: jugador 4 (Ultra Luna) |

Los puestos son fijos para prevenir que un cliente de Luna suplante accidentalmente un puesto de Sol.

## Limitaciones y seguridad

- **LAN de confianza únicamente**: HTTP sin cifrar. No abras el puerto en Internet, no configures port forwarding y no utilices redes Wi-Fi públicas.
- El enlace de espectador permite leer los cuatro equipos; las claves de jugadores permiten publicar en un puesto específico. Cambian cada vez que reinicias la sala. Los enlaces se comparten por un canal privado.
- No existe persistencia de sala ni chat en esta versión.
- Actualización aproximada de 2 segundos, más el intervalo del tracker local.
- Si cambias de juego, usa el puesto correspondiente y vuelve a ejecutar el cliente LAN con la clave nueva.
- Los PS en combate continúan con las limitaciones conocidas de los combates especiales (dobles/SOS/transformaciones no validados).

## Pruebas

`py -3 -m unittest discover -s tests -v`

También puedes ejecutar `py -3 -m unittest tests.test_lan -v` si tu entorno permite el import directo del paquete tests. En caso contrario: `py -3 -m unittest discover -s tests -p test_lan.py -v`.
