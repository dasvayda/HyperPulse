@echo off
echo Stopping HyperPulse frontend (port 3000)...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":3000" ^| findstr "LISTENING"') do (
  echo Killing PID %%p
  taskkill /F /PID %%p >nul 2>&1
)
echo Done.
if not defined HP_NOPAUSE pause
