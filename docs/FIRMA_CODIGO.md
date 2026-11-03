# Firma de código del ejecutable Windows

`PokemonTracker.exe` se publica hoy **sin firmar**. Windows SmartScreen muestra
entonces "Windows protegió su PC" y el editor aparece como desconocido. Este
documento explica qué está preparado en el repositorio, qué opciones existen
para obtener un certificado y cómo activarlo.

El workflow de publicación (`.github/workflows/release-windows.yml`) admite tres
modos y elige uno solo, sin mostrar nunca el valor de los secretos:

| Modo | Se activa cuando | Resultado |
| --- | --- | --- |
| `signpath` | Existen el secreto `SIGNPATH_API_TOKEN` y las variables `SIGNPATH_ORGANIZATION_ID`, `SIGNPATH_PROJECT_SLUG` y `SIGNPATH_SIGNING_POLICY_SLUG` | SignPath firma el EXE (ver [SignPath Foundation](#signpath-foundation-paso-a-paso)) |
| `pfx` | No hay SignPath y existen `WINDOWS_SIGN_PFX_BASE64` y `WINDOWS_SIGN_PFX_PASSWORD` | `build_windows.ps1` firma con `signtool` |
| `unsigned` | No hay nada configurado | EXE sin firmar, igual que hasta ahora |

SignPath tiene prioridad: si también existen los secretos PFX, se ignoran (con un
aviso en el registro). Si SignPath está **a medias** (por ejemplo, las variables
sin el token), la publicación se detiene con la lista de lo que falta, para no
publicar sin firma por error. En los modos `signpath` y `pfx`, el paso
"Verificar paquete" exige que `Get-AuthenticodeSignature` devuelva `Valid`.

## Firma con PFX en `build_windows.ps1`

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
  (`env:` del paso) y solo en modo `pfx`, no al trabajo completo. GitHub además
  enmascara los secretos en los registros.
- La contraseña **no** va en la línea de comandos de `signtool`: el script
  importa el `.pfx` al almacén del usuario con `SecureString`, firma por huella
  (`/sha1`) y borra el certificado y su clave al terminar, también si falla.
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
  oficial (`signpath/github-action-submit-signing-request`). El workflow de
  publicación ya incluye ese camino; los pasos para activarlo están en
  [SignPath Foundation paso a paso](#signpath-foundation-paso-a-paso).

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

## SignPath Foundation paso a paso

### Cómo funciona en el workflow

Con el modo `signpath`, el trabajo `build` de `release-windows.yml` hace:

1. Pruebas Python, JavaScript y del Worker, igual que en los otros modos.
2. `build_windows.ps1 -Stage Build`: PyInstaller y smoke test del EXE **sin
   firmar**. No firma ni crea el ZIP.
3. Sube `dist/PokemonTracker.exe` como artefacto de GitHub
   (`PokemonTracker-sin-firmar-<tag>`, se borra al día siguiente). GitHub
   entrega los artefactos como un ZIP con `PokemonTracker.exe` en la raíz.
4. `signpath/github-action-submit-signing-request` (fijada por SHA, v3.0) envía
   ese artefacto a SignPath, espera hasta 60 minutos (tiempo para la aprobación
   manual) y descarga el resultado en `build/signpath-signed/`.
5. Comprueba que el EXE devuelto es distinto del enviado, que
   `Get-AuthenticodeSignature` da `Valid` y que la firma lleva sello de tiempo;
   escribe el firmante en el resumen del job y sustituye
   `dist/PokemonTracker.exe`.
6. `build_windows.ps1 -Stage Package`: smoke test (`--smoke-test`) sobre el EXE
   **firmado** y ZIP con ese EXE.
7. "Verificar paquete" exige firma `Valid`, que el ZIP tenga solo los tres
   archivos y que el EXE del ZIP sea idéntico al publicado suelto.
   `SHA256SUMS.txt` se calcula después, sobre los archivos firmados.

El trabajo `publish` (el único con permiso de escritura) descarga ese paquete,
comprueba `SHA256SUMS.txt` y crea el release.

Permisos y separación de trabajos: la acción de SignPath recibe el
`GITHUB_TOKEN` del trabajo para leer el job y descargar el artefacto. Por eso
`build` tiene solo `contents: read` y `actions: read`: SignPath no recibe nunca
un token capaz de escribir en el repositorio ni de publicar. El token de la API
de SignPath solo se entrega al paso de firma.

Compatibilidad: el modo `signpath` usa `-Stage Build` y `-Stage Package`, que
solo existen en `build_windows.ps1` desde este cambio. El workflow compila el
código de la **etiqueta** indicada, así que solo funciona con etiquetas creadas
después de incorporar este cambio a la rama publicada. Los modos `pfx` y
`unsigned` siguen llamando al script sin argumentos y funcionan con etiquetas
antiguas.

### 1. Antes de solicitarlo

Condiciones de SignPath Foundation que conviene revisar en
<https://signpath.org/terms> (pueden cambiar):

- Licencia aprobada por OSI (el proyecto usa GPL-3.0) y repositorio público.
- El binario se compila en CI a partir del código del repositorio (GitHub
  Actions en runners alojados por GitHub, como hace este workflow).
- Al menos una versión publicada y el proyecto mantenido.
- Todos los miembros con acceso a SignPath y al repositorio con
  autenticación en dos pasos.
- Una **política de firma de código** visible en el README o en la web del
  proyecto, con:
  - la frase "Free code signing provided by SignPath.io, certificate by
    SignPath Foundation" (con los enlaces a <https://signpath.io> y
    <https://signpath.org>);
  - los roles del equipo: quién puede hacer commits, quién revisa y quién
    aprueba cada firma;
  - una declaración de privacidad. La aplicación sí se conecta a la red en
    algunos casos (Soul Link Companion con el Worker de Cloudflare, descarga de
    sprites desde GitHub, compartir overlay); la declaración debe decir qué se
    envía y cuándo, no que el programa nunca usa la red.
- Puede que pidan metadatos de versión en el EXE (nombre de producto, versión).
  Hoy PyInstaller lo compila sin recurso de versión (`--version-file`); si lo
  exigen, hay que añadirlo en `build_windows.ps1` antes de firmar.

### 2. Solicitud

1. Abrir <https://signpath.org> y seguir el enlace de solicitud para proyectos
   de código abierto ("Apply").
2. Indicar el repositorio `https://github.com/joanjuz/NuzlockeTracker`, la
   licencia, el enlace a la política de firma y el artefacto a firmar: un único
   `PokemonTracker.exe` (PE de Windows x64) generado por
   `.github/workflows/release-windows.yml`.
3. Esperar la aprobación. SignPath crea entonces la organización y el proyecto
   en <https://app.signpath.io>.

### 3. Configuración en SignPath (tras la aprobación)

1. **Proyecto**: comprobar que está vinculado al repositorio de GitHub y que
   tiene el *Trusted Build System* "GitHub.com" (lo configura SignPath
   Foundation; permite verificar que el artefacto sale de este workflow).
2. **Artifact configuration** para un solo EXE. Como el artefacto de GitHub es
   un ZIP, la raíz es `<zip-file>`:

   ```xml
   <?xml version="1.0" encoding="utf-8"?>
   <artifact-configuration xmlns="http://signpath.io/artifact-configuration/v1">
     <zip-file>
       <pe-file path="PokemonTracker.exe">
         <authenticode-sign />
       </pe-file>
     </zip-file>
   </artifact-configuration>
   ```

   Marcarla como predeterminada del proyecto, o guardar su *slug* en la
   variable opcional `SIGNPATH_ARTIFACT_CONFIGURATION_SLUG`.
3. **Políticas de firma**: SignPath Foundation suele crear `test-signing`
   (certificado de prueba, sin aprobación) y `release-signing` (certificado
   real, requiere que un aprobador acepte cada solicitud en la web de
   SignPath). Para publicar se usa `release-signing`.
4. **Usuario de CI y token**: en *Users*, crear un usuario de CI (o usar el
   propio) y generar su **API token**. Añadirlo como *Submitter* en la política
   de firma que se vaya a usar. El token solo se muestra una vez.
5. Anotar el **Organization ID** (en *Settings* de la organización, es un GUID),
   el *slug* del proyecto y el *slug* de la política.

### 4. Secretos y variables en GitHub

En **Settings → Secrets and variables → Actions**:

| Tipo | Nombre | Valor |
| --- | --- | --- |
| Secret | `SIGNPATH_API_TOKEN` | Token de la API del usuario de CI |
| Variable | `SIGNPATH_ORGANIZATION_ID` | GUID de la organización |
| Variable | `SIGNPATH_PROJECT_SLUG` | *Slug* del proyecto |
| Variable | `SIGNPATH_SIGNING_POLICY_SLUG` | `release-signing` (o `test-signing` para probar) |
| Variable (opcional) | `SIGNPATH_ARTIFACT_CONFIGURATION_SLUG` | *Slug* de la configuración de artefacto, si no es la predeterminada |

Con la CLI de GitHub (el secreto se pide sin mostrarlo):

```powershell
gh secret set SIGNPATH_API_TOKEN
gh variable set SIGNPATH_ORGANIZATION_ID --body '<guid-de-la-organizacion>'
gh variable set SIGNPATH_PROJECT_SLUG --body '<slug-del-proyecto>'
gh variable set SIGNPATH_SIGNING_POLICY_SLUG --body 'release-signing'
```

Solo el ID de la organización y los *slugs* van en variables (no son secretos).
El token **nunca** debe ir en una variable, en el repositorio ni en issues.

### 5. Primera prueba y publicación

1. Probar primero con `SIGNPATH_SIGNING_POLICY_SLUG=test-signing`. El
   certificado de prueba no es de confianza en Windows, así que el paso
   "Verificar firma de SignPath" se detendrá con un estado distinto de `Valid`
   (por ejemplo `UnknownError`). Es lo esperado: confirma el envío y la
   descarga, y como el trabajo `build` falla, **no se publica nada**.
2. Cambiar la variable a `release-signing`, lanzar el workflow con la etiqueta
   nueva y aprobar la solicitud en SignPath mientras el job espera (hasta 60
   minutos; el trabajo tiene 90 de límite).
3. Revisar en el resumen del job "Metodo de firma: signpath", el firmante y
   "Firma Authenticode del EXE: Valid".
4. Actualizar `docs/INSTALACION_PORTABLE_WINDOWS.txt`, el README y las notas
   de versión, que hoy dicen que el EXE no está firmado.

Para volver a publicar sin firma basta con borrar el secreto y las tres
variables (no dejar solo una parte: el workflow lo rechaza).

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
