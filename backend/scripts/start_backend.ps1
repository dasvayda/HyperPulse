Set-Location "$PSScriptRoot\.."

$port = 8100
Write-Host "Stopping any existing HyperPulse backend on port $port ..."
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Where-Object { $_.CommandLine -match 'uvicorn|app\.main' } |
  ForEach-Object {
    try {
      Write-Host "Killing python PID $($_.ProcessId)"
      Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop
    } catch {
      Write-Warning ("Failed to kill PID {0}: {1}" -f $_.ProcessId, $_.Exception.Message)
    }
  }

$conns = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue |
  Select-Object -ExpandProperty OwningProcess -Unique

foreach ($procId in $conns) {
  try {
    Write-Host "Killing PID $procId"
    Stop-Process -Id $procId -Force -ErrorAction Stop
  } catch {
    Write-Warning ("Failed to kill PID {0}: {1}" -f $procId, $_.Exception.Message)
  }
}

Start-Sleep -Seconds 1

try {
  $health = Invoke-RestMethod -Uri "http://127.0.0.1:$port/health" -TimeoutSec 2
  if ($health.status -eq "ok") {
    Write-Host "Backend already running on http://127.0.0.1:$port"
    exit 0
  }
} catch {
  # Port free or server not ready; continue to start.
}

Write-Host "Starting HyperPulse backend on http://127.0.0.1:$port ..."
if (-not (Test-Path ".venv")) {
  Write-Error "Python venv (.venv) not found. Run 'python -m venv .venv' in backend first."
  exit 1
}

$env:PYTHONPATH = "."
$env:API_PORT = "$port"
# No --reload: avoids zombie reloader processes and port conflicts on Windows.
.venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port $port
