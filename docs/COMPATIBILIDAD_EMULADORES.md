# Estado de compatibilidad de emuladores y juegos

## Pokémon Ultra Sol y Ultra Luna (versión 1.0)

- **Lime3DS / Windows 64 bits: validado manualmente por el usuario**. Lectura de equipo, cajas, PS de combate, rutas y Soul Link, usando lectura de memoria del proceso.
- **Azahar y Citra: experimentales, pendientes de validar en Windows**. El detector ahora puede localizar procesos con ejecutables `azahar*.exe` o `citra*.exe` además de `lime3ds*.exe`. Esto **no confirma** que el mapeo de RAM del proceso, las firmas, offsets y acceso a cajas o PS de combate funcionen igual. El conector seguirá validando datos reales y rechazando RAM inválida; no modifica memoria de ningún emulador.
- En Windows, para probar Azahar o Citra: abrir únicamente ese emulador y cargar una partida USUM 1.0, seleccionar modo **Memoria Windows**, conectar y verificar equipo, cajas y PS de combate. Si hay varios emuladores, introducir el PID. Guardar el diagnóstico ante error y reportar el ejecutable, versión, juego y mensaje; **no enviar ROM, save, secretos ni volcados completos de RAM**.
- GDB (puerto local) sigue siendo experimental. Que un emulador soporte GDB remoto no garantiza que acepte las lecturas actuales sin cambios; verificar protocolo y dirección base.
- Hay una sola capa de RAM virtual de USUM implementada. Los métodos de descubrimiento estático/dinámico y el proceso anfitrión pueden requerir adaptaciones por emulador. No marcar Azahar ni Citra como **soportados** antes de pruebas reales de campo.

## Juegos pendientes — fuera de esta rama

- **Pokémon Rubí Omega / Zafiro Alfa (ORAS)**: requiere perfiles de direcciones, tamaños de estructuras, rutas y memoria de combate específicos de Gen6. No usar los offsets de USUM.
- **Pokémon X / Y**: mismas necesidades de perfiles Gen6, pero validar por separado respecto a ORAS.
- Ambos quedan expresamente en backlog; no se implementan ni se anuncian como compatibles en esta entrega.

## Criterio de cierre

La rama de escritorio/layout podrá integrarse una vez que el usuario valide la ventana, la conservación de sesiones, los seis sprites PNG cambiantes y Soul Link en ambas partidas. La compatibilidad Azahar/Citra solo pasará de experimental a validada tras pruebas de lectura reales con esos emuladores. ORAS y X/Y continuarán en el backlog.

## Error de permisos WinError 5 en Azahar (diagnóstico específico)
Si aparece «Acceso denegado» en Azahar, el conector identifica ahora
proceso, PID, etapa OpenProcess y error 5 en un mensaje en español.
La lectura requiere PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, no acceso
total. VirtualQueryEx necesita el primer permiso; un fallback de solo
PROCESS_QUERY_LIMITED_INFORMATION no es suficiente para localizar RAM.
Abrir Azahar normalmente, sin elevación distinta de Pokémon Tracker, y
seleccionar su PID si existen otros procesos. No se garantiza soporte sin
pruebas con partidas y versiones concretas.

## Ultra Luna en Azahar: búsqueda dinámica y diagnóstico (experimental)

El tracker utilizaba la búsqueda por dirección fija para Ultra Luna, incluso dentro de Azahar. Esto puede fallar si el emulador reubica la RAM virtual. Se ha cambiado el conector para que **Azahar y Citra usen búsqueda dinámica**, la misma familia de método que Ultra Sol ya utiliza, mientras que **Lime3DS + Ultra Luna conserva la búsqueda fija** para evitar regresiones.

El menú **··· → Guardar diagnóstico** ahora escribe un JSON real en `%LOCALAPPDATA%\\PokemonTracker\\runtime\\diagnosticos` (o `runtime/profiles/segundo-jugador/diagnosticos`) y muestra la ruta, porque WebView2 puede bloquear las descargas iniciadas con blobs. El archivo registra nombre de proceso, PID, regiones exploradas, bytes, firmas y rechazos. No incluye ROM, partidas completas ni tokens Soul Link.

La sincronización de PS puede adelantarse a la animación del combate, porque la lectura de memoria observa los valores internos que el juego actualiza antes de dibujarlos. No se introducen retrasos artificiales que puedan ocultar estados válidos.

Esta corrección sigue pendiente de validar con **Azahar + Ultra Luna** real. Si falla, enviar el JSON generado, sin volcados completos de memoria ni credenciales.

## Instalación portable y estado de compatibilidad

El ejecutable no depende de una computadora en particular: Windows 10/11 x64,
WebView2 Runtime y autorización normal de lectura de memoria bastan para
iniciar la aplicación. La compatibilidad con el emulador/juego específico
se valida por separado (Lime3DS/Azahar probados en el entorno del usuario);
el empaquetado no incluye partidas, ROM, plantillas o tokens. El progreso y
Soul Link se guardan por equipo en `%LOCALAPPDATA%\\PokemonTracker\\runtime`
y requieren importación/copias seguras al cambiar de computadora.

ORAS y X/Y siguen pendientes; no se incluyen perfiles de RAM Gen6.
