Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

. "$PSScriptRoot\dev_ports.ps1"

function Show-Menu {
    Write-Host ""
    Write-Host "=== Axiodrasil Dev Menu ===" -ForegroundColor Cyan
    Write-Host "1) Restart Redis (6379)"
    Write-Host "2) Restart Backend (8000)"
    Write-Host "3) Restart Frontend (3000)"
    Write-Host "4) Restart All (open in this terminal one by one)"
    Write-Host "5) Run migration (scripts/migration.py)"
    Write-Host "6) Run RAG test (test_suite/test_rag.py)"
    Write-Host "7) Run router test (test_suite/test.py)"
    Write-Host "8) List input files for cleaning mode"
    Write-Host "9) Dry-run logs->SFT pipeline"
    Write-Host "0) Exit"
    Write-Host ""
}

function Run-Choice {
    param([string]$Choice)

    switch ($Choice) {
        "1" {
            Restart-RedisDev
        }
        "2" {
            Restart-BackendDev
        }
        "3" {
            Restart-FrontendDev
        }
        "4" {
            Restart-RedisDev
            Restart-BackendDev
            Restart-FrontendDev
        }
        "5" {
            python scripts/migration.py
        }
        "6" {
            python test_suite/test_rag.py
        }
        "7" {
            python test_suite/test.py
        }
        "8" {
            if (-not (Test-Path "input")) {
                New-Item -ItemType Directory -Path "input" | Out-Null
            }
            Get-ChildItem -Path "input" -File | Select-Object Name, Length, LastWriteTime | Format-Table -AutoSize
        }
        "9" {
            python tools/logs_to_sft.py --input-dir logs --output-dir output --dry-run
        }
        "0" {
            return $false
        }
        default {
            Write-Warning "Unknown choice: $Choice"
        }
    }
    return $true
}

while ($true) {
    Show-Menu
    $choice = Read-Host "Select action"
    $continue = Run-Choice -Choice $choice
    if (-not $continue) {
        break
    }
}

Write-Host "Bye."
