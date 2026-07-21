@echo off
echo Stopping HyperPulse frontend (port 3100)...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":3100" ^| findstr "LISTENING"') do (
  echo Killing PID %%p
  taskkill /F /PID %%p >nul 2>&1
)
echo Done.
if not defined HP_NOPAUSE pause
