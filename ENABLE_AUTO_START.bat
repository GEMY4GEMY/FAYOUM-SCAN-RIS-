@echo off
setlocal
title Enable FAYOUM SCAN RIS Auto Start
cd /d "%~dp0"
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "LINK=%STARTUP%\FayoumScanRIS-AutoStart.cmd"
> "%LINK%" echo @echo off
>>"%LINK%" echo cd /d "%~dp0"
>>"%LINK%" echo if exist "FayoumScanRIS.exe" start "" "FayoumScanRIS.exe"
echo.
echo FAYOUM SCAN RIS automatic startup is ENABLED for this Windows user.
echo The server will start automatically after Windows sign-in.
pause
