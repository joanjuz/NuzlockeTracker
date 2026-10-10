@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  echo No se encontro Python 3. Instalalo desde https://www.python.org/downloads/
  echo Durante la instalacion marca "Add Python to PATH".
  pause
  exit /b 1
)
py -3 Diagnostico_Gen6.py
echo.
echo El archivo JSON se guarda dentro de la carpeta runtime.
pause
