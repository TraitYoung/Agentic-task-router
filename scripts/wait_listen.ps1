param(
    [int]$Port = 3000,
    [int]$SleepSec = 2,
    [int]$Attempts = 20
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Test-LocalListenPort([int]$p) {
    $g = [System.Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties()
    foreach ($ep in $g.GetActiveTcpListeners()) {
        if ($ep.Port -eq $p) { return $true }
    }
    return $false
}

for ($i = 0; $i -lt $Attempts; $i++) {
    if (Test-LocalListenPort $Port) {
        Write-Host "Port $Port ready"
        exit 0
    }
    Write-Host ("Waiting... " + (($i + 1) * $SleepSec) + "s (max " + ($Attempts * $SleepSec) + "s)")
    Start-Sleep -Seconds $SleepSec
}

Write-Host "[WARN] Timeout waiting for port $Port, continuing anyway"
