Write-Host "Stopping HyperPulse backend on port 8000 ..."

$conns = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue |
  Select-Object -ExpandProperty OwningProcess -Unique

if (-not $conns) {
  Write-Host "No process is listening on port 8000."
  exit 0
}

foreach ($procId in $conns) {
  try {
    Write-Host "Killing PID $procId"
    Stop-Process -Id $procId -Force -ErrorAction Stop
  } catch {
    Write-Warning ("Failed to kill PID {0}: {1}" -f $procId, $_.Exception.Message)
  }
}

