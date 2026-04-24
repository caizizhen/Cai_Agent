# 记忆 TTL / 置信度策略说明（与 CLI 对齐）

本文档与 **`memory_entry_v1`** 行结构、`memory prune` / `memory state` / `memory health` 行为一致，供运维与发版评审引用。权威 schema 见仓库内 **`cai-agent/schemas/memory_entry_v1.schema.json`**（若存在）及 [`docs/schema/README.zh-CN.md`](schema/README.zh-CN.md) 相关小节。

## 1. 行内字段语义

| 字段 | 含义 | 建议 |
|------|------|------|
| **`confidence`** | `0.0`–`1.0`，结构化抽取或规则写入时的主观可靠度 | 会话摘要类 **0.45–0.55**；经人工复核的事实 **≥0.75**；不确定占位 **≤0.35** 便于后续 prune |
| **`expires_at`** | ISO8601 字符串或空；早于「当前 UTC」则视为 TTL 到期 | 短期促销/一次性上下文可设 **7–30 天**；长期知识可留空，依赖 **stale** 策略 |
| **`created_at`** | 写入时间（UTC） | 由 `append_memory_entry` 自动填充，勿手改 |

## 2. `memory prune` 清理顺序（实现顺序）

与 **`prune_expired_memory_entries`** 一致：

1. **`expires_at` 已过期** → 计入 **`expired_by_ttl`**
2. **`--min-confidence`** 大于默认 `0.0` 时，**低于阈值**的行 → **`low_confidence`**
3. **`--drop-non-active`** 为真时，按状态机剔除 **非 active**（见下）→ **`stale_by_age` / `stale_by_confidence` / …`**
4. **`--max-entries` > 0** 时，按 **`created_at` 新到旧** 仅保留前 N 条 → **`over_limit`**

CLI 参数对应（节选）：

- **`--min-confidence`**：默认 **0.0** 表示不按置信度删；设 **0.35** 可清掉大量低质自动条目。
- **`--max-entries`**：**0** 表示不限制条数。
- **`--drop-non-active`**：与 **`--state-stale-after-days`**（默认 **30**）、**`--state-min-active-confidence`**（默认 **0.4**）配合，与 **`memory state`** 的 stale 判定对齐。

## 3. `memory state` 与 prune 的「stale」对齐

- **`memory state --stale-days`** / **`--stale-confidence`**：用于**只读**评估分布。
- **`memory prune --drop-non-active`** 使用的 **`stale_after_days` / `min_active_confidence`** 应与团队对「多久算旧、多低算不可信」的约定一致；**推荐与 `memory state` 使用同一组数字**，先 `state --json` 看分布再开 prune。

## 4. `memory health` 与策略的关系

- **`memory health`** 输出 **freshness / coverage / conflict_rate / grade**，不直接改文件。
- 若 **grade** 持续偏低：优先 **`memory validate-entries`** → **`memory extract --structured`** 补全 → 再考虑 **`prune --min-confidence`** 或 **`--max-entries`** 上限，避免一次删过量。

## 5. 推荐默认组合（可按项目收紧）

| 场景 | 建议 |
|------|------|
| 个人开发机 | `prune` 仅用 **`--max-entries 2000`** 防无限增长；**`min-confidence` 暂勿动** 除非确认抽取噪声大 |
| 小团队共享盘 | **`--max-entries 5000`** + 每月一次 **`--min-confidence 0.35`**（先 dry-run：用 **`memory list`/`state`** 目测） |
| CI 工作区 | 不写长期 `entries.jsonl`；若跑集成测试，事后 **`prune --max-entries 0`** 不限制或删测试数据目录 |

## 6. 与写入门禁的关系

若 **`memory/entries.jsonl`** 存在无效行，**`append_memory_entry` / `import` / `extract` 写入路径**会拒绝追加（见 **`CAI_MEMORY_ALLOW_DIRTY_ENTRIES_JSONL`** 救急变量）。**治理顺序**：`validate-entries` → 修复 → 再 `extract` / `import`。

---

*维护：变更 `memory prune` 默认行为或 schema 时，请同步更新本页与 [`PRODUCT_PLAN.zh-CN.md`](PRODUCT_PLAN.zh-CN.md) / [`ROADMAP_EXECUTION.zh-CN.md`](ROADMAP_EXECUTION.zh-CN.md) 中 `HM-05` 相关表述。*
