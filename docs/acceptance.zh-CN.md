# 验收标准

版本 **1.2.0** · 架构 `layered-pi+harness-ui`

## Pi 内核

| # | 要求 | 状态 |
|---|------|------|
| 1 | 默认工具：read、write、edit、bash | PASS |
| 2 | 顺序 Agent 循环 + 事件 | PASS |
| 3 | 会话 JSONL 持久化/恢复 + 工作区 meta | PASS |
| 4 | OpenAI 兼容 + Anthropic Messages（含 mock） | PASS |
| 5 | ui / adapter / engine 分层 | PASS |
| 6 | 统一 EventBus 事件 | PASS |

## UI / Desktop

| # | 要求 | 状态 |
|---|------|------|
| 1 | Harness 风格 Web 壳（会话挂在工作区下） | PASS |
| 2 | Electron + Python sidecar | PASS |
| 3 | App 内添加/切换工作区（无强制启动选目录） | PASS |
| 4 | 设置：协议选择 + 拉模型 + runtime.json | PASS |
| 5 | CLI `run` / `ui` / `web` / `--dump-config` | PASS |
| 6 | 测试通过（`python -m pytest -q`） | PASS |

详见 [architecture.zh-CN.md](architecture.zh-CN.md) 与 [guide.zh-CN.md](guide.zh-CN.md)。
