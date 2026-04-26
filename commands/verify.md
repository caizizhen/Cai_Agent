# /verify

## 用途

执行持续验证循环，确认改动满足验收标准。

## 建议流程

1. 定义验证项：功能、错误路径、性能/安全。
2. 运行快速验证：关键命令或关键测试。
3. 记录验证结果与失败原因。
4. 针对失败项回修并复验。

## NEXT_ACTIONS 回写

如果本次验证改变了任务状态、测试结论或下一步建议，同步更新 `docs/NEXT_ACTIONS.zh-CN.md`，再回写对应的开发/测试 backlog。

推荐使用：

```powershell
uv run --project cai-agent python scripts/finalize_task.py --task-id <ID> --summary "<完成内容>" --verification "<验证命令: PASS>"
```
