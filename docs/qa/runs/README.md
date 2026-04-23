# Regression run logs

This directory stores **auto-generated** Markdown reports from `scripts/run_regression.py` (which also runs `scripts/smoke_new_features.py` for JSON envelope checks).

- Filenames: `regression-YYYYMMDD-HHmmss.md`；T7 gate 手工回填可用 `t7-gate-YYYYMMDD-*.md`（见 [`T7_RELEASE_GATE_CHECKLIST.zh-CN.md`](../T7_RELEASE_GATE_CHECKLIST.zh-CN.md) 底部索引）
- **手工模板**：[`TEMPLATE_GATEWAY_S8_AC3.zh-CN.md`](TEMPLATE_GATEWAY_S8_AC3.zh-CN.md)（Gateway **S8-02 AC3** 压测记录，复制改名后提交）
- Policy: see `docs/QA_REGRESSION_LOGGING.md` (English) and `docs/QA_REGRESSION_LOGGING.zh-CN.md` (Chinese).

You may commit these logs after major releases or keep them for audit; if the volume grows, archive older files or point `QA_LOG_DIR` to a location outside the repo.
