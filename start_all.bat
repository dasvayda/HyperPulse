@echo off
setlocal
set HP_NOPAUSE=1

echo === Checking for existing HyperPulse processes ===
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0kill_existing.ps1"
if errorlevel 1 (
  echo WARNING: Some HyperPulse processes may still be running. Continuing anyway...
)

timeout /t 2 /nobreak >nul

echo === Starting HyperPulse backend ===
call "%~dp0backend\scripts\start_backend.bat"

timeout /t 3 /nobreak >nul

echo === Starting HyperPulse frontend ===
call "%~dp0frontend\start_frontend.bat"

echo.
echo Backend:  http://127.0.0.1:8100
echo Frontend: http://localhost:3100
pause
endlocal
