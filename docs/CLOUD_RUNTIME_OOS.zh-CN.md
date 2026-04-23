# 云运行后端（Modal / Daytona 等）：范围与 OOS 备案

> **结论**：**默认发行物不包含**「随包交付的 Modal / Daytona / 其他云沙箱休眠编排」；运行形态以 **本机/自有容器内 `cai-agent` 进程** 为主。若未来单独立项，须另起版本线与安全评审。

## 1. 术语

| 概念 | 含义 |
|------|------|
| **云运行后端** | 将 Agent 主循环、工具执行或工作区挂载到 **按需启动 / 休眠计费** 的远程环境（如 Modal Functions、Daytona Sandbox、托管 Devcontainer 等），与「本机一条 `cai-agent run`」相对。 |
| **OOS** | **Out of scope**：本仓库 **不承诺** 实现、不承诺长期维护该路径；集成方可自建。 |

## 2. 为何当前 OOS

1. **安全与数据边界**：远程沙箱涉及 **工作区同步、密钥注入、出站网络策略**；与现有 **`[permissions]` / `fetch_url` / `run_command`** 组合后攻击面显著扩大，需独立威胁模型。
2. **产品焦点**：Hermes / claude-code parity 主线优先 **CLI + 网关 + 记忆 + 调度**；云休眠编排属于 **平台化底座**，不阻塞 L1 发版（见 [PRODUCT_PLAN.zh-CN.md](PRODUCT_PLAN.zh-CN.md) §〇.2、§三之二）。
3. **供应商锁定**：Modal、Daytona、云厂商 API 变更频繁；纳入默认交付意味着 **持续适配成本**，当前团队容量下以文档与 **MCP/侧车** 模式更稳妥。

## 3. 推荐替代路径（集成方可选）

| 路径 | 说明 |
|------|------|
| **容器一条命令** | 在标准 OCI 镜像中安装 `cai-agent`，挂载只读/读写卷到工作区；由现有 CI/CD 拉起/销毁；**无**内置「休眠计费」逻辑。 |
| **MCP / 外部编排** | 将重负载工具放到 **自建 MCP Bridge** 或 **Kubernetes Job**；`cai-agent` 仍跑在可信网络一侧，仅通过 MCP 调用远端能力。 |
| **用户态 SSH / devcontainer** | 开发者在远端 VM 内自行 `pip install` 与本仓库文档对齐；密钥仍走 **`api_key_env`** / 环境变量，不进入镜像层。 |

## 4. 若未来立项（非承诺）

最小验收应包括：**工作区同步协议**、**密钥不落盘策略**、**与 `doctor`/`release-ga` 的门禁对齐**、**网络出站默认拒绝 + 显式 allowlist**、**版本矩阵**（Python、`cai-agent`、供应商 SDK）。

## 5. 索引

- 产品表：[PRODUCT_PLAN.zh-CN.md](PRODUCT_PLAN.zh-CN.md)（§一「运行后端」、§三之二 **§一 P2**）
- Parity：[PARITY_MATRIX.zh-CN.md](PARITY_MATRIX.zh-CN.md) **L3 — 云运行后端** 行（`OOS`）
