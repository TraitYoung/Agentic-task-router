@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo.
echo ╔══════════════════════════════════════════════╗
echo ║       SpecForge Dev Stack Launcher          ║
echo ╚══════════════════════════════════════════════╝
echo.
echo 服务: Redis (6379) + Backend (8000) + Frontend (3000)
echo 前端: http://localhost:3000
echo.

REM --- 前端依赖 ---
if not exist "frontend\node_modules\" (
    echo [1/3] 安装前端依赖...
    cd frontend
    call npm install
    cd ..
    echo.
) else (
    echo [ok] 前端依赖已就绪
)

REM --- 后端依赖 ---
if not exist "backend\venv\Scripts\python.exe" (
    if exist "backend\.venv\Scripts\python.exe" (
        echo [ok] Python 虚拟环境已就绪
    ) else (
        echo [WARN] 未检测到 Python 虚拟环境，将使用全局 python
    )
)

REM --- 检查关键 Python 包 ---
python -c "import fastapi, uvicorn" 2>nul
if errorlevel 1 (
    echo [WARN] 缺少 fastapi/uvicorn，请先安装: pip install -r requirements.txt
    echo.
)

REM --- 启动所有服务（后台运行，不自动打开浏览器）---
echo.
echo [2/3] 启动服务...
powershell -ExecutionPolicy Bypass -File ".\scripts\dev_stack.ps1" -Action start -All

REM --- 等待端口就绪 ---
echo [3/3] 等待端口就绪...
powershell -ExecutionPolicy Bypass -Command ^
    "$ports = @(3000, 8000, 6379);" ^
    "$maxWait = 30; $elapsed = 0;" ^
    "while ($elapsed -lt $maxWait) {" ^
    "  $allReady = $true;" ^
    "  foreach ($p in $ports) {" ^
    "    $listener = Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue;" ^
    "    if (-not $listener) { $allReady = $false; break }" ^
    "  }" ^
    "  if ($allReady) { Write-Host '所有端口已就绪'; break }" ^
    "  Write-Host ('等待中... (' + $elapsed + 's)'); Start-Sleep 2; $elapsed += 2;" ^
    "}" ^
    "if ($elapsed -ge $maxWait) {" ^
    "  Write-Host '[WARN] 部分端口超时未就绪，仍将打开浏览器';" ^
    "}" ^
    "Start-Process 'http://127.0.0.1:3000';" ^
    "Write-Host '浏览器已打开: http://127.0.0.1:3000'"

echo.
echo =============================================
echo   前端: http://localhost:3000
echo   后端: http://localhost:8000/docs
echo   关闭此窗口不会停止服务
echo   停止服务: .\scripts\dev_stack.ps1 -Action stop -All
echo =============================================
echo.
echo Press any key to close this window...
pause >nul
