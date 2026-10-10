@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
if exist "%~dp0Diagnostico_Gen6.exe" (
  "%~dp0Diagnostico_Gen6.exe"
) else (
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
