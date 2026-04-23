# 指标事件 JSONL（S7-01 · `metrics_schema_v1`）

> 非 CLI 标准输出；当环境变量 **`CAI_METRICS_JSONL`** 指向可写路径时，部分命令会**追加一行 JSON**（JSONL），便于外接采集。

## 版本

- **`schema_version`**：固定为 **`metrics_schema_v1`**（与 `cai_agent.metrics.METRICS_SCHEMA_VERSION` 一致）。

## 字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `schema_version` | string | 是 | `metrics_schema_v1` |
| `ts` | string (ISO8601 UTC) | 是 | 事件时间 |
| `module` | string | 是 | 逻辑模块，如 **`observe`** |
| `event` | string | 是 | 事件名，如 **`observe.summary`**、**`observe.report`** |
| `latency_ms` | number | 是 | 本次操作耗时（毫秒）；无则 `0` |
| `tokens` | int | 是 | 关联 token 计数（observe 路径下为聚合 **`total_tokens`** / **`token_total`**）；无则 `0` |
| `cost_usd` | number | 否 | 可选成本 |
| `success` | bool | 是 | 是否视为成功落盘 |

## 触发路径（当前实现）

- **`cai-agent observe`**（默认摘要或 **`--json`**）：成功生成 payload 后写入 **`observe.summary`**。
- **`cai-agent observe report`**：成功生成报告后写入 **`observe.report`**。

## 示例行

```json
{"schema_version":"metrics_schema_v1","ts":"2026-04-23T12:00:00+00:00","module":"observe","event":"observe.summary","latency_ms":12.3,"tokens":0,"success":true}
```
