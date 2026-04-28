# CAI Agent → Cursor 导出

本目录由 `cai-agent export --target cursor` 生成。

- `cai-export-manifest.json`：导出清单（机器可读）。
- `rules/`、`skills/` 等为从仓库根目录复制的子树。

**降级说明**：Cursor 原生规则格式可能与仓库 `rules/` 中 Markdown 不完全一致；若需 `.mdc` frontmatter 规则，请在本机再执行一次转换或 手动迁移。目录约定与脚手架：`cai-agent ecc layout` / `ecc scaffold`；详见 `docs/CROSS_HARNESS_COMPATIBILITY.zh-CN.md`。
