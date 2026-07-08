@echo off
setlocal
cd /d "%~dp0"

echo Stopping any existing frontend on port 3000...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":3000" ^| findstr "LISTENING"') do (
  taskkill /F /PID %%p >nul 2>&1
)

if exist ".next" (
  echo Clearing stale .next cache...
  rmdir /s /q ".next"
)

echo Starting HyperPulse frontend dev server in a new window...
start "HyperPulse Frontend" cmd /k "npm run dev"
endlocal
