@echo off
setlocal
chcp 65001 >nul
rem En el paquete de diagnostico el .bat esta junto a Diagnostico_Gen6.exe;
rem en el repositorio vive en tools\ y ejecuta el script desde la raiz.
if exist "%~dp0Diagnostico_Gen6.exe" (
  cd /d "%~dp0"
  "%~dp0Diagnostico_Gen6.exe"
) else (
  cd /d "%~dp0.."
  where py >nul 2>nul
  if errorlevel 1 (
    echo No se encontro Diagnostico_Gen6.exe ni Python 3.
    echo Usa el paquete de diagnostico completo. No necesitas instalar Python.
    pause
    exit /b 1
  )
  py -3 "%~dp0Diagnostico_Gen6.py"
)
echo.
echo Busca el JSON en la carpeta runtime junto al diagnostico.
pause
