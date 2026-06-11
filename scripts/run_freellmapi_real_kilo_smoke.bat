@echo off
setlocal
cd /d "%~dp0.."

set FREELLMAPI_PATH=C:\Users\Davi\AppData\Local\Temp\freellmapi

python scripts\freellmapi_real_kilo_smoke.py --freellmapi "%FREELLMAPI_PATH%"

echo.
pause
endlocal
