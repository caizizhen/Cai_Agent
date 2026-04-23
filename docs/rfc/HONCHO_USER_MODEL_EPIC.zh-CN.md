# RFC：Honcho 级 User-Model 演进（Epic 拆分与首包 API/存储）

> **状态**：设计草案（A1 / W0-A1）。当前主线已实现 **`memory user-model`** 的 **`behavior_extract`**（工具频次、错误率、goal 摘要），**非**完整 Honcho 图谱引擎；**`memory user-model export`** 已输出 **`user_model_bundle_v1`**（归档用，**非** E1 独立存储引擎）。本 RFC 定义向「可持久化、可查询、可在线更新」演进的边界与首包接口。

## 1. 目标与非目标

| 目标 | 非目标（本 Epic 不承诺） |
|------|---------------------------|
| 显式 **user-model** 版本化存储与读取 API（CLI + 可选 HTTP） | 替换现有 `memory` 条目模型 |
| 与 **`.cai/user-model.json`** 及会话落盘字段对齐的合并策略 | 云端多租户账号体系 |
| **图谱式**偏好关系（主题 → 行为边）的 **schema 与导入路径** | 实时分布式图数据库 |

## 2. Epic 拆分

| Epic | 交付物 | 依赖 |
|------|--------|------|
| **E1 存储与版本** | `user_model_store_v1`：单文件 JSONL 或 SQLite 单表；`schema_version` + `updated_at`；与 `memory health` 交叉引用（**进展**：**`user_model_bundle_v1` 导出**已落地，持久化 store 仍为后续） | 现有 `.cai/` 约定 |
| **E2 在线学习** | 任务结束后增量更新（钩子 `session_end` 或现有 metrics 管道）；冲突策略：LRU / 置信度加权 | E1 |
| **E3 查询 API** | `memory user-model query --json`：按标签/时间窗过滤；与 `recall` 只读组合说明 | E1 |
| **E4 图谱（可选）** | `entities[]` / `edges[]` 最小 schema；导入自 `behavior_extract` 摘要 | E1–E3 |

## 3. 首包 API（建议）

### 3.1 CLI（向后兼容）

- **`memory user-model export`**（stdout 为 JSON）→ **`user_model_bundle_v1`**（嵌 **`memory_user_model_v1`** **`overview`**；**`bundle_kind`**=`behavior_overview`）。  
- `memory user-model merge --file <path>`：仅允许 **dry-run** 首包，默认拒绝覆盖未声明版本。

### 3.2 存储布局（建议）

- 默认：`<workspace>/.cai/user-model/`  
  - `state.json`：`schema_version`、`last_task_id`、`aggregates`  
  - `events.jsonl`：可选追加学习事件（与 `schedule` audit 风格一致）

## 4. 验收与文档

- 与 [MEMORY_TTL_CONFIDENCE_POLICY.zh-CN.md](../MEMORY_TTL_CONFIDENCE_POLICY.zh-CN.md) 交叉引用「用户模型条目不适用 TTL」的说明。  
- 发版门：至少 **单元测试** 覆盖 merge dry-run + schema 校验；**不**强制阻塞 0.x 发版直至 E1 落地。

---

*维护：实现 E1 时在本 RFC 勾选 Epic 并链到 PR。*
