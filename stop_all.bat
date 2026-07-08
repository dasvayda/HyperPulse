@echo off
set HP_NOPAUSE=1

echo === Stopping HyperPulse frontend ===
call "%~dp0frontend\stop_frontend.bat"

echo === Stopping HyperPulse backend ===
call "%~dp0backend\scripts\stop_backend.bat"

echo Done.
pause
