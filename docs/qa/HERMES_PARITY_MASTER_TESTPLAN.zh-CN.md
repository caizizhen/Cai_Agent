# Hermes 对齐总测试计划（Master Test Plan）

> 目标：为开发与测试提供统一的测试入口、用例分层和回归标准，覆盖 Hermes 对齐路线的全部 Sprint。

---

## 1. 测试策略总览

测试分四层：

1. **契约层（CLI/Schema）**
   - 命令参数、退出码、JSON 字段契约
2. **功能层（Feature）**
   - memory/recall/schedule/subagent/gateway 的功能正确性
3. **系统层（E2E）**
   - 多命令串联（如 nudge -> history -> nudge-report -> schedule）
4. **非功能层（Perf/Security/Reliability）**
   - 压测、稳定性、权限与密钥扫描

---

## 2. Sprint 测试矩阵

### Sprint 1（基线收敛）

- 重点：命令参数一致性、help 文本、schema 字段稳定性
- 通过标准：所有核心命令 `--json` 可稳定解析

### Sprint 2（Memory 2.0）

- 重点：health score、阈值守门、历史统计
- 通过标准：可稳定复现 low/medium/high 三种健康状态

### Sprint 3（Recall 2.0）

- 重点：排序、无命中解释、索引体检
- 通过标准：给定固定样本，排序结果可预测

### Sprint 4（Scheduler 2.0）

- 重点：重试/退避/依赖/并发
- 通过标准：故障注入后状态机正确、日志完整

### Sprint 5（Subagents）

- 重点：并行执行一致性、合并策略
- 通过标准：并行结果可重现且冲突可解释

### Sprint 6（Gateway Telegram）

- 重点：消息链路、会话连续性、安全策略
- 通过标准：跨端连续对话 + 非授权拒绝

### Sprint 7（Observability Pro）

- 重点：指标正确性、周报一致性
- 通过标准：同输入重复生成同统计结果

### Sprint 8（GA）

- 重点：全量回归、性能、发布门禁
- 通过标准：门禁全绿，无 P0/P1 未关闭缺陷

---

## 3. 用例分组与命名规范

命名建议：`[域]-[子域]-[编号]`

- `MEM-NDG-*`：memory nudge / report
- `RCL-IDX-*`：recall / index
- `SCH-DAE-*`：schedule daemon / run-due
- `SAG-PAR-*`：subagent parallel
- `GTW-TG-*`：telegram gateway
- `OBS-RPT-*`：observe/report
- `SEC-*`：安全与权限
- `PERF-*`：性能与稳定性

---

## 4. 回归套件建议

### 4.1 快速回归（PR 必跑）

- memory：`test_memory_*.py`
- recall：`test_recall_*.py`
- schedule：`test_schedule_*.py`
- 核心 smoke：`test_cli_misc.py`

### 4.2 全量回归（每日）

- `python3 -m pytest -q cai-agent/tests`
- `python3 scripts/run_regression.py`

### 4.3 发布回归（GA）

- 全量回归 + 压测 + 安全扫描 + 手工冒烟

---

## 5. 非功能测试要求

### 性能

- recall 检索耗时（小/中/大数据集）
- schedule daemon 长跑稳定性
- gateway 消息吞吐与恢复

### 安全

- secrets 扫描（误报率与漏报率）
- 命令审批策略绕过测试
- 网关身份鉴权与白名单

### 可靠性

- kill/restart 后状态恢复
- 文件损坏/缺失情况下降级行为
- 并发写入一致性

---

## 6. 缺陷等级与阻断规则

- **P0**：崩溃/数据破坏/安全越权 -> 阻断发布
- **P1**：核心能力不可用/结果错误 -> 阻断 GA
- **P2**：功能可用但体验问题 -> 可带缺陷发布

---

## 7. 测试产物要求

每次测试批次输出：

1. 执行命令列表
2. 通过/失败统计
3. 失败用例明细（含复现命令）
4. 风险评估（是否阻断）
5. 建议回归范围

建议落盘目录：`docs/qa/runs/`（沿用现有机制）

---

## 8. 与开发协作节奏

- 开发提测前：提交功能说明 + 命令样例 + JSON 样例
- QA 反馈后：开发需在 PR 中补“修复点 -> 新增测试”映射
- 每个 Sprint 结束：更新本文件 + 对应 feature testplan

