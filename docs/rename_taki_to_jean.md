# Taki → Jean 重命名说明

本文档说明代码与文档助理从 **Taki** 更名为 **Jean** 时，仓库内**已修改**与**刻意未修改**的范围，便于后续维护与 onboarding。

## 已修改（与运行时代码一致）

| 类别 | 说明 |
|------|------|
| **协议** | `schemas/protocols.py` 中 `task_type` 的取值 `taki` 已改为 `jean`。 |
| **路由与节点** | `agents/router.py`：`node_jean`、`jean_agent`、`jean_route`；条件路由与 `active_task_type` 使用 `jean`。 |
| **System Prompt** | `prompts/system_prompts.py`：`JEAN_PROMPT`（原 `TAKI_PROMPT`），人设名为「Jean」。 |
| **技术节点工具常量** | `tools/agent_tools.py`：`BIT_TOOLS`（原 `TAKI_TOOLS`），仅由 Bit 节点使用，命名与职责对齐。 |
| **API 回复前缀** | `main.py`：`task_type` / `active_task_type` 为 `jean` 时，前缀为 `jean`。 |
| **前端展示** | `frontend/app/page.tsx`：`jean` 分支，展示「文档（Jean）」。 |
| **项目文档** | 根目录 `README.md`、`docs/Digital_Assistant_Team_structure.md`、`docs/adr/ADR-001-pain_level_calibration.md`。 |
| **测试脚本注释与输出文案** | `test_suite/test.py`、`test_system_prompts.py`、`test_memory.py` 中与节点名、职责相关的描述。 |

**迁移注意**：任何依赖旧值 `task_type: "taki"` 或 `import TAKI_TOOLS` / `TAKI_PROMPT` 的外部脚本或分支，需改为 `jean` / `BIT_TOOLS` / `JEAN_PROMPT`。

## 未修改（历史、设定或归档）

| 类别 | 说明 |
|------|------|
| **BIOS 设定文档** | `docs/Axiodrasil_BIOS_*.md` 等仍为世界观内的角色名（如椎名立希 / Taki），与代码中的路由标识 **Jean** 是两套命名体系；未做批量替换。 |
| **input / output 归档** | 历史对话 JSON、SFT 清单等若含「Taki」或文件名如 `taki_tools_debug.log`，保留原样，避免破坏既有路径与训练数据引用。 |
| **磁盘上的日志文件名** | 若本地仍存在 `taki_tools_debug.log` 等文件，仅为历史命名；代码与文档已以 `BIT_TOOLS` 等为准。 |

## 修订记录

- 随仓库演进更新；若未来统一 BIOS 与代码侧名称，应在本文件追加一节说明决策与影响面。
