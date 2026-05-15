# 贡献与工程约定

## 仓库分层

| 区域 | 路径 | 说明 |
|------|------|------|
| Python API | `backend/` | FastAPI 入口、`agents/dev_pipeline/`、`schemas/`、`config/`、`memory/` |
| 前端 | `frontend/` | Next.js 16，`app/api/*` 反向代理到 FastAPI |
| 脚本 | `scripts/` | 开发环境管理（dev_stack.ps1）、压测（locustfile.py） |
| 测试 | `tests/` | pytest，依赖 `backend/` 在 `sys.path` 中 |
| 产物与数据 | `data/`、`output/`、`logs/` | 默认 `.gitignore` 忽略；路径通过 `backend/repo_paths.py` 解析 |
| 文档 | `docs/` | [架构与履历映射](docs/ARCHITECTURE.md)、[项目结构与技术要点](docs/项目结构与技术要点.md)、历史归档 |

`.env` 放在**仓库根**，由 `backend/repo_paths.REPO_ROOT` 加载。

## 本地运行

**一键启动：**
```powershell
# 双击根目录 start_dev.bat，自动启动 Redis + Backend + Frontend 并打开浏览器
```

**手动启动：**
```powershell
# 终端 1 — Redis（可选）
redis-server --port 6379

# 终端 2 — 后端
python -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload

# 终端 3 — 前端
cd frontend
npm install
npm run dev
```

浏览器打开 `http://localhost:3000`。

## 测试

```powershell
pip install pytest
pytest
```

`pyproject.toml` 已配置 `pythonpath = ["backend"]`。

## 提交前自检

- `python -m compileall backend -q`
- `pytest`
- 前端：`cd frontend && npx tsc --noEmit && npm run build`

## Docker

`docker-compose.yml` 编排 Redis + FastAPI，挂载仓库根以读取 `.env` 与 `requirements.txt`。
