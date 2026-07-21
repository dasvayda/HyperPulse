@echo off
REM Stops the HyperPulse backend running on port 8100.
powershell -ExecutionPolicy Bypass -File "%~dp0stop_backend.ps1"
if not defined HP_NOPAUSE pause
