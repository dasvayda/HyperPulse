@echo off
setlocal
cd /d "%~dp0"

echo Stopping any existing frontend on port 3100...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":3100" ^| findstr "LISTENING"') do (
  taskkill /F /PID %%p >nul 2>&1
)

if exist ".next" (
  echo Clearing stale .next cache...
  rmdir /s /q ".next"
)

echo Starting HyperPulse frontend dev server on port 3100...
start "HyperPulse Frontend" cmd /k "npm run dev -- -p 3100"
endlocal
