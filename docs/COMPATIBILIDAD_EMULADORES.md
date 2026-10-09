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
