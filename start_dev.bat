@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo.
echo =============================================
echo   SpecForge Dev Stack Launcher
echo =============================================
echo.
echo   Frontend: http://localhost:3000
echo   Backend:  http://localhost:8000/docs
echo.

REM --- Check frontend deps ---
if not exist "frontend\node_modules\" (
    echo [1/3] Installing frontend dependencies...
    cd frontend
    call npm install
    if errorlevel 1 (
        echo [ERROR] npm install failed
        cd ..
        pause
        exit /b 1
    )
    cd ..
) else (
    echo [ok] frontend dependencies ready
)

REM --- Check Python deps ---
python -c "import fastapi, uvicorn" 2>nul
if errorlevel 1 (
    echo [WARN] fastapi/uvicorn not found, run: pip install -r requirements.txt
)

REM --- Start all services ---
echo.
echo [2/3] Starting services...
powershell -ExecutionPolicy Bypass -File "%~dp0scripts\dev_stack.ps1" -Action start -All
if errorlevel 1 (
    echo [ERROR] Failed to start services
    pause
    exit /b 1
)

REM --- Wait for frontend port and open browser ---
echo [3/3] Waiting for frontend (port 3000)...
powershell -ExecutionPolicy Bypass -Command "for ($i=0; $i -lt 20; $i++) { $r = Get-NetTCPConnection -LocalPort 3000 -State Listen -ErrorAction SilentlyContinue; if ($r) { Write-Host 'Port 3000 ready'; exit 0 }; Write-Host ('Waiting... ' + ($i+1)*2 + 's'); Start-Sleep 2 }; Write-Host '[WARN] Timeout, opening anyway'"
start http://127.0.0.1:3000
echo Browser opened: http://localhost:3000

echo.
echo =============================================
echo   Frontend : http://localhost:3000
echo   Backend  : http://localhost:8000/docs
echo   Stop all : powershell .\scripts\dev_stack.ps1 -Action stop -All
echo =============================================
echo.
pause
