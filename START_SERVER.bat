@echo off
setlocal
title FAYOUM SCAN RIS
cd /d "%~dp0"
if exist "FayoumScanRIS.exe" (
  start "" "FayoumScanRIS.exe"
  echo Starting FAYOUM SCAN RIS server...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "$ok=$false; 1..30 | ForEach-Object { try { $r=Invoke-RestMethod -Uri 'http://127.0.0.1:8787/api/health' -TimeoutSec 1; if($r.ok){$ok=$true;break} } catch {}; Start-Sleep -Seconds 1 }; if($ok){exit 0}else{exit 1}"
  if errorlevel 1 (
    echo.
    echo Server did not become ready within 30 seconds.
    echo Check Windows Firewall and whether port 8787 is already in use.
    pause
    exit /b 1
  )
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
