# 上下文压缩后续开发计划

> 交接目标：`CTX-COMPACT-N01` 到 `N07` 已完成真实压缩、LLM 模式、降级、离线质量评估、LLM summary retention gate、正式 schema 文件、多代 summary 合并与工具类型感知摘要。本文件只记录后续可开发项，供后续开发者按优先级接续。

## 当前基线

- `context_summary_v1` 已可在 graph 自动触发，也可由 TUI `/compress` 手动触发。
- `[context].compact_mode` 支持 `off | heuristic | llm`。
- LLM 摘要失败、非 JSON、或压缩后不变小时会降级 heuristic。
- LLM 摘要缺失初始目标、tail、路径、工具名或指定 marker 时会因 retention gate 失败降级 heuristic。
- `sessions --compact-eval --json` 输出 `sessions_compact_eval_v1`，可作为长会话质量 gate。
- `context_compaction_summary_v1`、`context_compaction_retention_v1`、`context_compaction_eval_v1` 已有正式 schema 文件和 fixtures 校验。
- 启发式压缩会合并已有 `context_summary_v1`，避免连续压缩时丢失旧路径、工具证据和对话要点。
- `tool_calls[]` 已按测试、traceback、git diff、search、read、command 等类型提取结构化证据。
- 已有聚焦测试覆盖：
  - `test_context_compaction.py`
  - `test_graph_context_compaction.py`
  - `test_sessions_compact_eval_cli.py`

## 后续任务队列

| 顺位 | 任务 ID | 目标 | 建议代码入口 | 验收门槛 |
|---|---|---|---|---|
| 1 | `CTX-COMPACT-N08` | TUI 压缩可视化：显示最近一次压缩 mode/source、before/after tokens、ratio、fallback reason、quality score | `tui.py`、`tui_session_strip.py` | TUI 单元测试覆盖状态文案和 `/compress` 后刷新 |
| 2 | `CTX-COMPACT-N09` | 安全/隐私过滤：summary 写入前脱敏 token、secret、JWT、常见凭据 | `context_compaction.py`、`security_scan.py` 或 PII helpers | 测试覆盖 secret 不进入 summary/eval 输出 |
| 3 | `CTX-COMPACT-N10` | 真实模型回归样本集：构造长会话 fixtures，分别跑 `heuristic` 与 `llm` 模式比较质量 | `cai-agent/tests/fixtures/`、`docs/qa/` | QA run 记录真实模型或 mock profile 结果；压缩质量基线写入 docs |

## 推荐实现顺序

1. 先做 `CTX-COMPACT-N08`，把已稳定的压缩状态和质量字段暴露给 TUI 用户。
2. `N09` 应在真实模型回归前完成，避免 QA 样本或摘要中固化敏感内容。
3. `N10` 最后做，作为整体质量基线和发布前验收。

## QA 测试矩阵

每个后续任务至少跑：

```powershell
python -m compileall -q cai-agent/src/cai_agent/context_compaction.py cai-agent/src/cai_agent/graph.py cai-agent/src/cai_agent/tui.py cai-agent/src/cai_agent/__main__.py
python -m pytest -q -p no:cacheprovider cai-agent/tests/test_context_compaction.py cai-agent/tests/test_graph_context_compaction.py cai-agent/tests/test_sessions_compact_eval_cli.py
```

触及 schema 时加：

```powershell
python -m pytest -q -p no:cacheprovider cai-agent/tests/test_schema*.py cai-agent/tests/test_cli_misc.py
```

触及 TUI 时加：

```powershell
python -m pytest -q -p no:cacheprovider cai-agent/tests/test_tui_session_strip.py cai-agent/tests/test_tui_slash_suggester.py
```

发布前建议：

```powershell
python -m pytest -q -p no:cacheprovider cai-agent/tests
python scripts/smoke_new_features.py
```

## 质量门槛

- 默认 `heuristic` 行为不得回退。
- `compact_mode = "off"` 不得生成 `context_summary_v1`。
- `compact_mode = "llm"` 的失败路径必须稳定降级，不能中断主任务。
- `sessions --compact-eval --json` 任一会话失败时必须 exit `2`。
- `context_summary_v1` 必须保留：
  - 初始用户目标
  - 最近 tail messages
  - 工具名
  - 重要路径
  - 用户指定 required marker
- 新增字段必须登记到 `docs/schema/README.zh-CN.md` 或正式 schema 文件。

## 文档更新要求

后续每完成一项：

1. 更新 `docs/CONTEXT_AND_COMPACT.zh-CN.md` 的配置、事件和 QA 说明。
2. 更新 `docs/schema/README.zh-CN.md` 或 schema 文件。
3. 更新 `docs/NEXT_ACTIONS.zh-CN.md` 与 `docs/DEVELOPER_TODOS.zh-CN.md`。
4. 运行 `scripts/finalize_task.py --task-id <ID> ...` 写入 QA run。
5. 如对用户可见，补 `CHANGELOG.md` / `CHANGELOG.zh-CN.md`。
