# Probar Soul Link con dos Lime3DS en una sola computadora

Desde v0.22.1 experimental, cada jugador necesita **su propio proceso del tracker**, no solo otra pestaña del navegador. Ambos procesos corren en puertos diferentes y guardan el progreso y las credenciales por separado.

## Preparación
1. Mantén la pareja ya creada en el perfil **principal**: abre `Iniciar.bat` para ese jugador. Sus datos existentes en `runtime/` no cambian.
2. Abre `Iniciar_Segundo_Jugador.bat` desde la misma carpeta. Se abre un segundo servidor con un puerto local diferente y el indicador **Sesión segundo-jugador**. Sus datos se guardan en `runtime/profiles/segundo-jugador/`.
3. Abre dos procesos de Lime3DS: uno con Ultra Sol y otro con Ultra Luna, ambos con la partida cargada.
4. En PowerShell, obtén los PID de ambos emuladores con:

```powershell
Get-Process | Where-Object { $_.ProcessName -like 'lime3ds*' } | Select-Object Id, ProcessName, MainWindowTitle
```

5. En el tracker **principal**, sección Conexión, elige Ultra Sol 1.0 y escribe el **PID de ese Lime3DS**, luego Conectar. En el tracker **segundo-jugador**, elige Ultra Luna 1.0 y su **otro PID**, luego Conectar. Si no estás seguro de qué PID corresponde a cada juego, cierra temporalmente uno de los emuladores para identificarlo; no inventes el PID.
6. En el principal abre `··· → Sincronizar compañero`, copia su código de invitación. **No crees otra pareja** si ya tienes una creada.
7. En el segundo abre el mismo menú, utiliza `Unirme a mi compañero` con la misma URL del Worker y el código de invitación. No escribas CREATE_KEY en el segundo.
8. Cada proceso sincroniza su propio juego a Cloudflare y consulta la última sesión del otro. Tras vincularlos aparecerá el botón **Compañero**.

## Seguridad y almacenamiento
- `Iniciar.bat` mantiene sus credenciales previas en `runtime/companion-credentials.json`; **no las borres**.
- `Iniciar_Segundo_Jugador.bat` guarda su propia cuenta en `runtime/profiles/segundo-jugador/companion-credentials.json`.
- El archivo local `runtime/state.json` y el progreso anterior permanecen intactos. La sincronización no cambia la partida ni conecta dos ROM entre sí.
- No compartas `CREATE_KEY`, tokens o archivos de `runtime`.
- Si el código de invitación ya caducó, habrá que crear una pareja nueva desde el primer perfil (desvincular destruye los snapshots de la pareja anterior). No pulses Desvincular solo para abrir una segunda instancia.
- Mantén abiertas ambas ventanas de consola. Para terminar, cierra los servidores con Ctrl+C.
- Cada tracker necesita un **PID distinto** si ambos Lime3DS están abiertos. El conector no elige automáticamente entre varios Lime3DS.

## Otros perfiles
También se puede abrir `py -3 server.py --profile nombre-del-jugador`. El nombre admite letras minúsculas, números, guion y guion bajo, hasta 32 caracteres. Todos se separan en `runtime/profiles/NOMBRE/`; la versión normal sin parámetros conserva `runtime/`.
