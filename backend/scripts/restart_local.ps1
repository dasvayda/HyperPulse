[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [ValidateSet('Full', 'Monitor')]
    [string]$Mode,
    [switch]$Plan,
    [switch]$SendTelegram
)

$ErrorActionPreference = 'Stop'
if ($SendTelegram -and $Mode -ne 'Full') {
    throw '-SendTelegram is supported only in Full mode.'
}

$backend = (Resolve-Path "$PSScriptRoot\..").Path
$frontend = (Resolve-Path "$backend\..\frontend").Path
$python = Join-Path $backend '.venv\Scripts\python.exe'
$next = Join-Path $frontend 'node_modules\next\dist\bin\next'
$roster = Join-Path $backend 'hyperpulse.db'
$logs = Join-Path $backend 'logs'
$api = 'http://127.0.0.1:8100'
$site = 'http://127.0.0.1:3100'

function Get-ProjectProcesses($processes) {
    $backendLauncher = [regex]::Escape("$backend\scripts\start_backend.ps1")
    $venv = [regex]::Escape("$backend\.venv\Scripts\")
    $frontendModules = [regex]::Escape("$frontend\node_modules\")
    $owned = @{}
    foreach ($process in $processes) {
        $command = $process.CommandLine
        $legacyBackend = $process.Name -match '^(powershell|pwsh)\.exe$' -and
            $command -match ('(?:^|\s)-file\s+"?' + $backendLauncher + '(?:"|\s|$)')
        $backendServer = $process.ExecutablePath -match "^$venv(?:python|uvicorn)\.exe$" -and
            $command -match '(?:\bapp\.main:app\b|\s-m\s+scripts\.observe_whale_alerts\b)'
        $frontendServer = $process.Name -eq 'node.exe' -and
            $command -match ($frontendModules + '(?:\.bin\\+\.\.\\)?next\\dist\\(?:bin\\next|server\\lib\\start-server\.js)(?:"|\s|$)')
        if ($legacyBackend -or $backendServer -or $frontendServer) {
            $owned[$process.ProcessId] = $process
        }
    }
    do {
        $previousCount = $owned.Count
        foreach ($process in $processes) {
            $parent = $owned[$process.ParentProcessId]
            if ($parent -and $process.Name -ne 'conhost.exe' -and $process.CreationDate -ge $parent.CreationDate) {
                $owned[$process.ProcessId] = $process
            }
        }
    } while ($owned.Count -gt $previousCount)
    $owned
}

function Get-ServerListeners {
    Get-NetTCPConnection -State Listen | Where-Object { $_.LocalPort -in @(8100, 3100) }
}

function Start-Server($executable, $arguments, $directory, $logPrefix) {
    $options = @{
        FilePath = $executable
        ArgumentList = $arguments
        WorkingDirectory = $directory
        WindowStyle = 'Hidden'
        RedirectStandardOutput = Join-Path $logs "$logPrefix.out.log"
        RedirectStandardError = Join-Path $logs "$logPrefix.err.log"
        PassThru = $true
    }
    $process = Start-Process @options
    Write-Host "Started PID $($process.Id). Logs: $($options.RedirectStandardOutput), $($options.RedirectStandardError)"
    $process
}

function Wait-Server($process, [scriptblock]$Probe, $url) {
    $deadline = [DateTime]::UtcNow.AddSeconds(90)
    do {
        if ($process.HasExited) {
            throw "PID $($process.Id) exited with code $($process.ExitCode). See the logs above."
        }
        try {
            if (& $Probe $url) { return }
        } catch {
            Write-Verbose $_.Exception.Message
        }
        Start-Sleep -Seconds 1
    } while ([DateTime]::UtcNow -lt $deadline)
    throw "Timed out waiting for $url. See the logs above."
}

# Serialize restarts of this checkout, including when there are no listeners.
$mutexName = 'Local\HyperPulseRestart-' + ($backend.ToUpperInvariant() -replace '[^A-Z0-9]', '_')
$mutex = [System.Threading.Mutex]::new($false, $mutexName)
$locked = $false
try {
    try {
        $locked = $mutex.WaitOne(0)
    } catch [System.Threading.AbandonedMutexException] {
        $locked = $true
    }
    if (-not $locked) { throw 'Another HyperPulse restart is in progress.' }

    $owned = Get-ProjectProcesses (Get-CimInstance Win32_Process)
    $foreign = @(Get-ServerListeners | Where-Object { -not $owned.ContainsKey($_.OwningProcess) })
    if ($foreign.Count) {
        $details = ($foreign | ForEach-Object { "$($_.LocalPort) (PID $($_.OwningProcess))" }) -join ', '
        throw "Could not confirm HyperPulse ownership of listeners on $details. No processes stopped."
    }

    $stopOrder = @($owned.Values | Sort-Object CreationDate)
    $ids = ($stopOrder | ForEach-Object ProcessId) -join ', '
    if (-not $ids) { $ids = 'none' }
    Write-Host "Mode: $Mode. HyperPulse PIDs to stop: $ids."
    if ($Plan) { return }

    $required = @($python)
    if ($Mode -eq 'Monitor') {
        $required += $roster
    } else {
        $node = (Get-Command node.exe -CommandType Application).Source
        $required += $next
    }
    foreach ($file in $required) {
        if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { throw "Required file missing: $file" }
    }
    New-Item -ItemType Directory -Path $logs -Force | Out-Null

    foreach ($target in $stopOrder) {
        $process = Get-Process -Id $target.ProcessId -ErrorAction SilentlyContinue
        if (-not $process) { continue }
        # CIM timestamps can lose the sub-microsecond part of the process start time.
        if ([math]::Abs(($process.StartTime - $target.CreationDate).Ticks) -ge 10) {
            throw "PID $($target.ProcessId) changed during restart. Run the check again."
        }
        $process | Stop-Process -Force
        Wait-Process -InputObject $process -Timeout 5
    }
    if (Get-ServerListeners) { throw 'A server port is still occupied after cleanup.' }

    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
    $oldAlerts = $env:ALERTS_ENABLED
    $oldApiUrl = $env:API_URL
    try {
        $env:ALERTS_ENABLED = $SendTelegram.IsPresent.ToString().ToLowerInvariant()
        if ($Mode -eq 'Monitor') {
            $observation = Join-Path $logs "whale-observation-$stamp.jsonl"
            $arguments = '-m scripts.observe_whale_alerts --roster "{0}" --output "{1}" --hours 24 --interval 120 --wallets 30 --port 8100' -f $roster, $observation
            $server = Start-Server $python $arguments $backend "observer-$stamp"
            Write-Host "Observation log: $observation"
            Wait-Server $server {
                param($url)
                $health = Invoke-RestMethod -Uri $url -TimeoutSec 3
                $health.mode -eq 'non_sending_observation' -and $health.telegram -eq $false
            } "$api/health"
        } else {
            $server = Start-Server $python '-m uvicorn app.main:app --host 127.0.0.1 --port 8100' $backend "backend-$stamp"
            Wait-Server $server {
                param($url)
                (Invoke-RestMethod -Uri $url -TimeoutSec 3).status -eq 'ok'
            } "$api/health"
            $env:API_URL = $api
            $arguments = '"{0}" dev --hostname 127.0.0.1 --port 3100' -f $next
            $web = Start-Server $node $arguments $frontend "frontend-$stamp"
            Wait-Server $web {
                param($url)
                (Invoke-WebRequest -UseBasicParsing -Uri $url -TimeoutSec 10).StatusCode -eq 200
            } $site
            Write-Host "Frontend ready: $site"
        }
        Write-Host "Backend ready: $api/health"
    } finally {
        $env:ALERTS_ENABLED = $oldAlerts
        $env:API_URL = $oldApiUrl
    }
} finally {
    if ($locked) { $mutex.ReleaseMutex() }
    $mutex.Dispose()
}
