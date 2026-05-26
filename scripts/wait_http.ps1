param(
    [Parameter(Mandatory = $true)]
    [string]$Url,
    [int]$SleepSec = 1,
    [int]$Attempts = 60,
    [int]$TimeoutSec = 2
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

for ($i = 0; $i -lt $Attempts; $i++) {
    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec $TimeoutSec
        if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 300) {
            Write-Host "HTTP ready: $Url"
            exit 0
        }
        Write-Host "Waiting for HTTP $Url (status=$($response.StatusCode))"
    } catch {
        Write-Host ("Waiting for HTTP " + $Url + "... " + (($i + 1) * $SleepSec) + "s (max " + ($Attempts * $SleepSec) + "s)")
    }
    Start-Sleep -Seconds $SleepSec
}

Write-Host "[ERROR] Timeout waiting for HTTP ready: $Url"
exit 1
