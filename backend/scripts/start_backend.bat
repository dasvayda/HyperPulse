@echo off
REM Restarts the HyperPulse backend: checks port 8000 for any live process and
REM kills it, then starts a fresh instance in a new window so you can watch
REM the logs live. (start_backend.ps1 also does its own cleanup as a backstop.)

echo Checking for existing process on port 8000...
set FOUND=0
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTENING"') do (
  set FOUND=1
  echo Killing PID %%p
  taskkill /F /PID %%p >nul 2>&1
)
if "%FOUND%"=="0" echo No existing process found on port 8000.

start "HyperPulse Backend" powershell -NoExit -ExecutionPolicy Bypass -File "%~dp0start_backend.ps1"
