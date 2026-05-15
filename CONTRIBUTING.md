# 贡献与工程约定

本文约定本仓库的目录语义、本地运行方式与测试入口，便于多人协作与 CI 对齐。

## 仓库分层（Monorepo）

| 区域 | 路径 | 说明 |
|------|------|------|
| Python API / Agent | `backend/` | FastAPI 入口、`agents/`、`memory/`、`schemas/`、`tools/` 等；运行时应将此前缀加入 Python 路径（见下文）。 |
| 前端 | `frontend/` | Next.js，`app/api/*` 反向代理到 FastAPI。 |
| 自动化与运维脚本 | `scripts/` | 迁移、压测、PDF、本地编排 PowerShell；**不是**运行时装载的包路径。 |
| 测试 | `tests/` | 脚本式回归与 `pytest`；依赖 `backend/` 在 `sys.path` 中。 |
| 产物与数据 | `data/`、`output/`、`input/`、`logs/` | 默认 `.gitignore` 忽略敏感或生成内容；路径相对**仓库根**解析（见 `backend/repo_paths.py`）。 |
| 文档与设计 | `docs/` | BIOS、ADR、`项目结构与技术要点.md`；历史笔记见 `docs/archive/`。 |

`.env` 放在**仓库根**，由 `backend/repo_paths.REPO_ROOT` 加载，请勿只在 `backend/` 下放一份副本以免遗漏。

## 本地运行后端

在仓库根目录安装依赖后启动（推荐与 Docker 一致使用 `--app-dir`）：

```powershell
cd G:\path\to\aixodrasil_core
pip install -r requirements.txt
python -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
```

或先 `Set-Location backend` 再执行 `python -m uvicorn main:app ...`，此时当前目录即为包根，亦兼容。

## 本地运行前端

```powershell
cd frontend
npm install
npm run dev
```

## 测试

- **pytest**（推荐）：根目录 `pyproject.toml` 已配置 `pythonpath = ["backend"]`。

  ```powershell
  pip install pytest
  pytest
  ```

- **单文件脚本**（不经过 pytest）：各脚本开头已将 `backend/` 注入 `sys.path`，请在**仓库根**执行：

  ```powershell
  python tests/test_rag.py
  python tests/test.py
  ```

## 代码与路径约定

- 新增可导入的 Python 模块放在 `backend/` 下适当子包内；避免在仓库根散落 `.py` 业务文件。
- 凡依赖「仓库根」的路径（数据库、`output/`、`.env`）应使用 `repo_paths.REPO_ROOT`，不要假定进程 cwd。
- Bit 侧 `write_local_file` 仅允许写入 `REPO_ROOT` 以下路径。

## 提交前自检建议

- `python -m compileall backend -q`
- 按需运行 `python scripts/migration.py`、`pytest` 或与改动相关的 `tests/*.py`

## Docker

`docker-compose.yml` 中 API 服务使用 `uvicorn main:app --app-dir backend`，挂载仓库根以便读取 `requirements.txt` 与 `.env`。
