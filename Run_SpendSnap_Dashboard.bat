@echo off
title SpendSnap AI - Dashboard Control Center
echo =====================================================================
echo    💸 SPENDSNAP AI - YOUR FINANCIAL MEMORY
echo =====================================================================
echo.
echo Starting backend server in the background...

:: Start uvicorn server in a minimized window labeled "SpendSnapBackendServer"
start "SpendSnapBackendServer" /min cmd /c ".\backend\venv\Scripts\python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000"

:: Wait a brief moment for the port to bind
echo Waiting for server initialization...
timeout /t 2 /nobreak > nul

:: Launch the Web Dashboard in the user's default browser
echo Launching Local Dashboard in browser...
start http://127.0.0.1:8000/

echo.
echo =====================================================================
echo  SpendSnap AI is successfully running!
echo  Web Dashboard: http://127.0.0.1:8000/
echo.
echo  -- PRESS ANY KEY IN THIS WINDOW TO SHUT DOWN THE SERVER --
echo =====================================================================
pause > nul

echo Shutting down SpendSnap AI backend...
:: Kill the backend window and its sub-processes
taskkill /fi "windowtitle eq SpendSnapBackendServer" /t /f > nul 2>&1

echo Server stopped. Goodbye!
timeout /t 2 > nul
