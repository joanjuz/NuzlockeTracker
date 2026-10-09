# Clean portable Windows bundle; keep all legacy .bat files OUT of the ZIP.
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $root

python -m pip install -r requirements-desktop.txt
if ($LASTEXITCODE -ne 0) { throw 'No se pudieron instalar dependencias de escritorio.' }

$pyi = @('--noconfirm', '--clean', '--windowed', '--onedir',
    '--name', 'PokemonTracker', '--collect-all', 'webview',
    '--hidden-import', 'clr', '--exclude-module', 'PyQt5',
    '--exclude-module', 'PyQt6', '--exclude-module', 'PySide2',
    '--exclude-module', 'PySide6',
    '--add-data', 'web;web', '--add-data', 'data;data', 'desktop.py')
python -m PyInstaller @pyi
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller no pudo compilar PokemonTracker.exe.' }

$bundle = Join-Path $root 'dist\PokemonTracker'
$exe = Join-Path $bundle 'PokemonTracker.exe'
if (-not (Test-Path $exe)) { throw 'No se encontró PokemonTracker.exe.' }
Copy-Item 'LICENSE.txt' (Join-Path $bundle 'LICENSE.txt')
Copy-Item 'docs\DESKTOP_WINDOWS.md' (Join-Path $bundle 'LEEME.txt')

# Check packaged executable without opening the window, with isolated data.
$oldAppData = $env:LOCALAPPDATA
try {
    $env:LOCALAPPDATA = Join-Path $root 'build\ci-appdata'
    New-Item -ItemType Directory -Path $env:LOCALAPPDATA -Force | Out-Null
    & $exe --smoke-test --profile principal
    if ($LASTEXITCODE -ne 0) { throw 'Falló la prueba del ejecutable compilado.' }
} finally {
    $env:LOCALAPPDATA = $oldAppData
}

New-Item -ItemType Directory -Force (Join-Path $root 'out') | Out-Null
$zip = Join-Path $root 'out\PokemonTracker-Windows-x64.zip'
if (Test-Path $zip) { Remove-Item $zip -Force }
Compress-Archive -Path (Join-Path $bundle '*') -DestinationPath $zip -CompressionLevel Optimal
Write-Host ("Paquete listo: " + $zip)
