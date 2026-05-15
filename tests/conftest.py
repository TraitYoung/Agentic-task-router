import sys
from pathlib import Path

# 将 backend/ 加入 sys.path，使测试能 import backend.* 模块
backend_root = Path(__file__).resolve().parent.parent / "backend"
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))
