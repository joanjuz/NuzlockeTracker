# Firma de código del ejecutable Windows

`PokemonTracker.exe` se publica hoy **sin firmar**. Windows SmartScreen muestra
entonces "Windows protegió su PC" y el editor aparece como desconocido. Este
documento explica qué está preparado en el repositorio, qué opciones existen
para obtener un certificado y cómo activarlo.

## Qué hace el repositorio

`tools/build_windows.ps1` firma el EXE **solo si** existen estas dos variables de
entorno:

| Variable | Contenido |
| --- | --- |
| `WINDOWS_SIGN_PFX_BASE64` | El archivo `.pfx` (certificado + clave privada) codificado en Base64 |
| `WINDOWS_SIGN_PFX_PASSWORD` | La contraseña del `.pfx` |

Opcionalmente, `WINDOWS_SIGNTOOL` indica la ruta exacta de `signtool.exe`; si no
se define, el script lo busca en el `PATH` y en el Windows SDK
(`C:\Program Files (x86)\Windows Kits\10\bin\<versión>\x64`).

Orden de la compilación:

1. PyInstaller genera `dist\PokemonTracker.exe`.
2. **Firma** con `signtool sign /fd SHA256 /td SHA256 /tr http://timestamp.digicert.com`
   (digest SHA-256 y sello de tiempo RFC 3161, con hasta tres intentos si el
   servidor de sellado falla).
3. Comprobación con `signtool verify /pa`. Si falla, la compilación se detiene.
4. Smoke test (`--smoke-test`) sobre el EXE **ya firmado**.
5. ZIP y `SHA256SUMS.txt`, calculados sobre el EXE firmado.

Comportamiento según la configuración:

- **Ninguna variable definida:** se escribe "Firma de código omitida" y la
  compilación continúa igual que antes. Es el caso de las compilaciones locales,
  de las pull requests y de cualquier release mientras no haya certificado.
- **Solo una de las dos:** la compilación falla con un mensaje claro, para no
  publicar sin firma por un error de configuración.
- **Ambas:** se firma y verifica.

Protección de los secretos:

- El script no imprime nunca el contenido de las variables. Si el Base64 no es
  válido, el error es genérico y no incluye el valor.
- El `.pfx` se decodifica a un archivo temporal con nombre aleatorio y se borra
  en un bloque `finally`, también si la firma falla.
- En `release-windows.yml` los secretos se pasan **solo** al paso de compilación
  (`env:` del paso), no al trabajo completo. GitHub además enmascara los
  secretos en los registros.
- La contraseña llega a `signtool` como argumento `/p`; en un runner de GitHub
  (máquina efímera) eso es aceptable. En un equipo compartido, preferir un
  certificado instalado en el almacén de Windows o en un token hardware.
- El workflow de pull requests (`windows-desktop.yml`) **no** recibe los
  secretos: solo el workflow de publicación manual.

Tras la compilación, el paso "Verificar paquete" del workflow de publicación
añade al resumen del job el estado de `Get-AuthenticodeSignature`
(`Valid` si está firmado, `NotSigned` si no).

## Opciones para obtener la firma

### 1. SignPath Foundation (gratuito para código abierto)

[SignPath Foundation](https://signpath.org/) firma gratis proyectos de código
abierto que cumplan sus condiciones (licencia OSI, repositorio público,
compilación reproducible desde CI, mantenedores identificados, entre otras).

- Hay que **solicitarlo** y esperar la aprobación; no es inmediato.
- El certificado pertenece a SignPath Foundation y aparece como editor del EXE.
- La clave privada nunca sale del HSM de SignPath, así que **no hay `.pfx`**: la
  firma se hace enviando el artefacto desde GitHub Actions con su acción
  oficial (`signpath/github-action-submit-signing-request`). Si se elige esta
  opción, el paso de firma de `build_windows.ps1` no se usa: hay que añadir un
  paso en `release-windows.yml` que suba `dist\PokemonTracker.exe` a SignPath,
  descargue el firmado y repita el smoke test antes del ZIP.

### 2. Azure Trusted Signing

Servicio de Microsoft con certificados de corta duración gestionados en Azure.

- Requiere suscripción de Azure y pago mensual, y una validación de identidad
  (persona u organización). La disponibilidad según país y tipo de solicitante
  es limitada: comprobar las condiciones vigentes antes de contratar.
- Tampoco entrega un `.pfx`: se firma con `signtool` y el complemento de Azure
  (`Azure.CodeSigning.Dlib`) o con la acción de GitHub de Microsoft, usando
  credenciales de Azure guardadas como secretos. Igual que con SignPath, habría
  que sustituir el paso de firma actual por el del servicio.

### 3. Certificado comercial OV (Organization Validation)

Se compra a una autoridad de certificación (DigiCert, Sectigo, SSL.com, etc.).

- Desde junio de 2023 las autoridades emiten la clave privada **solo en hardware**
  (token USB o HSM en la nube). En la práctica ya no se obtiene un `.pfx`
  exportable, de modo que el flujo con `WINDOWS_SIGN_PFX_BASE64` solo sirve para
  certificados exportables anteriores o para pruebas.
- Con HSM en la nube (por ejemplo, el servicio de firma remota de la propia CA)
  se usa su herramienta o su complemento de `signtool` en un paso del workflow.
- Un certificado EV ya no concede reputación inmediata en SmartScreen; la
  diferencia con OV es menor que antes.

### Prueba local con certificado autofirmado

Útil para comprobar el script, **no** para publicar (Windows no confía en él y
`signtool verify /pa` fallará salvo que se instale su raíz en el equipo):

```powershell
$cert = New-SelfSignedCertificate -Type CodeSigningCert -Subject 'CN=Pokemon Tracker (prueba)' -CertStoreLocation Cert:\CurrentUser\My
$pass = Read-Host 'Contraseña para el PFX' -AsSecureString
Export-PfxCertificate -Cert $cert -FilePath "$env:TEMP\prueba.pfx" -Password $pass
```

## Añadir los secretos en GitHub

1. Convertir el `.pfx` a Base64 sin dejar copias en el repositorio:

   ```powershell
   [Convert]::ToBase64String([IO.File]::ReadAllBytes('C:\ruta\certificado.pfx')) | Set-Clipboard
   ```

2. En GitHub: **Settings → Secrets and variables → Actions → New repository
   secret**.
   - Nombre `WINDOWS_SIGN_PFX_BASE64`, valor: pegar el portapapeles.
   - Nombre `WINDOWS_SIGN_PFX_PASSWORD`, valor: la contraseña del `.pfx`.

   Con la CLI de GitHub (pide el valor sin mostrarlo en pantalla):

   ```powershell
   gh secret set WINDOWS_SIGN_PFX_PASSWORD
   [Convert]::ToBase64String([IO.File]::ReadAllBytes('C:\ruta\certificado.pfx')) | gh secret set WINDOWS_SIGN_PFX_BASE64
   ```

3. Vaciar el portapapeles y borrar cualquier copia temporal del `.pfx` o del
   Base64. **Nunca** subir el `.pfx`, el Base64 ni la contraseña al repositorio,
   a issues o a los registros.
4. Lanzar el workflow **Publicar Progressive Tracker para Windows** y revisar en
   el resumen que la firma aparece como `Valid`.

Límite: un secreto de GitHub admite hasta 48 KB; un `.pfx` habitual en Base64
ocupa bastante menos.

Para retirar la firma basta con borrar los dos secretos: la siguiente
compilación vuelve a generar el EXE sin firmar.

## SmartScreen y la reputación

Firmar no elimina de inmediato el aviso de SmartScreen. Windows asigna
reputación al certificado (y al archivo) según cuántas personas lo descargan y
ejecutan sin incidencias, y eso se acumula con el tiempo. Las primeras versiones
firmadas pueden seguir mostrando el aviso; con el mismo certificado, las
siguientes lo pierden antes. Cambiar de certificado reinicia esa reputación.

Mientras tanto, la guía de instalación (`docs/INSTALACION_PORTABLE_WINDOWS.txt`)
indica comprobar que la descarga procede del release oficial, y
`SHA256SUMS.txt`, publicado junto al ZIP, permite comparar el hash del archivo
descargado. Cuando haya firma, conviene actualizar la frase "El programa no esta
firmado digitalmente" de esa guía.
