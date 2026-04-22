# `cai-agent observe-report --json`

## schema_version

`observe_report_v1`（见 `_build_observe_report_payload`）。

## 顶层字段（摘要）

| 字段 | 类型 | 说明 |
|------|------|------|
| `state` | string | `pass` / `warn` / `fail`，由告警级别聚合 |
| `alerts` | array | 每项含 `metric`、`value`、`warn_threshold`、`fail_threshold`、`level`（`ok`/`warn`/`fail`） |
| `observe` | object | 嵌套精简 observe 信息（`schema_version`、`sessions_count`、`aggregates`） |

阈值参数：`--warn-failure-rate` / `--fail-failure-rate`、`--warn-token-budget` / `--fail-token-budget`、`--warn-tool-errors` / `--fail-tool-errors`。

## Exit 码

| 条件 | exit |
|------|------|
| `state == fail` | `2` |
| `state == warn` 且未传 `--fail-on-warn` | `0` |
| `state == warn` 且传入 `--fail-on-warn` | `2` |
| `state == pass` | `0` |
