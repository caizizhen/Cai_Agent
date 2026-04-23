# Gateway 500 条消息压测 Runbook（S8-02 AC3）

> **Backlog**：[`docs/HERMES_PARITY_BACKLOG.zh-CN.md`](../HERMES_PARITY_BACKLOG.zh-CN.md) Sprint 8  
> **GA 计划表**：[`sprint8-ga-testplan.md`](sprint8-ga-testplan.md) 中 **PERF-GA** 与 **gateway 500 消息**行（当前为真机专项 **⬜**）

本项验证：**在真实 Bot / Webhook 环境下，连续收发约 500 条消息（可含轻量命令）进程不崩溃、无静默断连、无未处理异常刷屏**。自动化仓库内已有 **recall / daemon** 压测（`scripts/perf_ga_gate.py`、`tests/test_perf_ga_s8_02.py`），**不替代**本 runbook。

## 1. 前置条件

| 项 | 说明 |
|----|------|
| 平台 | 至少选一条：**Telegram**（`gateway telegram …`）或已绑定的 **Discord Polling** / **Slack Webhook** |
| 配置 | 生产或**独立测试 Bot** token；**`.cai/`** 映射与 allowlist 已配置 |
| 观测 | 终端或日志文件可保存完整输出；可选 **`CAI_METRICS_JSONL`** 记录 gateway 事件 |

## 2. 执行步骤（Telegram 示例）

1. 启动服务（按你环境选择 webhook 或 getUpdates 模拟路径），确认 **`gateway status --json`** 为健康。
2. 使用第二个账号或脚本，向 Bot **连续发送 500 条**短文本（建议每条 ≤256 字符，间隔 **50–200 ms** 可调，避免触发平台 flood ban）。
3. 每 **50 条**记录一次：进程 RSS、CPU、`gateway` 日志中 error 计数。
4. 可选：穿插 **`/ping`** 或等价命令 **20 次**，确认命令仍响应。
5. 结束后执行 **`cai-agent doctor --json`**，确认无新增异常配置项。

## 3. 通过标准

- **500/500** 条消息侧无 **5xx** 或未捕获异常导致进程退出。
- 无 **连续 10 条**以上消息丢失（与 Telegram `getUpdates` offset 或 webhook 应答对照）。
- 内存增长在可接受范围（建议 **RSS 增长 < 200MB** 或团队基线内）。

## 4. 回填

将结论写入 **`docs/qa/runs/`** 新文件，命名示例：`gateway-s8-ac3-YYYYMMDD.md`，并在 [`sprint8-ga-testplan.md`](sprint8-ga-testplan.md) 将对应行改为 **✅** 且链接到该报告。

---

*维护：Discord/Slack 路径验证通过后，在本 runbook 追加一节「平台差异」与实测参数。*
