# T7 发版 Gate 检查清单（手工）

与 [`PRODUCT_PLAN.zh-CN.md`](../PRODUCT_PLAN.zh-CN.md) **§三 T7** 对齐：主版本或对外发版前逐项勾选；**非全绿不得宣称 GA 完成**（允许单项标注豁免理由与责任人）。

## 1. 自动化门禁

| 项 | 命令 / 条件 | 通过 |
|----|----------------|------|
| T1 全量单测 | `cd cai-agent && python -m pytest tests -q` | [ ] |
| T2 回归脚本 | 仓库根：`python scripts/run_regression.py`（或等价 `PYTHONPATH=cai-agent/src` + `python -m cai_agent`） | [ ] |
| 冒烟子集 | 仓库根：`python scripts/smoke_new_features.py`，退出码 `0` 且输出含 `NEW_FEATURE_CHECKS_OK` | [ ] |

## 2. 产品与契约文档

| 项 | 说明 | 通过 |
|----|------|------|
| Parity 矩阵 | 至少更新 [`PARITY_MATRIX.zh-CN.md`](../PARITY_MATRIX.zh-CN.md) 一行（`Next`→`Done` / `MCP` 链接 / `OOS` 备注） | [ ] |
| 执行清单 | [`PRODUCT_PLAN.zh-CN.md`](../PRODUCT_PLAN.zh-CN.md) §二 / §三 与本次发版范围一致 | [ ] |
| CHANGELOG | [`CHANGELOG.md`](../../CHANGELOG.md) 与 [`CHANGELOG.zh-CN.md`](../../CHANGELOG.zh-CN.md) 同步写入本版条目（流程见 [`CHANGELOG_SYNC.zh-CN.md`](../CHANGELOG_SYNC.zh-CN.md)） | [ ] |
| Schema 索引 | [`docs/schema/README.zh-CN.md`](../schema/README.zh-CN.md) 中本版新增/变更 JSON 契约已描述 | [ ] |

### 2.1 Gateway S8-02 AC3（若本版含 Gateway 发布）

| 项 | 说明 | 通过 |
|----|------|------|
| 500 消息压测 | 按 [`GATEWAY_500_MSG_STRESS_RUNBOOK.zh-CN.md`](GATEWAY_500_MSG_STRESS_RUNBOOK.zh-CN.md) 执行并回填 [`docs/qa/runs/`](runs/)（可用 [`runs/TEMPLATE_GATEWAY_S8_AC3.zh-CN.md`](runs/TEMPLATE_GATEWAY_S8_AC3.zh-CN.md)） | [ ] |

## 3. 运行与健康

| 项 | 说明 | 通过 |
|----|------|------|
| `doctor` | 目标工作区执行 `cai-agent doctor`（或 `--json`），无未解释的阻塞项 | [ ] |
| 配置抽样 | 若本版涉及 TOML/权限：抽查 `cai-agent.toml` / `[permissions]` 与文档一致 | [ ] |

## 4. 记录

- 结论可回填：`docs/qa/runs/` 下追加一篇 Markdown，或在 [`DEVELOPMENT_PROGRESS_TRACKER.zh-CN.md`](../DEVELOPMENT_PROGRESS_TRACKER.zh-CN.md) 记一行。
- **豁免**：某项无法执行时，写明原因、计划补测日期与 owner。

---

*维护：发版负责人随 PR 更新本清单勾选状态或链接到具体 `docs/qa/runs/*` 报告。*
