# AGENTS.md — 统一上下文入口（Hermes HX-AGENTS）

在仓库根放置 `AGENTS.md`（或 `AGENTS.zh-CN.md`），与 `CAI.md` / `README` 并列，供人类与 Agent 快速对齐：

- **产品目标**与当前里程碑  
- **目录约定**（源码、配置、脚本）  
- **禁止事项**（例如禁止直改生产密钥、禁止跳过分支保护）  
- **常用命令**（测试、lint、发版 gate）

`cai-agent` 的 `project_context` 已支持从工作区读取多份说明文件；将本文件加入团队规范后，可在 PR 模板中提示贡献者更新本节。
