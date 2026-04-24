# Hermes 规划项 H5–H8（落地说明与后续）

本页为 **Sprint H5–H8** 的仓库内锚点：重功能已在独立 backlog / gateway 模块演进，此处记录 CLI 与文档入口，避免规划悬空。

| Sprint | 主题 | 仓库内入口 / 说明 |
|--------|------|---------------------|
| **H5-GW** | Gateway / 多端 | 见 `cai_agent/gateway_*.py`、`docs/` 下 Gateway 相关文档；Slash Commands 随平台 Webhook 配置扩展。 |
| **H6-NET** | 网络与工具面 | `fetch_url_*` 配置与权限在 `cai-agent.toml` `[permissions]`；重定向上限 `fetch_url_max_redirects`。 |
| **H7-WEB** | Web 运营 / 看板 | `cai-agent board` 与 `observe-report` 输出 JSON/Markdown；富 UI 可走独立前端仓。 |
| **H8-ECO** | 生态与迁移 | `cai-agent claw-migrate`（占位）；插件矩阵见 `plugins` 命令 `--with-compat-matrix`。 |
