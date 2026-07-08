@echo off
set HP_NOPAUSE=1

echo === Starting HyperPulse backend ===
call "%~dp0backend\scripts\start_backend.bat"

timeout /t 3 /nobreak >nul

echo === Starting HyperPulse frontend ===
call "%~dp0frontend\start_frontend.bat"

echo.
echo Backend:  http://127.0.0.1:8000
echo Frontend: http://localhost:3000
pause
