@echo off
cd /d "%~dp0"
py -3 server.py --profile segundo-jugador
if errorlevel 1 pause
