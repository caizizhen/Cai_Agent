# CAI Agent 试点用户说明

本文面向**受邀试点**：在正式发版或大规模推广前，在真实工作区中小范围试用，并把**稳定性、易用性、风险点**反馈给项目方。

---

## 1. 试点目标（你需要帮什么）

- 验证在 **Windows / 你的常用工作区** 下：`init` → `doctor` → `run` / `ui` 是否顺畅。  
- 验证 **OpenAI 兼容端点**（如 LM Studio、自建网关）在长时间对话下是否稳定。  
- 发现 **文档没说清的地方**、**误伤权限**、**令人困惑的报错**，便于改进。

试点**不是**生产级 SLA 承诺；遇到问题请优先保护**代码与密钥**，并走反馈渠道（见 §6）。

---

## 2. 适用环境与前置条件

| 项 | 说明 |
|----|------|
| Python | **3.11+**（与 `cai-agent/pyproject.toml` 一致） |
| 网络 | 能访问你的 **LLM 服务地址**（本地或内网均可） |
| 磁盘 | 建议在**副本仓库或分支**上试用，避免未审查的自动改文件影响主线 |

---

## 3. 安装与版本

1. 使用项目方提供的 **Git 提交 / 分支 / 预发布包**（以对方通知为准）。  
2. 在仓库的 `cai-agent` 目录执行：

```bash
cd cai-agent
pip install -e .
```

3. 确认命令可用：

```bash
cai-agent --help
```

当前包版本号可参考 `cai-agent/pyproject.toml` 中的 `version`；反馈问题时请**写明该版本或 commit hash**。

---

## 4. 配置与安全（必读）

1. 在工作区根目录生成配置（若已有可跳过）：

```bash
cai-agent init
```

2. 编辑 **`cai-agent.toml`**，至少配置 `[llm]` 的 `base_url`、`model`、`api_key`。  
3. **勿将含真实 Key 的 `cai-agent.toml` 提交到 Git**；勿在公开渠道粘贴完整配置。  
4. 建议先阅读权限相关段落：`[permissions]`、`run_command` 白名单、`write_file` 策略；不确定时用 **`cai-agent doctor`** 核对当前工作区与配置来源。

更细路径见：[ONBOARDING.zh-CN.md](ONBOARDING.zh-CN.md)。

---

## 5. 建议试用清单（约 30 分钟）

按顺序做即可；任一步失败可把终端输出（**打码密钥后**）一并反馈。

| 步骤 | 命令 / 操作 | 期望 |
|------|-------------|------|
| 1 | `cai-agent doctor` | 无阻塞性错误；工作区与 LLM 配置可读 |
| 2 | `cai-agent run "用一句话说明当前目录用途"` | 得到合理自然语言回复 |
| 3 | （可选）在项目根执行：`cai-agent ui -w .` | TUI 能启动并发起一轮对话 |
| 4 | （可选）`cai-agent plan "列出本仓库入口模块，不改代码"` | 规划类输出可读 |
| 5 | （可选）若试点范围包含 MCP：按项目方提供的 MCP 文档做一次 **list / call** | 工具列表与一次调用成功 |

---

## 6. 反馈方式（请带齐上下文）

请通过项目方指定的渠道反馈（例如 **GitHub Issue** 或内部工单），并尽量附上：

- **操作系统**与 Python 版本  
- **`cai-agent doctor` 输出**（删除或替换 `api_key` 等敏感字段）  
- **复现步骤**与**期望 vs 实际**  
- 若与目标能力相关，可注明对应 [PRODUCT_GAP_ANALYSIS.zh-CN.md](PRODUCT_GAP_ANALYSIS.zh-CN.md) 或 [ROADMAP_EXECUTION.zh-CN.md](ROADMAP_EXECUTION.zh-CN.md) 中的哪一类场景

---

## 7. 试点用户需要知道的限制

- 本工具可对工作区内文件**读/写**、在允许范围内**执行命令**；请在**可信目录**使用并理解 `[permissions]`。  
- 与 **Anthropic Claude Code 官方安装器、插件市场、账号体系** 无绑定；模型与端点由你方自行提供。  
- 功能与路线图以仓库文档为准：[PRODUCT_GAP_ANALYSIS.zh-CN.md](PRODUCT_GAP_ANALYSIS.zh-CN.md)、[PARITY_MATRIX.zh-CN.md](PARITY_MATRIX.zh-CN.md)。

---

## 8. 退出试点

卸载或不再使用该环境即可；若曾安装为 `pip install -e .`，可在对应 venv 中 `pip uninstall cai-agent`。  
试点期间产生的本地会话文件、日志路径以项目方说明为准。

---

*文档维护：产品 / 交付；详细上手与 CI 见 [ONBOARDING.zh-CN.md](ONBOARDING.zh-CN.md)。*
