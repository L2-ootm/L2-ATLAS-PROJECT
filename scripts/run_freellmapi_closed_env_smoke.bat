@echo off
setlocal
cd /d "%~dp0.."

set FREELLMAPI_PATH=<USER_HOME>\AppData\Local\Temp\freellmapi

python scripts\freellmapi_closed_env_smoke.py --freellmapi "%FREELLMAPI_PATH%"

echo.
pause
endlocal
