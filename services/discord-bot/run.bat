@echo off
echo Starting L2 BOT...

REM This script assumes Python is in your PATH.
REM Ensure you have installed the dependencies using: pip install -r requirements.txt

echo Starting Discord Bot...
start "L2_Bot_Discord" cmd /c "py -m bot.main & pause"

echo Starting Web Dashboard...
start "L2_Bot_Web" cmd /c "py web/main.py & pause"

timeout /t 5 /nobreak > nul

echo Opening web dashboard in your default browser...
start http://localhost:5000

echo.
echo L2 BOT components are running in separate windows. 