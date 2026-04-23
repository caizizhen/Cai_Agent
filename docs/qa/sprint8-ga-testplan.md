# Sprint 8 QA 测试计划：GA 收敛（性能 + 安全 + 发布）

> 对应开发文档：`docs/HERMES_PARITY_SPRINT_PLAN.zh-CN.md` §Sprint 8  
> 对应 backlog：`docs/HERMES_PARITY_BACKLOG.zh-CN.md` §Epic S8  
> 注意：本阶段为发布门禁阶段，**所有 P0 必须全部通过**才能进入发布流程。

---

## 1. 发布门禁清单（GA Gate）

以下所有项必须通过，方可执行发布：

| 类别 | 项目 | 状态 |
|------|------|------|
| 功能 | S1~S7 所有 P0/P1 测试通过 | ✅（以 **`pytest cai-agent/tests`** 为准） |
| 回归 | 全量回归 414+ 用例通过 | ✅（**`0.6.15`** 本机；以 CI 为准） |
| 性能 | recall 200 文件 < 5s | ✅（**`scripts/perf_ga_gate.py`** + **`test_perf_ga_s8_02`**） |
| 性能 | schedule daemon 100 轮次无崩溃 | ✅（**`test_perf_ga_s8_02`** mock 执行；可选 **`perf_ga_gate.py --pytest-daemon`**） |
| 性能 | gateway 500 消息无掉线（如已实现） | ⬜（**S8-02 AC3** 真机专项） |
| 安全 | security-scan 零 P0 告警 | ✅（**`scripts/security_ga_gate.py`** + **`test_sec_ga_s8_03`** 扫 **`src`**） |
| 安全 | 无硬编码 API key 或 token | ✅（**`test_sec_ga_s8_03`** 引号 **`sk-`** 长字面量扫描） |
| 安全 | gateway allowlist bypass 测试通过 | ✅（**`test_gateway_telegram_cli`** **`not_allowed`**） |
| 文档 | CHANGELOG 0.6.0 章节完整 | ✅（**0.6.9**：含 **Breaking changes / New CLI / Deprecations** 小节） |
| 文档 | 迁移指南覆盖所有 breaking changes | ✅（**[`docs/MIGRATION_GUIDE.md`](../MIGRATION_GUIDE.md)**；自动化 **`test_migration_guide_present`**） |

---

## 2. 全量回归测试

### GA-REG-001：单元与 CLI 测试全量通过
- **执行**：
  ```bash
  cd cai-agent
  python3 -m pytest -q tests/
  ```
- **期望**：全部通过，无 skip（或 skip 均有记录原因）

### GA-REG-002：回归脚本产出报告
- **执行**：
  ```bash
  python3 scripts/run_regression.py
  ```
- **期望**：
  - 所有用例通过
  - 在 `docs/qa/runs/` 生成带时间戳的报告

### GA-REG-003：跨 Sprint 功能串联端到端
- **执行**（手工）：
  1. `memory health` → 获取评分
  2. `schedule add-memory-nudge` → 创建巡检任务
  3. `schedule run-due --execute` → 执行任务
  4. `memory nudge-report` → 查看历史
  5. `observe report` → 查看运营报告
- **期望**：所有步骤正常，数据链路连通

---

## 3. 性能测试

### PERF-GA-001：recall 200 文件全量扫描
- **执行**：`python3 scripts/perf_recall_bench.py --sessions 200`
- **期望**：scan 耗时 < 5s，无 OOM

### PERF-GA-002：recall-index 200 文件搜索
- **执行**：build 索引后执行 `recall-index search --query test`
- **期望**：搜索耗时 < 500ms

### PERF-GA-003：schedule daemon 长跑稳定性
- **执行**：`cai-agent schedule daemon --max-cycles 100 --execute --json`（mock 执行）
- **期望**：
  - 100 轮次正常完成
  - 无内存泄漏（RSS 增长 < 50MB）
  - 无死锁

### PERF-GA-004：memory health 1000 条目性能
- **前置条件**：entries.jsonl 包含 1000 条目
- **执行**：`cai-agent memory health --json`
- **期望**：耗时 < 5s

### PERF-GA-005：并发 workflow 吞吐（如已实现）
- **执行**：10 个并行步骤 workflow，`--max-concurrent 3`
- **期望**：正常完成，耗时比串行缩短明显

---

## 4. 安全测试

### SEC-GA-001：security-scan 零高风险告警
- **执行**：`cai-agent security-scan --json`
- **期望**：`ok=true` 或告警全部为 P2 级别

### SEC-GA-002：代码库无硬编码 API key
- **执行**：
  ```bash
  rg "sk-[a-zA-Z0-9]+" --include="*.py" cai-agent/
  rg "Bearer [a-zA-Z0-9]+" --include="*.py" cai-agent/
  ```
- **期望**：无实际 key（测试用假 key 除外）

### SEC-GA-003：配置文件的 api_key 字段脱敏
- **执行**：`cai-agent doctor --json`
- **期望**：输出中 api_key 显示为 `***` 或省略

### SEC-GA-004：gateway allowlist bypass 测试（如已实现）
- **步骤**：通过非 allowlist chat_id 发送消息
- **期望**：被拒绝，不触发执行

### SEC-GA-005：命令审批绕过测试
- **前置条件**：`[permissions].run_command = ask`，非交互模式
- **执行**：触发需要命令执行的任务，无 `--auto-approve`
- **期望**：任务拒绝，给出清晰提示

---

## 5. Breaking Change 验证

### GA-COMPAT-001：已弃用字段仍可解析（向后兼容）
- **执行**：使用旧格式 session 文件运行 `sessions --json`
- **期望**：不崩溃，有 deprecation 提示

### GA-COMPAT-002：schema 版本升级时旧版本客户端给出提示
- **前置条件**：索引文件为 schema 1.0，当前版本为 1.1
- **执行**：`recall-index info --json`
- **期望**：输出包含版本不匹配警告，但不崩溃

---

## 6. 发布前手工冒烟（Release Smoke）

以下步骤在全新安装环境（无历史数据）中手工执行：

1. `pip install -e cai-agent` → 成功安装
2. `cai-agent init` → 生成配置文件
3. `cai-agent doctor` → 无关键错误
4. `cai-agent run "列出当前目录结构"` → 正常执行
5. `cai-agent memory extract --limit 1` → 生成记忆文件
6. `cai-agent memory nudge --json` → 正常输出
7. `cai-agent recall --query test --json` → 正常输出（0 命中也算通过）
8. `cai-agent schedule add --every-minutes 1 --goal "test" --json` → 任务添加
9. `cai-agent quality-gate --json` → 正常输出
10. `cai-agent security-scan --json` → 正常输出

---

## 7. 缺陷关闭标准

发布前必须关闭：
- 所有 P0 缺陷（无条件）
- 所有 P1 缺陷（允许 workaround + 已知问题文档记录）
- P2 缺陷按优先级处理，允许带缺陷发布（需 PM 确认）

---

## 8. 回归关联

```bash
cd cai-agent
python3 -m pytest -q tests/
python3 -m pytest -q tests/test_memory_*.py tests/test_recall_*.py tests/test_schedule_*.py
```

---

## 9. 验收信号

- 发布门禁清单所有 ⬜ 都变为 ✅
- 全量回归报告在 `docs/qa/runs/` 存档
- CHANGELOG 0.6.0 章节与 PR 描述一致
