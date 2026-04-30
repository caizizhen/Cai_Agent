# 上下文压缩后续开发计划

> 交接目标：`CTX-COMPACT-N01` 到 `N03` 已完成真实压缩、LLM 模式、降级与离线质量评估。本文件只记录后续可开发项，供后续开发者按优先级接续。

## 当前基线

- `context_summary_v1` 已可在 graph 自动触发，也可由 TUI `/compress` 手动触发。
- `[context].compact_mode` 支持 `off | heuristic | llm`。
- LLM 摘要失败、非 JSON、或压缩后不变小时会降级 heuristic。
- `sessions --compact-eval --json` 输出 `sessions_compact_eval_v1`，可作为长会话质量 gate。
- 已有聚焦测试覆盖：
  - `test_context_compaction.py`
  - `test_graph_context_compaction.py`
  - `test_sessions_compact_eval_cli.py`

## 后续任务队列

| 顺位 | 任务 ID | 目标 | 建议代码入口 | 验收门槛 |
|---|---|---|---|---|
| 1 | `CTX-COMPACT-N04` | LLM 摘要质量校验：对 LLM summary 也执行 marker/path/tool/tail 保留检查，不达标时降级 heuristic | `context_compaction.py`、`graph.py`、`tui.py` | pytest 覆盖 LLM 摘要缺 marker、缺路径、缺工具名时降级；progress 记录 `compact_fallback` reason |
| 2 | `CTX-COMPACT-N05` | 正式 JSON Schema：为 summary/eval 输出补 schema 文件和 schema 校验测试 | `cai_agent/schemas/`、`docs/schema/README.zh-CN.md` | 新增 `context_compaction_summary_v1.schema.json`、`context_compaction_eval_v1.schema.json`；pytest 校验 fixtures |
| 3 | `CTX-COMPACT-N06` | 多代压缩合并：识别已有 `context_summary_v1`，避免 summary 套 summary 造成信息衰减 | `context_compaction.py` | 两次连续压缩后 summary 仍保留初始目标、最近意图、路径和工具证据；token 不反弹 |
| 4 | `CTX-COMPACT-N07` | 工具类型感知摘要：对 read/search/test/git diff/run_command 输出分别提取结构化证据 | `context_compaction.py`、工具结果解析辅助函数 | 测试覆盖 pytest 失败、traceback、git diff、search 命中、长文件读取 |
| 5 | `CTX-COMPACT-N08` | TUI 压缩可视化：显示最近一次压缩 mode/source、before/after tokens、ratio、fallback reason、quality score | `tui.py`、`tui_session_strip.py` | TUI 单元测试覆盖状态文案和 `/compress` 后刷新 |
| 6 | `CTX-COMPACT-N09` | 安全/隐私过滤：summary 写入前脱敏 token、secret、JWT、常见凭据 | `context_compaction.py`、`security_scan.py` 或 PII helpers | 测试覆盖 secret 不进入 summary/eval 输出 |
| 7 | `CTX-COMPACT-N10` | 真实模型回归样本集：构造长会话 fixtures，分别跑 `heuristic` 与 `llm` 模式比较质量 | `cai-agent/tests/fixtures/`、`docs/qa/` | QA run 记录真实模型或 mock profile 结果；压缩质量基线写入 docs |

## 推荐实现顺序

1. 先做 `CTX-COMPACT-N04`，因为它直接提升 `compact_mode = "llm"` 的可靠性。
2. 再做 `CTX-COMPACT-N05`，稳定 JSON 合约后再扩展 UI/CI 消费面。
3. `N06` 和 `N07` 可并行推进，但要避免同时修改同一段 summary payload 结构。
4. `N08` 依赖 `N04/N05` 的字段稳定后再做。
5. `N09` 应在真实模型回归前完成，避免 QA 样本或摘要中固化敏感内容。
6. `N10` 最后做，作为整体质量基线和发布前验收。

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
