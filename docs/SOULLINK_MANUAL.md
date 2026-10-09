# Soul Link manual (versión experimental)

## Juegos admitidos

Se puede enlazar **Ultra Sol + Ultra Sol**, **Ultra Luna + Ultra Luna**,
**Ultra Sol + Ultra Luna** y **Ultra Luna + Ultra Sol**. La identidad del
juego propio y la del compañero se conservan sin convertir las partidas.

**Importante:** la restricción de juegos distintos existía en el
Cloudflare Worker, no solo en la aplicación. Una vez validado el PR,
despliega su versión nueva desde la carpeta
`cloudflare/companion-worker`:

```powershell
cd "D:\Progra\NuzlockeTracker\cloudflare\companion-worker"
npx wrangler deploy
```

No es necesario borrar la base D1, cambiar el secreto CREATE_KEY ni
desvincular parejas existentes; el endpoint /v1/pairs/join deja de
requerir juegos diferentes.

## Muerte vinculada, bajo control del jugador

- Al entrar en **··· → Sincronizar compañero**, se puede activar la casilla
  **Activar avisos Soul Link por ruta**. Permanece desactivada de forma
  predeterminada.
- Si el compañero registra la muerte de un Pokémon nuevo, el tracker
  busca entre tu Equipo y tus Cajas leídas un Pokémon vivo capturado
  en la misma ruta, según el identificador de encuentro y los grupos de rutas.
- Muestra un aviso discreto con el sprite, el Pokémon y dos decisiones:
  **Marcar muerte** o **Ignorar**.
- **Nunca se modifica la ROM, el save o el estado del compañero**, y nunca
  se registra una muerte sin el clic del jugador.
- Las muertes remotas ya registradas cuando activas la función no crean
  avisos retroactivos. Ignorar un aviso no lo vuelve a mostrar en la sesión.
- Si hay varias capturas en una misma ruta, el sistema propone la primera
  candidata válida; es importante revisarla antes de seleccionar Marcar muerte.
- Los avisos se comprueban mientras ambos trackers estén sincronizando
  y el emulador local proporcione una lectura en vivo.
- Este sistema sigue siendo experimental hasta validar dos PCs y los
  distintos nombres de rutas (especialmente cuando cada juego tiene
  ubicaciones exclusivas).

## Contador de muertes

Se muestra a la izquierda del mini-equipo superior. El valor se guarda por
perfil y partida en el registro local de progreso; es **acumulativo** e
independiente del número de Pokémon actualmente en Muertos.

- Muerte manual o detectada por PS=0 → contador +1 (sin duplicados).
- **Revivir** → se quita del registro Muertos; pregunta si también quieres
  restar una muerte del contador.
- Elegir No conserva el número acumulado; elegir Sí reduce en 1, nunca
  por debajo de cero.
- Un progreso previo sin contador se migra automáticamente empezando por
  la cantidad de muertes registradas en ese momento.

## Icono de escritorio

El archivo `assets/app_icon.png` deriva del icono original enviado por el
propietario del proyecto. La compilación PyInstaller crea un ICO multirresolución
en `build/PokemonTracker.ico` y lo usa en el ejecutable Windows. El mismo
emblema se usa como favicon y en la cabecera de la aplicación.

## Seguridad y alcance

Los avisos Soul Link son un apoyo visual. No se garantiza encontrar una
pareja si la ruta no se puede asociar con los datos disponibles o si no
se leyeron las cajas. El contador, las opciones locales y el progreso no
necesitan enviarse a servicios distintos del Worker existente. Los tokens
y las claves siguen guardados por perfil, no en el repositorio.
