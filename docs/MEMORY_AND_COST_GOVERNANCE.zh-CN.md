# 记忆与成本治理方案（P1）

## 目标

- 将会话结果沉淀为可复用“项目记忆”
- 将 token/cost 从被动统计升级为主动治理

## 记忆系统 v1（建议 schema）

```json
{
  "id": "mem_20260417_xxx",
  "project": "Cai_Agent",
  "category": "build|test|debug|style|security",
  "content": "在本仓库运行测试请先执行 ...",
  "evidence": ["session:.cai-session-2026-04-17.json"],
  "confidence": 0.82,
  "expires_at": "2026-07-01T00:00:00Z"
}
```

## 成本治理策略 v1

- 默认模型使用中成本档，复杂任务再切高配模型
- 在“研究完成、里程碑完成、失败后重试前”建议 compact
- 对 MCP 数量与工具活跃数设置预算阈值告警

## 与现有功能对接

- 会话数据来源：`sessions` / `stats` / `workflow` 输出
- 质量门禁入口：`quality-gate` 命令
- 后续可新增：
  - `memory extract`
  - `memory list`
  - `cost budget --check`
