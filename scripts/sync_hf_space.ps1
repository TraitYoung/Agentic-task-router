# 将 backend 同步到 hf-space 并提示推送 Hugging Face Space
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "backend"
$HfBackend = Join-Path $Root "hf-space\backend"

if (-not (Test-Path (Join-Path $Root "hf-space\.git"))) {
    Write-Error "hf-space 目录不是 git 仓库。请先在 hf-space 克隆 iShowRelx5/specForge-api"
}

Write-Host "Syncing backend -> hf-space/backend ..."
robocopy $Backend $HfBackend /MIR /XD __pycache__ .pytest_cache /NFL /NDL /NJH /NJS | Out-Null
if ($LASTEXITCODE -ge 8) { exit $LASTEXITCODE }

Copy-Item (Join-Path $Root "requirements.txt") (Join-Path $Root "hf-space\requirements.txt") -Force

Push-Location (Join-Path $Root "hf-space")
git status
Write-Host ""
Write-Host "Next steps:"
Write-Host "  cd hf-space"
Write-Host "  git add -A"
Write-Host "  git commit -m 'deploy: backend update'"
Write-Host "  git push origin main"
Write-Host "Then Restart Hugging Face Space."
Pop-Location
