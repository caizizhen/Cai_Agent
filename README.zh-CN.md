# CAI Agent

**Pi 风格编码 Agent 内核** + DeepSeek Harness 风格的 CLI / Web / Desktop UI。

> 内核已是 Pi：`pi_core` + `pi_session` + 默认工具（`read` / `write` / `edit` / `bash`），经 EventBus 适配层对接 UI。UI 仅借鉴 Harness 壳层，不是 Cordis/DSH 内核。

```text
Electron (desktop/) ──► Web 壳 + EventBus ──► Pi 引擎
CLI / Web            ──► ui / surfaces     ──► Pi 引擎
```

English: [README.md](README.md).

## 能力

- **Pi 引擎** — 顺序工具循环、JSONL 会话、中止
- **模型协议** — OpenAI Compatible **与** Anthropic Messages
- **Harness UI** — 工作区树 + 嵌套会话、设置、文件抽屉
- **Desktop** — Electron + 本地 Python sidecar（Win / macOS / Linux）
- **分层** — `ui` → `adapter` → `engine`

## 安装

```bash
pip install -e ".[dev]"
```

## 快速开始

### Desktop

```bash
cd desktop
npm install
npm run desktop
```

设置 → 选择协议（`openai` / `anthropic`）→ 填写 Base URL / API Key / Model。  
侧栏 **工作区** 添加文件夹；会话挂在对应工作区下。

### CLI / Web

```bash
CAI_MOCK=1 cai-agent run "hello"
cai-agent ui
cai-agent web --port 8765
```

可复制 [`config.example.yaml`](config.example.yaml) → `cai.config.yaml`。

环境变量：`CAI_PROVIDER`、`LM_BASE_URL`、`LM_MODEL`、`LM_API_KEY`、`CAI_WORKSPACE`、`CAI_HOME`、`CAI_MOCK`。

## 目录

| 路径 | 作用 |
|------|------|
| `src/cai_agent/pi_core/` | Pi Agent 循环 |
| `src/cai_agent/pi_session/` | 会话存储 |
| `src/cai_agent/adapter/` | EventBus + 桥接 |
| `src/cai_agent/llm/` | OpenAI / Anthropic 客户端 |
| `src/cai_agent/surfaces/` | Web API + 静态壳 |
| `src/cai_agent/ui/` | CLI / TUI |
| `desktop/` | Electron 宿主 |

## 文档

| 文档 | |
|------|--|
| [架构](docs/architecture.zh-CN.md) | [English](docs/architecture.md) |
| [指南](docs/guide.zh-CN.md) | [English](docs/guide.md) |
| [验收](docs/acceptance.zh-CN.md) | [English](docs/acceptance.md) |

## 测试

```bash
python -m pytest -q
```
