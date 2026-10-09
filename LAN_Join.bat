@echo off
cd /d "%~dp0"
set /p "TRACKER=URL de tu tracker local (http://127.0.0.1:PUERTO/): "
set /p "HOST=URL sala (http://IP_ANFITRION:8765/): "
set /p "SLOT=Puesto (A-SUN, A-MOON, B-SUN, B-MOON): "
set /p "CODE=Clave de ese puesto: "
set /p "NAME=Nombre que aparecera en la sala: "
py -3 -m lan.client --tracker "%TRACKER%" --host "%HOST%" --slot "%SLOT%" --token "%CODE%" --name "%NAME%"
if errorlevel 1 pause
