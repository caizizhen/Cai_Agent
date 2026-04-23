# 记忆治理策略（TTL / 置信度 / prune）

> 与 `memory health --json` 字段对齐：`health_score`、`grade`、`freshness`、`coverage`、`conflict_rate` 等见 [schema 说明](schema/README.zh-CN.md)。

## 置信度分级（建议）

| 区间 | 含义 | 建议动作 |
|------|------|----------|
| **≥ 0.9** | 高可信 | 长期保留；可作为 `memory recall` 优先展示 |
| **0.6 ~ 0.9** | 参考级 | 正常保留；定期与 `memory health` 联动复核 |
| **< 0.6** | 低可信 | 标注 low；`memory prune --min-confidence 0.6` 可清理 |

## TTL（过期时间）

| 类型 | `expires_at` 建议 | 适用 |
|------|-------------------|------|
| 短期事实 | 创建后 **7 天** | 临时上下文、实验结论 |
| 中期经验 | **30 天** | 迭代中的项目约定 |
| 长期原则 | **留空**（不过期） | 架构约束、团队规范 |

## 何时触发 `memory prune`

1. **调度**：`schedule add` 每日 `memory prune`（与 `memory health --fail-on-grade` 组合）。
2. **健康度**：`memory health` 等级为 **C/D** 时，先 `nudge-report` 再 `prune`。
3. **体量**：`entries.jsonl` 行数超过团队上限时，`--max-entries` 配合 `--min-confidence`。

## 与 `memory extract` / `import-entries` 的关系

- 写入前均执行 **memory_entry_v1** 校验；非法行不会落盘（见 `MemoryEntryInvalid`）。
- 结构化抽取建议带 `source=structured_extract`（见 `memory.append_memory_entry`）。

## 相关 CLI

- `cai-agent memory health --json [--fail-on-grade C]`
- `cai-agent memory prune [--min-confidence] [--max-entries] [--drop-non-active]`
- `cai-agent memory validate-entries --json`
- `cai-agent memory extract --structured`
