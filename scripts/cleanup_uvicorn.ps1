$ErrorActionPreference = 'Stop'

$port = 8000
$connections = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue

if (-not $connections) {
  Write-Host "No listeners on port $port"
  exit 0
}

$processIds = $connections.OwningProcess | Sort-Object -Unique

foreach ($processId in $processIds) {
  $proc = $null
  try {
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$processId"
  } catch {
    $proc = $null
  }

  $cmd = $proc?.CommandLine
  $shouldStop = $false

  if (-not $proc) {
    Write-Host "Process info not available for PID $processId; stopping to free port $port"
    $shouldStop = $true
  } elseif (-not $cmd) {
    Write-Host "Command line not available for PID $processId; stopping to free port $port"
    $shouldStop = $true
  } elseif ($cmd -match 'uvicorn') {
    Write-Host "Stopping uvicorn (PID $processId): $cmd"
    $shouldStop = $true
  } else {
    Write-Host "Skipping PID $processId (not uvicorn): $cmd"
  }

  if ($shouldStop) {
    try {
      Stop-Process -Id $processId -Force -ErrorAction Stop
    } catch {
      Write-Host ("Failed to stop PID {0}: {1}" -f $processId, $_.Exception.Message)
    }
  }
}
