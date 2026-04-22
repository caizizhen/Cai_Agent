# JSON 输出契约索引（S1-02）

本目录描述 **`cai-agent` 各命令 `--json` 或专用 JSON 输出** 的 `schema_version`、主要字段与 **exit 码约定**（与 [S1-03](../HERMES_PARITY_BACKLOG.zh-CN.md) 一致：成功 `0`，逻辑/阈值失败 `2`，用法错误 `2`）。

| 文档 | 命令 / 产物 | `schema_version` 示例 |
|------|----------------|----------------------|
| [OBSERVE_JSON.zh-CN.md](OBSERVE_JSON.zh-CN.md) | `observe --json` | `1.1` |
| [OBSERVE_REPORT_JSON.zh-CN.md](OBSERVE_REPORT_JSON.zh-CN.md) | `observe-report --json` | `observe_report_v1` |
| [INSIGHTS_JSON.zh-CN.md](INSIGHTS_JSON.zh-CN.md) | `insights --json` | `1.1` |
| [BOARD_JSON.zh-CN.md](BOARD_JSON.zh-CN.md) | `board --json` | `board_v1`（内嵌 `observe` 同源） |
| [SCHEDULE_AUDIT_JSONL.zh-CN.md](SCHEDULE_AUDIT_JSONL.zh-CN.md) | `.cai-schedule-audit.jsonl` / `daemon --jsonl-log` | 行级 `1.0` |
| [SCHEDULE_STATS_JSON.zh-CN.md](SCHEDULE_STATS_JSON.zh-CN.md) | `schedule stats --json` | `schedule_stats_v1` |

**尚未单列成文的命令**：`memory *`、`recall*`、`recall-index *`、`workflow --json`、`plugins --json` 等仍以源码与 pytest 为准；后续按同一格式补档。

破坏性变更时请 **升级对应 `schema_version`** 并更新本文档与 `CHANGELOG`。
