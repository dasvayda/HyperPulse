# Kill any leftover HyperPulse backend/frontend processes before a fresh start.
$ErrorActionPreference = "Continue"
$ports = @(8100, 3100)
$killed = 0

Write-Host "Scanning HyperPulse ports $($ports -join ', ') ..."

foreach ($port in $ports) {
  $pids = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique
  foreach ($procId in $pids) {
    if (-not $procId) { continue }
    try {
      Write-Host "  Killing port $port PID $procId"
      Stop-Process -Id $procId -Force -ErrorAction Stop
      $killed++
    } catch {
      Write-Warning ("  Failed to kill PID {0}: {1}" -f $procId, $_.Exception.Message)
    }
  }
}

Write-Host "Scanning HyperPulse uvicorn / python processes ..."
Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
  Where-Object {
    $_.CommandLine -and (
      $_.CommandLine -match 'uvicorn' -or
      $_.CommandLine -match 'app\.main' -or
      $_.CommandLine -match 'start_backend\.ps1'
    )
  } |
  ForEach-Object {
    try {
      Write-Host "  Killing python PID $($_.ProcessId)"
      Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop
      $script:killed++
    } catch {
      Write-Warning ("  Failed to kill python PID {0}: {1}" -f $_.ProcessId, $_.Exception.Message)
    }
  }

Write-Host "Scanning HyperPulse frontend node processes ..."
Get-CimInstance Win32_Process -Filter "Name='node.exe'" -ErrorAction SilentlyContinue |
  Where-Object {
    $_.CommandLine -and (
      $_.CommandLine -match '-p\s*3100' -or
      $_.CommandLine -match 'next.*3100' -or
      ($_.CommandLine -match 'my-own-project\\frontend' -and $_.CommandLine -match 'next')
    )
  } |
  ForEach-Object {
    try {
      Write-Host "  Killing node PID $($_.ProcessId)"
      Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop
      $script:killed++
    } catch {
      Write-Warning ("  Failed to kill node PID {0}: {1}" -f $_.ProcessId, $_.Exception.Message)
    }
  }

Write-Host "Scanning HyperPulse console windows ..."
Get-Process -ErrorAction SilentlyContinue |
  Where-Object {
    $_.MainWindowTitle -and (
      $_.MainWindowTitle -match '^HyperPulse Backend' -or
      $_.MainWindowTitle -match '^HyperPulse Frontend'
    )
  } |
  ForEach-Object {
    try {
      Write-Host "  Killing window '$($_.MainWindowTitle)' PID $($_.Id)"
      Stop-Process -Id $_.Id -Force -ErrorAction Stop
      $script:killed++
    } catch {
      Write-Warning ("  Failed to kill window PID {0}: {1}" -f $_.Id, $_.Exception.Message)
    }
  }

# Named cmd/powershell windows may not expose MainWindowTitle reliably; taskkill FI helps.
foreach ($title in @("HyperPulse Backend*", "HyperPulse Frontend*")) {
  & taskkill /F /FI "WINDOWTITLE eq $title" >$null 2>&1
}

Start-Sleep -Seconds 1

$still = @()
foreach ($port in $ports) {
  if (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) {
    $still += $port
  }
}

if ($still.Count -gt 0) {
  Write-Warning ("Ports still in use after cleanup: {0}" -f ($still -join ", "))
  exit 1
}

if ($killed -eq 0) {
  Write-Host "No existing HyperPulse process found."
} else {
  Write-Host "Cleanup complete. Killed $killed process(es)."
}
exit 0
