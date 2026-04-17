# QA 回归测试记录说明

每次做**完整 CLI 回归**时，应留下可追溯的文档记录：默认由脚本**自动生成** Markdown；若有失败或需要说明，可再**人工补充**分析结论。

## 自动生成记录（推荐）

在**仓库根目录**执行：

```bash
python scripts/run_regression.py
```

结束后会写入：

- `docs/qa/runs/regression-YYYYMMDD-HHmmss.md`（文件名中的时间为**本机本地**时间前缀）

可通过环境变量 **`QA_LOG_DIR`** 指定报告目录（相对仓库根或绝对路径）。

设置 **`QA_SKIP_LOG=1`** 则**不写** Markdown 文件（仅控制台输出）。

## 每次记录里应包含什么（脚本已写入）

1. **元数据**：执行时间、仓库根路径、`git rev-parse HEAD`（若可用）、Python 版本、平台、与回归相关的环境变量（如 `REGRESSION_STRICT_MODELS`、`QA_LOG_DIR`）。说明：`CAI_MOCK` 仅在需要 mock 的子进程中注入，一般不会出现在全局环境里。
2. **总览**：整次回归是否通过、脚本退出码。
3. **步骤表**：步骤名称、完整命令行、期望退出码集合、实际退出码、是否通过。
4. **失败详情**：对失败步骤，附截断后的子进程 `stdout` / `stderr`（控制体积，便于阅读）。

## 人工补充（失败或异常时）

1. 打开对应日期的 `docs/qa/runs/regression-*.md`。
2. 在同一 cwd（仓库根）复现失败命令。
3. 可在该文件末尾增加 **「分析备注」** 小节：根因、工单号、修复 PR 等。

## 英文版说明

英文策略见 **`docs/QA_REGRESSION_LOGGING.md`**。
