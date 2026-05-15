Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

. "$PSScriptRoot\dev_ports.ps1"

function Show-Menu {
    Write-Host ""
    Write-Host "=== SpecForge Dev Menu ===" -ForegroundColor Cyan
    Write-Host "1) Restart Redis (6379)"
    Write-Host "2) Restart Backend (8000)"
    Write-Host "3) Restart Frontend (3000)"
    Write-Host "4) Restart All"
    Write-Host "5) Run import check (python -c 'import backend.main')"
    Write-Host "6) Run locust load test"
    Write-Host "0) Exit"
    Write-Host ""
}

function Run-Choice {
    param([string]$Choice)

    switch ($Choice) {
        "1" { Restart-RedisDev }
        "2" { Restart-BackendDev }
        "3" { Restart-FrontendDev }
        "4" {
            Restart-RedisDev
            Restart-BackendDev
            Restart-FrontendDev
        }
        "5" { python -c "import sys; sys.path.insert(0, 'backend'); import main; print('OK: backend.main imports cleanly')" }
        "6" { python scripts/locustfile.py --headless --users 5 --spawn-rate 1 --run-time 30s 2>$null }
        "0" { return $false }
        default { Write-Warning "Unknown choice: $Choice" }
    }
    return $true
}

while ($true) {
    Show-Menu
    $choice = Read-Host "Select action"
    $continue = Run-Choice -Choice $choice
    if (-not $continue) { break }
}

Write-Host "Bye."
