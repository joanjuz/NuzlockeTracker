# Soul Link

Una persona crea una sala y comparte un solo enlace. Hasta cuatro participantes
pueden entrar sin elegir previamente cuántos serán. Cada persona decide si muestra
su partida completa; al entrar está privada.

## Crear la sala y entrar

1. En Opciones (…) abre **Soul Link**. Introduce tu nombre y elige tu juego.
2. Pulsa **Crear sala**. Entras automáticamente y el contador muestra **1/4**.
3. Pulsa **Copiar invitación** y envía ese mismo enlace por un medio privado a tus
   amigos. No necesitas generar otro después de cada ingreso.
4. Los demás abren Soul Link, escriben su nombre/juego, pegan el enlace y pulsan
   **Unirse**. El contador crece hasta **4/4**. Un quinto ingreso recibe sala llena.

El enlace da permiso para entrar, no para hacerse pasar por otro participante.
Cada conexión tiene credencial propia. No cambia al entrar otra persona ni caduca
a los diez minutos: dura hasta que se revoque, regenere o cierre la sala. En
Administrar invitación puedes revocarlo o crear otro. Los miembros actuales siguen
conectados al revocar el enlace; solo se cierra la entrada con ese enlace.

La conexión usa una red local de confianza o una VPN cifrada. No atraviesa NAT ni
configura Internet automáticamente. En Opciones de conexión puedes corregir la
IP elegida automáticamente y el puerto; 0 permite elegir uno libre. Si la IP es
127.0.0.1 solo pueden entrar aplicaciones de ese mismo ordenador. Para amigos en
otras redes, usa la VPN existente o la conexión Cloudflare anterior de dos personas.
No se ha desplegado infraestructura nueva.

## Participar con la partida privada

El control **Compartir mi partida** está visible dentro de la sala y empieza
desactivado. Puedes cambiarlo durante la sesión. Solo cambia tu partida; nadie,
incluido quien creó la sala, puede activarlo por ti ni acceder a una vista privada.

Con el control desactivado los demás ven tu nombre, juego, conexión y los datos
mínimos de las capturas que eliges enlazar: especie, identidad/lugar y sus eventos
Soul Link. No reciben tu equipo completo, cajas, apodos, niveles, PS, estadísticas,
habilidades, objetos o movimientos. Puedes elegir capturas y confirmar avisos sin
mostrar toda la partida. Los mapas y partidas distintos permanecen separados.

Al activarlo compartes la lectura actual completa permitida por el Tracker. Los
demás pueden abrir Ver partida, siempre de solo lectura. Al desactivarlo se retira
esa vista, incluso si alguien la tenía abierta; vuelven a su propia partida. Los
avisos y capturas enlazadas siguen funcionando. Elegir una captura no autoriza
compartir otras capturas, rutas o datos ajenos al enlace.

Las vistas completas no se guardan en cachés persistentes. Un fallo de conexión
las retira y su acceso caduca como máximo a los doce segundos del último mensaje
autorizado; consultar o repetir respuestas no prolonga ese plazo. La revocación se
propaga al sincronizarse. No es posible borrar copias externas hechas mientras
existía permiso ni prometer revocación instantánea sin conexión.

## Capturas y avisos manuales

Cada jugador elige su captura para cada ruta. Hay un grupo activo por ruta/región;
si hay varias capturas, se elige explícitamente. Equipo, cajas, Muertos y marcas
de intercambio conservan la identidad. Una captura ausente no se sustituye por
otra. Entre X/Y, ORAS y USUM no se equiparan rutas por coincidencia de ID.

Activa Avisarme de muertes enlazadas si quieres propuestas de nuevas muertes. Nunca
se marca una muerte automáticamente: puedes ignorarla o confirmar la captura
local enlazada. No hay avisos retroactivos ni rebotes por muertes de respuesta.
La confirmación se comprueba contra sala, partidas, enlace y muerte vigentes; si
el dato ya cambió o fue reanimado, el aviso no se aplica. Reanimar a uno no reanima
a los demás. Ningún participante obtiene control sobre la partida de otro.

## Salir, perder conexión y volver

- **Salir:** libera tu plaza y revoca la conexión. Otra persona puede ocuparla con
  el enlace vigente, sin heredar tus capturas, identidad o eventos.
- **Interrupción o cierre de la app:** la plaza queda reservada para recuperarla.
  El estado muestra desconexión y reserva, no una salida voluntaria. Reinicia,
  pega la invitación de esa sala y entra: la prueba individual guardada recupera
  tu identidad y rota la credencial. La partida vuelve a estar privada.
- **Olvidar conexión guardada:** permite descartar una conexión que ya no puedes
  recuperar. Si el host no estaba disponible, deberá liberar su plaza reservada.
- **Liberar plaza:** el creador puede cerrar una conexión y liberar su lugar. Para
  excluir también a quien conoce el enlace común, debe revocar ese enlace.
- **Cerrar sala:** desconecta a todos. Reiniciar el host requiere crear una sala
  nueva; las credenciales de otra sala no se reutilizan.

La reconexión individual se guarda aparte de las vistas: protegida por la cuenta
de Windows mediante DPAPI, o permisos 0600 en POSIX. Nunca aparece en invitaciones
ni estado compartido. Reiniciar no abre puertos ni inicia conexiones automáticamente.
Un nuevo ingreso tras salir es otra participación y no rescata enlaces anteriores.
Tus datos locales de progreso y las partidas guardadas no se borran.

## Conexiones anteriores

Opciones de conexión conserva pareja Direct, pareja Cloudflare y salas anteriores.
Son modos de compatibilidad que comparten la partida completa como antes; no tienen
el permiso individual del nuevo Soul Link. Para controlarlo, sal de la conexión
anterior y crea/entra en una sala nueva. Una invitación anterior requiere elegir
explícitamente ese modo avanzado, sin bajar silenciosamente la privacidad.
La transición purga únicamente las cachés remotas anteriores al entrar en Soul Link;
conserva identidad de partida, progreso, DGD, límites de nivel y configuración OBS.

## Probar estos cambios desde el código

No se publica una versión ni se reemplaza tu ejecutable instalado. Desde un checkout
actualizado y un entorno Python con las dependencias del proyecto:

```powershell
python -m pip install --require-hashes -r requirements-desktop.lock
python desktop.py
```

Para una prueba segura sin emulador ni partidas reales, abre una terminal por
participante con perfiles independientes y conserva cada URL local anunciada:

```powershell
python server.py --demo --no-browser --profile prueba-soul-1
python server.py --demo --no-browser --profile prueba-soul-2
python server.py --demo --no-browser --profile prueba-soul-3
python server.py --demo --no-browser --profile prueba-soul-4
```

En la primera app abre Soul Link, elige en Opciones de conexión IP127.0.0.1 y puerto0
si todas están en el mismo ordenador, y crea la sala. Pega exactamente la misma
invitación en las otras tres. Prueba compartir/descompartir y enlazar capturas.
Un quinto perfil demuestra sala llena; salir de un invitado permite una entrada nueva.
La demo no acredita jugabilidad. La matriz automatizada incluye unidades, HTTP
loopback, Chromium y una comprobación aislada con WebView2 nativo oculto; no se
afirma haber repetido toda la aceptación jugable o nativa visible del propietario.

Contrato y límites: [SOUL_LINK_PROTOCOL.md](SOUL_LINK_PROTOCOL.md).
