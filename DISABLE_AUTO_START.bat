@echo off
setlocal
title Disable FAYOUM SCAN RIS Auto Start
set "LINK=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\FayoumScanRIS-AutoStart.cmd"
if exist "%LINK%" del /q "%LINK%"
echo.
echo FAYOUM SCAN RIS automatic startup is DISABLED for this Windows user.
pause
