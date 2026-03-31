function Get-PortOwnerProcesses {
    param(
        [Parameter(Mandatory = $true)]
        [int]$Port
    )

    $pids = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique

    if (-not $pids) {
        return @()
    }

    $processes = @()
    foreach ($pid in $pids) {
        $proc = Get-Process -Id $pid -ErrorAction SilentlyContinue
        if ($proc) {
            $processes += $proc
        }
    }
    return $processes
}

function Restart-PortService {
    param(
        [Parameter(Mandatory = $true)]
        [int]$Port,
        [Parameter(Mandatory = $true)]
        [string]$StartCommand
    )

    $processes = Get-PortOwnerProcesses -Port $Port
    foreach ($proc in $processes) {
        try {
            Stop-Process -Id $proc.Id -Force -ErrorAction Stop
            Write-Host "Stopped PID=$($proc.Id) Name=$($proc.ProcessName) (Port $Port)"
        } catch {
            Write-Warning "Failed to stop PID=$($proc.Id): $($_.Exception.Message)"
        }
    }

    Start-Sleep -Milliseconds 300
    Write-Host "Starting service: $StartCommand"
    Invoke-Expression $StartCommand
}

function Restart-PortServiceWithConfirm {
    param(
        [Parameter(Mandatory = $true)]
        [int]$Port,
        [Parameter(Mandatory = $true)]
        [string]$StartCommand
    )

    $processes = Get-PortOwnerProcesses -Port $Port
    if ($processes.Count -gt 0) {
        Write-Host "Port $Port is currently occupied by:" -ForegroundColor Yellow
        foreach ($proc in $processes) {
            Write-Host " - PID=$($proc.Id) Name=$($proc.ProcessName)"
        }
        $answer = Read-Host "Stop these processes and restart service? (y/N)"
        if ($answer -notin @("y", "Y", "yes", "YES")) {
            Write-Host "Canceled."
            return
        }
    } else {
        Write-Host "Port $Port is free."
        $answer = Read-Host "Start service now? (Y/n)"
        if ($answer -in @("n", "N", "no", "NO")) {
            Write-Host "Canceled."
            return
        }
    }

    Restart-PortService -Port $Port -StartCommand $StartCommand
}

# 便捷包装函数（本项目常用）
function Restart-RedisDev {
    Restart-PortServiceWithConfirm -Port 6379 -StartCommand 'redis-server --port 6379'
}

function Restart-BackendDev {
    Restart-PortServiceWithConfirm -Port 8000 -StartCommand 'python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload'
}

function Restart-FrontendDev {
    Restart-PortServiceWithConfirm -Port 3000 -StartCommand 'cd frontend; npm run dev'
}

