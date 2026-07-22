@echo off
set HP_NOPAUSE=1

echo === Stopping existing HyperPulse processes ===
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0kill_existing.ps1"

echo === Stopping HyperPulse frontend ===
call "%~dp0frontend\stop_frontend.bat"

echo === Stopping HyperPulse backend ===
call "%~dp0backend\scripts\stop_backend.bat"

echo Done.
if not defined HP_NOPAUSE pause
