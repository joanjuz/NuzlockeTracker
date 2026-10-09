@echo off
cd /d "%~dp0"
py -3 server.py --demo
if errorlevel 1 pause
