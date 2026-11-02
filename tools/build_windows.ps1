# Portable single-file Windows EXE; keep legacy .bat and private runtime OUT of ZIP.
param([string]$Python = 'python')
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $root

# --- Firma Authenticode opcional (docs/FIRMA_CODIGO.md) ----------------------
# Solo se firma si existen WINDOWS_SIGN_PFX_BASE64 y WINDOWS_SIGN_PFX_PASSWORD.
# Sin ellas la compilacion sigue igual y el EXE queda sin firmar. Los valores
# nunca se imprimen; el PFX se decodifica a un archivo temporal que se borra
# siempre. WINDOWS_SIGNTOOL permite indicar una ruta concreta a signtool.exe.
function Find-SignTool {
    if ($env:WINDOWS_SIGNTOOL) {
        if (-not (Test-Path -LiteralPath $env:WINDOWS_SIGNTOOL)) { throw 'WINDOWS_SIGNTOOL no apunta a un archivo existente.' }
        return $env:WINDOWS_SIGNTOOL
    }
    $onPath = Get-Command 'signtool.exe' -ErrorAction SilentlyContinue
    if ($onPath) { return $onPath.Source }
    $kits = Join-Path ${env:ProgramFiles(x86)} 'Windows Kits\10\bin'
    if (Test-Path -LiteralPath $kits) {
        $found = Get-ChildItem -LiteralPath $kits -Directory |
            Where-Object { $_.Name -match '^\d+(\.\d+)+$' } |
            Sort-Object { [version]$_.Name } -Descending |
            ForEach-Object { Join-Path $_.FullName 'x64\signtool.exe' } |
            Where-Object { Test-Path -LiteralPath $_ } |
            Select-Object -First 1
        if ($found) { return $found }
    }
    throw 'No se encontro signtool.exe (Windows SDK). Instala el SDK o define WINDOWS_SIGNTOOL.'
}

function Invoke-OptionalSigning([string]$File) {
    $hasPfx = -not [string]::IsNullOrWhiteSpace($env:WINDOWS_SIGN_PFX_BASE64)
    $hasPassword = -not [string]::IsNullOrEmpty($env:WINDOWS_SIGN_PFX_PASSWORD)
    if (-not $hasPfx -and -not $hasPassword) {
        Write-Host 'Firma de codigo omitida: no hay certificado configurado (EXE sin firmar).'
        return $false
    }
    if (-not ($hasPfx -and $hasPassword)) {
        throw 'Firma de codigo mal configurada: se necesitan WINDOWS_SIGN_PFX_BASE64 y WINDOWS_SIGN_PFX_PASSWORD.'
    }
    $signtool = Find-SignTool
    $pfx = Join-Path ([IO.Path]::GetTempPath()) ('pt-sign-' + [guid]::NewGuid().ToString('N') + '.pfx')
    try {
        try {
            [IO.File]::WriteAllBytes($pfx, [Convert]::FromBase64String($env:WINDOWS_SIGN_PFX_BASE64.Trim()))
        } catch {
            # No reenviar la excepcion original: podria contener parte del valor.
            throw 'WINDOWS_SIGN_PFX_BASE64 no es Base64 valido.'
        }
        # La contrasena nunca va en la linea de comandos de signtool (visible en
        # la lista de procesos): se importa el PFX al almacen del usuario con
        # SecureString y se firma por huella; el certificado se borra al final.
        $secure = ConvertTo-SecureString -String $env:WINDOWS_SIGN_PFX_PASSWORD -AsPlainText -Force
        try {
            $cert = Import-PfxCertificate -FilePath $pfx -CertStoreLocation 'Cert:\CurrentUser\My' -Password $secure
        } catch {
            throw 'No se pudo importar el PFX: comprueba el archivo y la contrasena.'
        }
        $thumbprint = @($cert)[0].Thumbprint
        Remove-Item -LiteralPath $pfx -Force
        try {
            # El servidor de sellado de tiempo puede fallar de forma transitoria.
            $signed = $false
            for ($attempt = 1; $attempt -le 3 -and -not $signed; $attempt++) {
                & $signtool sign /fd SHA256 /td SHA256 /tr 'http://timestamp.digicert.com' `
                    /d 'Pokemon Tracker' /s My /sha1 $thumbprint $File | Out-Host
                if ($LASTEXITCODE -eq 0) { $signed = $true }
                elseif ($attempt -lt 3) {
                    Write-Host ("Firma fallida (intento $attempt de 3); reintentando...")
                    Start-Sleep -Seconds (5 * $attempt)
                }
            }
            if (-not $signed) { throw ('signtool no pudo firmar ' + (Split-Path $File -Leaf) + '.') }
        } finally {
            Get-ChildItem 'Cert:\CurrentUser\My' | Where-Object { $_.Thumbprint -eq $thumbprint } |
                Remove-Item -DeleteKey -ErrorAction SilentlyContinue
        }
    } finally {
        if (Test-Path -LiteralPath $pfx) { Remove-Item -LiteralPath $pfx -Force }
    }
    & $signtool verify /pa $File | Out-Host
    if ($LASTEXITCODE -ne 0) { throw ('La firma de ' + (Split-Path $File -Leaf) + ' no supera signtool verify /pa.') }
    Write-Host ('Firmado y verificado: ' + (Split-Path $File -Leaf))
    return $true
}

# Versiones exactas verificadas por hash (tools/update_desktop_lock.py) para
# que dos compilaciones del mismo commit usen las mismas dependencias.
& $Python -m pip install --require-hashes -r requirements-desktop.lock
if ($LASTEXITCODE -ne 0) { throw 'No se pudieron instalar dependencias de escritorio.' }

# --onefile prevents downloaded/extracted pythonnet DLLs from retaining the
# Windows Mark-of-the-Web that can block Python.Runtime.Loader.Initialize.
# Loading WebView2/WinForms is now part of the frozen smoke test.
# The image was supplied by the project owner. Build a multi-resolution ICO
# so Windows taskbar, Alt+Tab and Explorer show the same app emblem.
$iconSource = Join-Path $root 'assets\app_icon.png'
$iconFile = Join-Path $root 'build\PokemonTracker.ico'
New-Item -ItemType Directory -Force (Split-Path $iconFile) | Out-Null
& $Python -c "from PIL import Image; import sys; i=Image.open(sys.argv[1]).convert('RGBA'); i.save(sys.argv[2],format='ICO',sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])" $iconSource $iconFile
if ($LASTEXITCODE -ne 0) { throw 'No se pudo convertir el icono del programa.' }
$pyi = @('--noconfirm', '--clean', '--windowed', '--onefile', '--icon', $iconFile,
    '--name', 'PokemonTracker', '--collect-all', 'webview',
    '--hidden-import', 'clr', '--exclude-module', 'PyQt5',
    '--exclude-module', 'PyQt6', '--exclude-module', 'PySide2',
    '--exclude-module', 'PySide6',
    '--add-data', 'web;web', '--add-data', 'data;data', 'desktop.py')
& $Python -m PyInstaller @pyi
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller no pudo compilar PokemonTracker.exe.' }

$bundle = Join-Path $root 'dist'
$exe = Join-Path $bundle 'PokemonTracker.exe'
if (-not (Test-Path $exe)) { throw 'No se encontró PokemonTracker.exe.' }
# Firmar antes del smoke test (prueba el EXE firmado) y antes del ZIP.
$null = Invoke-OptionalSigning $exe
# The ZIP contains just the self-extracting EXE, the app license and the guide.
Copy-Item 'LICENSE.txt' (Join-Path $bundle 'LICENSE.txt')
Copy-Item 'docs\INSTALACION_PORTABLE_WINDOWS.txt' (Join-Path $bundle 'LEEME.txt')

# Check packaged executable without opening the window, with isolated data.
$oldAppData = $env:LOCALAPPDATA
try {
    $env:LOCALAPPDATA = Join-Path $root 'build\ci-appdata'
    New-Item -ItemType Directory -Path $env:LOCALAPPDATA -Force | Out-Null
    # Windowed EXEs are launched asynchronously by PowerShell; wait for the
    # real process (and PyInstaller onefile child) before touching the EXE.
    $probe = Start-Process -FilePath $exe -ArgumentList @('--smoke-test', '--profile', 'principal') -WindowStyle Hidden -Wait -PassThru
    if ($probe.ExitCode -ne 0) {
        $logFile = Join-Path $env:LOCALAPPDATA 'PokemonTracker\desktop-error.log'
        if (Test-Path $logFile) { Get-Content $logFile | Write-Host }
        throw 'Falló la prueba del EXE: API o Python.NET / WinForms.'
    }
} finally {
    $env:LOCALAPPDATA = $oldAppData
}

New-Item -ItemType Directory -Force (Join-Path $root 'out') | Out-Null
$zip = Join-Path $root 'out\PokemonTracker-Windows-x64.zip'
if (Test-Path $zip) { Remove-Item $zip -Force }
Compress-Archive -Path @($exe, (Join-Path $bundle 'LICENSE.txt'), (Join-Path $bundle 'LEEME.txt')) -DestinationPath $zip -CompressionLevel Optimal
Write-Host ("Paquete listo: " + $zip)
