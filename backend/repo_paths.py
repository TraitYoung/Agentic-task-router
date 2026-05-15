"""单一来源：仓库根目录与后端包根目录（不受 uvicorn 工作目录影响）。"""
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent
REPO_ROOT = BACKEND_ROOT.parent
