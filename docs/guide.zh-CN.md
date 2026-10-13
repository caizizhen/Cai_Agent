# 使用指南

## 安装

```bash
pip install -e ".[dev]"
```

## Desktop（Windows / macOS / Linux）

```bash
cd desktop
npm install
npm run desktop
```

直接打开应用，在侧栏「工作区」树中添加/切换项目（Harness 风格）。  
设置里选择 **OpenAI Compatible** 或 **Anthropic Messages**，填写 Base URL / API Key / Model。  
配置写入 `$CAI_HOME/runtime.json`（默认 `~/.cai`）。

可选打包：

```bash
npm run dist:win
npm run dist:mac
npm run dist:linux
```

## CLI / Web

```bash
CAI_MOCK=1 cai-agent run "hello"
CAI_MOCK=1 cai-agent run --json "hello"
cai-agent ui
cai-agent web --port 8765
cai-agent --model my-model --max-steps 8 --dump-config
```

可复制 `config.example.yaml` → `cai.config.yaml`，或在 App 内配置。

## 环境变量

| 变量 | 含义 |
|------|------|
| `CAI_PROVIDER` | `openai` 或 `anthropic` |
| `LM_BASE_URL` / `LM_MODEL` / `LM_API_KEY` | 模型接口 |
| `CAI_WORKSPACE` / `CAI_HOME` | 工作区与数据目录 |
| `CAI_CONFIG` | 配置文件路径 |
| `CAI_MOCK` / `CAI_MOCK_REPLY` | Mock LLM |
| `CAI_MAX_ITER` / `CAI_STREAM` / `CAI_DEBUG` | 引擎 / UI 开关 |

## 测试

```bash
python -m pytest -q
```
