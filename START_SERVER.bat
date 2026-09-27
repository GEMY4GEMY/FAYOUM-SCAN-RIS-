@echo off
title FAYOUM SCAN RIS
cd /d "%~dp0"
if exist "FayoumScanRIS.exe" (
  start "" "FayoumScanRIS.exe"
  timeout /t 3 /nobreak >nul
  start "" "http://127.0.0.1:8787"
  exit /b 0
)
if exist "server\app.py" (
  python server\app.py
  pause
  exit /b 0
)
echo FayoumScanRIS.exe was not found.
echo Please keep START_SERVER.bat beside the EXE.
pause
