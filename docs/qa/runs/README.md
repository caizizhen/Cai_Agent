# Regression run logs

This directory stores **auto-generated** Markdown reports from `scripts/run_regression.py` (which also runs `scripts/smoke_new_features.py` for JSON envelope checks).

- Filenames: `regression-YYYYMMDD-HHmmss.md`
- Policy: see `docs/QA_REGRESSION_LOGGING.md` (English) and `docs/QA_REGRESSION_LOGGING.zh-CN.md` (Chinese).

You may commit these logs after major releases or keep them for audit; if the volume grows, archive older files or point `QA_LOG_DIR` to a location outside the repo.
