from __future__ import annotations

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict

from cai_agent.agent_registry import list_agent_names
from cai_agent.config import Settings
from cai_agent.agents import create_agent
from cai_agent.graph import build_app, initial_state
from cai_agent.llm import get_usage_counters, reset_usage_counters
from cai_agent.memory import (
    extract_basic_instincts_from_session,
    save_instincts,
)
from cai_agent.quality_gate import run_quality_gate
from cai_agent.task_state import new_task

ROLE_RANK = {"default": 1, "explorer": 2, "reviewer": 3, "security": 4}

# ---------------------------------------------------------------------------
# RPC 标准 IO schema（§23 补齐）
# 子代理之间的标准化请求/响应结构，供编排器与子代理通信时引用。
# ---------------------------------------------------------------------------

class RpcStepInput(TypedDict, total=False):
    """子代理 RPC 输入载荷（schema_version=rpc_step_input_v1）。"""
    schema_version: str         # 固定 "rpc_step_input_v1"
    task_id: str                # 父任务 ID（由编排器注入）
    workflow_task_id: str       # workflow 级 task_id
    step_index: int             # 本步骤在 workflow 中的序号（1-based）
    name: str                   # 步骤名称
    goal: str                   # 执行目标
    role: str                   # agent 角色：default / explorer / reviewer / security
    parallel_group: Optional[str]  # 并行组名称（无并行时为 None）
    workspace: str              # 执行工作区绝对路径
    model: Optional[str]        # 覆盖模型（None 表示使用全局配置）
    context: dict               # 上游步骤输出摘要，key=step_name, value=answer[:500]
    budget_remaining_tokens: Optional[int]  # 剩余预算（None 表示无限制）


class RpcStepOutput(TypedDict, total=False):
    """子代理 RPC 输出载荷（schema_version=rpc_step_output_v1）。"""
    schema_version: str         # 固定 "rpc_step_output_v1"
    task_id: str
    step_index: int
    name: str
    ok: bool                    # 步骤是否成功完成
    answer: str                 # 步骤产出的最终答案
    error: Optional[str]        # 错误描述（ok=False 时填写）
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    elapsed_ms: int
    tool_calls_count: int
    used_tools: list            # 实际调用的工具名列表
    protocol: dict              # 原始 protocol 字段（input/output/error）


def build_rpc_step_input(
    *,
    task_id: str,
    workflow_task_id: str,
    step_index: int,
    name: str,
    goal: str,
    role: str = "default",
    parallel_group: Optional[str] = None,
    workspace: str,
    model: Optional[str] = None,
    upstream_results: Optional[List[Dict[str, Any]]] = None,
    budget_remaining_tokens: Optional[int] = None,
) -> RpcStepInput:
    """构造标准化 RPC 输入载荷，供编排器传给子代理。"""
    context: dict[str, str] = {}
    if upstream_results:
        for r in upstream_results:
            n = str(r.get("name") or "")
            a = str(r.get("answer") or "")
            if n:
                context[n] = a[:500]
    return RpcStepInput(
        schema_version="rpc_step_input_v1",
        task_id=task_id,
        workflow_task_id=workflow_task_id,
        step_index=step_index,
        name=name,
        goal=goal,
        role=role,
        parallel_group=parallel_group,
        workspace=workspace,
        model=model,
        context=context,
        budget_remaining_tokens=budget_remaining_tokens,
    )


def build_rpc_step_output(step_result: Dict[str, Any]) -> RpcStepOutput:
    """从 `_run_single_step` 的结果构造标准化 RPC 输出载荷。"""
    ok = bool(step_result.get("finished")) and int(step_result.get("error_count") or 0) == 0
    return RpcStepOutput(
        schema_version="rpc_step_output_v1",
        task_id=str(step_result.get("task_id") or ""),
        step_index=int(step_result.get("index") or 0),
        name=str(step_result.get("name") or ""),
        ok=ok,
        answer=str(step_result.get("answer") or ""),
        error=(
            None if ok
            else str((step_result.get("protocol") or {}).get("error") or "unknown_error")
        ),
        prompt_tokens=int(step_result.get("prompt_tokens") or 0),
        completion_tokens=int(step_result.get("completion_tokens") or 0),
        total_tokens=int(step_result.get("total_tokens") or 0),
        elapsed_ms=int(step_result.get("elapsed_ms") or 0),
        tool_calls_count=int(step_result.get("tool_calls_count") or 0),
        used_tools=list(step_result.get("used_tools") or []),
        protocol=dict(step_result.get("protocol") or {}),
    )


# ---------------------------------------------------------------------------
# 内置 Workflow 模板（§23 补齐：探索-实现-评审 等预设模板）
# ---------------------------------------------------------------------------

_BUILTIN_TEMPLATES: dict[str, dict[str, Any]] = {
    "explore-implement-review": {
        "description": "三阶段经典流程：探索（Explorer）→ 实现（Default）→ 评审（Reviewer）",
        "on_error": "fail_fast",
        "merge_strategy": "role_priority",
        "steps": [
            {
                "name": "explore",
                "role": "explorer",
                "goal": "{{GOAL}} —— 阶段：代码库/需求探索，输出结构摘要与关键文件清单",
            },
            {
                "name": "implement",
                "role": "default",
                "goal": "{{GOAL}} —— 阶段：根据探索结果实现功能，输出完整可运行代码",
            },
            {
                "name": "review",
                "role": "reviewer",
                "goal": "{{GOAL}} —— 阶段：对 implement 步骤的输出进行代码评审，给出 LGTM 或改进建议",
            },
        ],
    },
    "security-audit": {
        "description": "安全专项：探索攻击面 → 扫描漏洞 → 给出修复建议",
        "on_error": "continue_on_error",
        "merge_strategy": "last_wins",
        "steps": [
            {
                "name": "attack-surface",
                "role": "security",
                "goal": "{{GOAL}} —— 阶段：梳理攻击面，列出高风险入口",
            },
            {
                "name": "scan",
                "role": "security",
                "goal": "{{GOAL}} —— 阶段：扫描已知漏洞模式（XSS/SQLi/SSRF/secret 泄漏等）",
            },
            {
                "name": "remediation",
                "role": "reviewer",
                "goal": "{{GOAL}} —— 阶段：针对扫描结果给出具体修复方案与优先级建议",
            },
        ],
    },
    "parallel-research": {
        "description": "并行研究：多个探索子代理同时工作，汇总为统一报告",
        "on_error": "continue_on_error",
        "merge_strategy": "role_priority",
        "steps": [
            {
                "name": "research-a",
                "role": "explorer",
                "parallel_group": "research",
                "goal": "{{GOAL}} —— 方向 A：调研现有解决方案与最佳实践",
            },
            {
                "name": "research-b",
                "role": "explorer",
                "parallel_group": "research",
                "goal": "{{GOAL}} —— 方向 B：分析当前代码库的相关实现",
            },
            {
                "name": "synthesize",
                "role": "reviewer",
                "goal": "{{GOAL}} —— 汇总：将 research-a 与 research-b 的输出整合为统一方案",
            },
        ],
    },
}


def list_workflow_templates() -> list[dict[str, Any]]:
    """列出所有内置 workflow 模板的元信息（不含 steps 详情）。"""
    return [
        {"id": tid, "description": tpl["description"]}
        for tid, tpl in _BUILTIN_TEMPLATES.items()
    ]


def get_workflow_template(template_id: str, *, goal: str = "") -> dict[str, Any]:
    """获取指定内置模板并将 ``{{GOAL}}`` 替换为实际目标字符串。

    Returns:
        完整 workflow JSON 字典（可直接序列化后传给 `run_workflow`）。

    Raises:
        KeyError: template_id 不存在时抛出。
    """
    if template_id not in _BUILTIN_TEMPLATES:
        available = ", ".join(_BUILTIN_TEMPLATES.keys())
        raise KeyError(f"未知模板 '{template_id}'，可用：{available}")
    import copy
    tpl = copy.deepcopy(_BUILTIN_TEMPLATES[template_id])
    if goal:
        raw = json.dumps(tpl, ensure_ascii=False)
        raw = raw.replace("{{GOAL}}", goal.replace('"', '\\"'))
        tpl = json.loads(raw)
    return tpl


def _normalize_on_error(data: Dict[str, Any]) -> str:
    """Root `on_error`: fail_fast（默认）| continue_on_error（Hermes S5-03）。"""
    raw = data.get("on_error", "fail_fast")
    s = str(raw).strip().lower().replace("-", "_")
    if s in ("failfast", "fail_fast", ""):
        return "fail_fast"
    if s in ("continue_on_error", "continueonerror"):
        return "continue_on_error"
    return "fail_fast"


def _step_execution_failed(step: Dict[str, Any]) -> bool:
    """步骤已实际执行且视为失败（用于 fail_fast 判定）；不含 skip 占位。"""
    if step.get("skipped"):
        return False
    if int(step.get("error_count") or 0) > 0:
        return True
    return not bool(step.get("finished"))


def _step_ok_for_merge(step: Dict[str, Any]) -> bool:
    """参与 merge / conflict 检测的成功步骤（跳过与执行失败均排除）。"""
    if step.get("skipped"):
        return False
    if int(step.get("error_count") or 0) > 0:
        return False
    return bool(step.get("finished"))


def _parse_budget_max_tokens(data: Dict[str, Any]) -> int | None:
    """根级 `budget_max_tokens`（S5-04）：非负整数有效，否则视为未配置。"""
    raw = data.get("budget_max_tokens")
    if raw is None:
        return None
    try:
        n = int(raw)
    except (TypeError, ValueError):
        return None
    if n < 0:
        return None
    return n


def _parse_workflow_quality_gate(data: Dict[str, Any]) -> dict[str, Any]:
    """解析 root `quality_gate`（后置质量门禁硬联动）。"""
    raw = data.get("quality_gate")
    parsed = {
        "requested": False,
        "compile": None,
        "test": None,
        "lint": None,
        "typecheck": None,
        "security_scan": None,
        "report_dir": None,
    }
    if raw in (None, False):
        return parsed
    if raw is True:
        parsed["requested"] = True
        return parsed
    if not isinstance(raw, dict):
        return parsed
    if raw.get("enabled") is False:
        return parsed
    parsed["requested"] = True
    for key in ("compile", "test", "lint", "typecheck", "security_scan"):
        if isinstance(raw.get(key), bool):
            parsed[key] = bool(raw.get(key))
    report_dir = raw.get("report_dir")
    if isinstance(report_dir, str) and report_dir.strip():
        parsed["report_dir"] = report_dir.strip()
    return parsed


def _parse_retry_max_attempts(raw_step: dict[str, Any]) -> int:
    raw = raw_step.get("retry")
    if isinstance(raw, dict):
        cand = raw.get("max_attempts", raw.get("attempts", raw.get("max_retries")))
    else:
        cand = raw_step.get("max_attempts", raw_step.get("max_retries"))
    try:
        n = int(cand)
    except (TypeError, ValueError):
        return 1
    return max(1, min(n, 5))


def _step_matches_condition(results: List[Dict[str, Any]], condition: Any) -> tuple[bool, str | None]:
    if condition in (None, True):
        return True, None
    if condition is False:
        return False, "when_false"
    if not isinstance(condition, dict):
        return True, None
    dep_name = str(condition.get("step") or condition.get("name") or "").strip()
    if not dep_name:
        return True, None
    matches = [r for r in results if str(r.get("name") or "") == dep_name]
    if not matches:
        return False, "when_dependency_missing"
    dep = matches[-1]
    if dep.get("skipped"):
        dep_state = "skipped"
    elif _step_execution_failed(dep):
        dep_state = "failed"
    else:
        dep_state = "ok"
    expected = str(condition.get("status") or condition.get("state") or "ok").strip().lower()
    if expected in ("success", "succeeded", "completed", "pass"):
        expected = "ok"
    if expected in ("error", "failure"):
        expected = "failed"
    return dep_state == expected, None if dep_state == expected else "when_condition_false"


def _build_workflow_aggregate(results: List[Dict[str, Any]], *, enabled: bool) -> dict[str, Any] | None:
    if not enabled:
        return None
    successful = [r for r in results if _step_ok_for_merge(r)]
    failed = [r for r in results if _step_execution_failed(r)]
    skipped = [r for r in results if r.get("skipped")]
    return {
        "schema_version": "workflow_aggregate_v1",
        "strategy": "answers_by_name",
        "steps_total": len(results),
        "steps_ok": len(successful),
        "steps_failed": len(failed),
        "steps_skipped": len(skipped),
        "answers_by_name": {
            str(r.get("name") or ""): str(r.get("answer") or "")
            for r in successful
            if str(r.get("name") or "").strip()
        },
        "failed_steps": [
            {
                "name": str(r.get("name") or ""),
                "error": (
                    str((r.get("protocol") or {}).get("error"))
                    if isinstance(r.get("protocol"), dict)
                    and (r.get("protocol") or {}).get("error") is not None
                    else "step_failed"
                ),
            }
            for r in failed
        ],
        "skipped_steps": [
            {"name": str(r.get("name") or ""), "reason": str(r.get("skip_reason") or "")}
            for r in skipped
        ],
    }


def _resolve_report_dir(base_dir: str, report_dir: Any) -> str | None:
    """将 quality_gate.report_dir 解析为绝对路径；相对路径相对 workflow 文件目录。"""
    if not isinstance(report_dir, str) or not report_dir.strip():
        return None
    p = Path(report_dir.strip()).expanduser()
    if not p.is_absolute():
        p = Path(base_dir).resolve() / p
    return str(p.resolve())


def _tokens_used_executed(results: List[Dict[str, Any]]) -> int:
    return sum(int(r.get("total_tokens") or 0) for r in results if not r.get("skipped"))


def _append_workflow_skipped_range(
    settings: Settings,
    steps_data: List[Any],
    start_idx: int,
    end_idx: int,
    *,
    reason: str,
    results: List[Dict[str, Any]],
    events: List[Dict[str, Any]],
    wf_task: Any,
) -> None:
    """为 [start_idx, end_idx]（1-based 下标，含端点）写入 skipped 占位与事件。"""
    for j in range(start_idx, end_idx + 1):
        raw_skip = steps_data[j - 1]
        if not isinstance(raw_skip, dict):
            raise ValueError(f"workflow.steps[{j - 1}] 必须是 JSON object")
        sk = _skipped_step_stub(settings, j, raw_skip, reason=reason)
        results.append(sk)
        events.append(
            {
                "event": "workflow.step.skipped",
                "task_id": wf_task.task_id,
                "workflow_task_id": wf_task.task_id,
                "step_index": j,
                "name": sk.get("name"),
                "parallel_group": sk.get("parallel_group"),
                "reason": reason,
            },
        )


def _skipped_step_stub(
    settings: Settings,
    idx: int,
    raw_step: dict[str, Any],
    *,
    reason: str,
) -> dict[str, Any]:
    """未运行步骤占位（fail_fast / budget 等），便于与 workflow.steps 对齐。"""
    goal = str(raw_step.get("goal", "")).strip()
    name = str(raw_step.get("name") or f"step-{idx}").strip()
    ws_raw = raw_step.get("workspace")
    if isinstance(ws_raw, str) and ws_raw.strip():
        workspace = os.path.abspath(ws_raw.strip())
    else:
        workspace = settings.workspace
    pg_raw = raw_step.get("parallel_group")
    parallel_group = str(pg_raw).strip() if isinstance(pg_raw, str) and pg_raw.strip() else None
    role_raw = str(raw_step.get("role") or "default").strip().lower()
    if role_raw not in ("default", "explorer", "reviewer", "security"):
        role_raw = "default"
    return {
        "index": idx,
        "name": name,
        "goal": goal,
        "workspace": workspace,
        "provider": settings.provider,
        "model": settings.model,
        "elapsed_ms": 0,
        "answer": "",
        "finished": False,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "tool_calls_count": 0,
        "used_tools": [],
        "error_count": 0,
        "role": role_raw,
        "parallel_group": parallel_group,
        "attempts": 0,
        "skipped": True,
        "skip_reason": reason,
        "protocol": {
            "input": {
                "goal": goal,
                "role": role_raw,
                "parallel_group": parallel_group,
            },
            "output": {"answer": ""},
            "error": None,
        },
    }


def _load_workflow_file(path: str) -> Dict[str, Any]:
    p = Path(path).expanduser().resolve()
    if not p.is_file():
        msg = f"workflow 文件不存在: {p}"
        raise FileNotFoundError(msg)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        msg = f"解析 workflow JSON 失败: {e}"
        raise ValueError(msg) from e
    if not isinstance(data, dict):
        raise ValueError("workflow 根对象必须是 JSON object")
    steps = data.get("steps")
    if not isinstance(steps, list) or not steps:
        raise ValueError("workflow.steps 必须是非空数组")
    return data


def _collect_tool_stats(messages: List[Dict[str, Any]]) -> Dict[str, Any]:
    names: List[str] = []
    errors = 0
    for m in messages:
        if m.get("role") != "user":
            continue
        content = m.get("content")
        if not isinstance(content, str):
            continue
        try:
            obj = json.loads(content)
        except Exception:
            continue
        if not isinstance(obj, dict):
            continue
        tn = obj.get("tool")
        if isinstance(tn, str) and tn.strip():
            names.append(tn.strip())
            result = obj.get("result")
            if isinstance(result, str):
                r = result.lower()
                if (
                    "失败" in result
                    or "error" in r
                    or "exception" in r
                    or "traceback" in r
                ):
                    errors += 1
    uniq = sorted(set(names))
    return {
        "tool_calls_count": len(names),
        "used_tools": uniq,
        "error_count": errors,
    }


def _detect_conflicts(results: List[Dict[str, Any]]) -> list[dict[str, Any]]:
    by_name: dict[str, str] = {}
    conflicts: list[dict[str, Any]] = []
    for r in results:
        n = str(r.get("name", ""))
        a = str(r.get("answer", "")).strip()
        if not n:
            continue
        prev = by_name.get(n)
        if prev is None:
            by_name[n] = a
        elif prev != a:
            conflicts.append({"name": n, "type": "answer_mismatch"})
    return conflicts


def _answers_by_name(results: List[Dict[str, Any]]) -> dict[str, list[tuple[str, str, int]]]:
    """name -> [(answer, role, index), ...] 按步骤顺序."""
    m: dict[str, list[tuple[str, str, int]]] = {}
    for r in results:
        n = str(r.get("name", "")).strip()
        if not n:
            continue
        a = str(r.get("answer", "")).strip()
        role = str(r.get("role") or "default").strip().lower()
        idx = int(r.get("index") or 0)
        m.setdefault(n, []).append((a, role, idx))
    return m


def _merge_decision_for_strategy(
    strategy: str,
    conflicts: list[dict[str, Any]],
    results: List[Dict[str, Any]],
) -> str:
    if not conflicts:
        return "auto_merge"
    s = strategy.strip().lower()
    if s == "last_wins":
        return "last_wins"
    if s == "role_priority":
        by_n = _answers_by_name(results)
        for c in conflicts:
            name = str(c.get("name", ""))
            lst = by_n.get(name) or []
            scores: dict[str, int] = {}
            for ans, role, _ in lst:
                rk = ROLE_RANK.get(role, 1)
                scores[ans] = max(scores.get(ans, 0), rk)
            if len(scores) < 2:
                continue
            mx = max(scores.values())
            tops = [a for a, sc in scores.items() if sc == mx]
            if len(tops) != 1:
                return "manual_review_role_tie"
        return "role_priority"
    return "manual_review"


def _merge_confidence(
    merge_decision: str,
    conflicts_count: int,
    *,
    total_steps: int,
) -> str:
    if merge_decision == "auto_merge" and conflicts_count == 0:
        return "high"
    if merge_decision in ("last_wins", "role_priority") and conflicts_count <= max(1, total_steps // 3):
        return "medium"
    return "low"


def _build_subagent_io_summary(
    *,
    settings: Settings,
    steps: list[dict[str, Any]],
    merge_strategy: str,
    merge_decision: str,
    merge_confidence: str,
    conflicts: list[dict[str, Any]],
) -> dict[str, Any]:
    """标准化 workflow 输出为可被子代理编排消费的稳定 I/O schema。"""
    catalog = [str(x).strip() for x in list_agent_names(settings) if str(x).strip()]
    catalog_set = frozenset(catalog)
    outputs: list[dict[str, Any]] = []
    for step in steps:
        nm = str(step.get("name") or "").strip()
        agent_key = str(step.get("agent") or "").strip() or None
        tpl_id = agent_key if agent_key and agent_key in catalog_set else (
            nm if nm in catalog_set else None
        )
        rpc_in: dict[str, Any] | None = None
        rpc_out: dict[str, Any] | None = None
        prot = step.get("protocol")
        if isinstance(prot, dict):
            maybe_in = prot.get("rpc_input")
            maybe_out = prot.get("rpc_output")
            if isinstance(maybe_in, dict):
                rpc_in = maybe_in
            if isinstance(maybe_out, dict):
                rpc_out = maybe_out
        outputs.append(
            {
                "id": str(step.get("index") or ""),
                "name": nm,
                "role": str(step.get("role") or "default"),
                "agent_template_id": tpl_id,
                "rpc_step_input": rpc_in,
                "rpc_step_output": rpc_out,
                "ok": (not step.get("skipped"))
                and bool(step.get("finished"))
                and int(step.get("error_count") or 0) == 0,
                "answer": str(step.get("answer") or ""),
                "error": (
                    str((step.get("protocol") or {}).get("error"))
                    if isinstance(step.get("protocol"), dict)
                    and (step.get("protocol") or {}).get("error") is not None
                    else None
                ),
                "parallel_group": step.get("parallel_group"),
            },
        )
    return {
        "subagent_io_schema_version": "1.1",
        "inputs": {
            "steps_count": len(steps),
            "merge_strategy": merge_strategy,
            "agent_templates": [{"id": x} for x in catalog],
        },
        "merge": {
            "strategy": merge_strategy,
            "decision": merge_decision,
            "confidence": merge_confidence,
            "conflicts": conflicts,
        },
        "outputs": outputs,
    }


def _run_single_step(
    settings: Settings,
    raw_step: dict[str, Any],
    idx: int,
) -> tuple[dict[str, Any], dict[str, Any], str]:
    goal = str(raw_step.get("goal", "")).strip()
    if not goal:
        raise ValueError(f"workflow.steps[{idx - 1}] 缺少非空 goal")
    name = str(raw_step.get("name") or f"step-{idx}").strip()

    ws_raw = raw_step.get("workspace")
    if isinstance(ws_raw, str) and ws_raw.strip():
        workspace = os.path.abspath(ws_raw.strip())
    else:
        workspace = settings.workspace

    step_settings = replace(settings, workspace=workspace)
    model_raw = raw_step.get("model")
    if isinstance(model_raw, str) and model_raw.strip():
        step_settings = replace(step_settings, model=model_raw.strip())

    role_raw = str(raw_step.get("role") or "default").strip().lower()
    if role_raw not in ("default", "explorer", "reviewer", "security"):
        role_raw = "default"

    reset_usage_counters()
    agent = create_agent(step_settings, role=role_raw) if role_raw != "default" else None
    started = time.perf_counter()
    if agent is not None:
        final = agent.run(goal)
    else:
        app = build_app(step_settings)
        state = initial_state(step_settings, goal)
        final = app.invoke(state)
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    usage = get_usage_counters()

    msgs = final.get("messages")
    msg_list: List[Dict[str, Any]] = msgs if isinstance(msgs, list) else []
    stats = _collect_tool_stats(msg_list)
    pg_raw = raw_step.get("parallel_group")
    parallel_group = str(pg_raw).strip() if isinstance(pg_raw, str) and pg_raw.strip() else None

    step_result: Dict[str, Any] = {
        "index": idx,
        "name": name,
        "goal": goal,
        "workspace": step_settings.workspace,
        "provider": step_settings.provider,
        "model": step_settings.model,
        "elapsed_ms": elapsed_ms,
        "answer": (final.get("answer") or "").strip(),
        "finished": bool(final.get("finished")),
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0),
        "total_tokens": usage.get("total_tokens", 0),
        **stats,
        "role": role_raw,
        "parallel_group": parallel_group,
        "protocol": {
            "input": {"goal": goal, "role": role_raw, "parallel_group": parallel_group},
            "output": {"answer": (final.get("answer") or "").strip()},
            "error": None if int(stats.get("error_count", 0)) == 0 else "tool_error_detected",
        },
    }
    step_event = {
        "event": "workflow.step.completed",
        "step_index": idx,
        "name": name,
        "elapsed_ms": elapsed_ms,
        "tool_calls_count": int(stats.get("tool_calls_count", 0)),
        "error_count": int(stats.get("error_count", 0)),
        "parallel_group": parallel_group,
    }
    return step_result, step_event, step_settings.workspace


def _run_step_with_retries(
    settings: Settings,
    raw_step: dict[str, Any],
    idx: int,
) -> tuple[dict[str, Any], dict[str, Any], str, list[dict[str, Any]]]:
    max_attempts = _parse_retry_max_attempts(raw_step)
    retry_events: list[dict[str, Any]] = []
    last: tuple[dict[str, Any], dict[str, Any], str] | None = None
    for attempt in range(1, max_attempts + 1):
        step_result, step_event, workspace = _run_single_step(settings, raw_step, idx)
        step_result["attempts"] = attempt
        step_result["max_attempts"] = max_attempts
        step_event["attempt"] = attempt
        step_event["max_attempts"] = max_attempts
        last = (step_result, step_event, workspace)
        if not _step_execution_failed(step_result):
            return step_result, step_event, workspace, retry_events
        if attempt < max_attempts:
            retry_events.append(
                {
                    "event": "workflow.step.retrying",
                    "step_index": idx,
                    "name": step_result.get("name"),
                    "attempt": attempt,
                    "max_attempts": max_attempts,
                    "error": (
                        (step_result.get("protocol") or {}).get("error")
                        if isinstance(step_result.get("protocol"), dict)
                        else None
                    ),
                },
            )
    assert last is not None
    step_result, step_event, workspace = last
    return step_result, step_event, workspace, retry_events


def run_workflow(settings: Settings, path: str) -> Dict[str, Any]:
    """
    运行基于 JSON 描述的多步骤 workflow。

    JSON 结构示例：
    {
      "on_error": "fail_fast",
      "merge_strategy": "require_manual",
      "steps": [
        {"name": "analyze", "goal": "分析当前项目结构"},
        {"name": "plan", "goal": "为登录功能生成实现计划", "workspace": ".", "model": "gpt-4o-mini"}
      ]
    }

    `on_error`（Hermes S5-03）：`fail_fast`（默认）表示任一步骤执行失败则中止后续步骤并写入
    `skipped` 占位；`continue_on_error` 则跑完全部步骤，且 merge/conflict 仅统计成功完成的步骤。

    `budget_max_tokens`（Hermes S5-04，可选）：已执行步骤的 **`total_tokens`** 累计值在**下一批**
    开始前若 **≥** 预算，则本批及之后未启动步骤全部 **`skipped`**（`skip_reason=budget_exceeded`）；
    本批已启动的并行组仍会跑完（已运行结果保留）。`summary` / `workflow.finished` 含 **`budget_used`** /
    **`budget_limit`** / **`budget_exceeded`**。

    `quality_gate`（后续增量补齐）：root 可选 `true` 或对象；当 workflow 本身先成功完成时，
    自动执行一次后置 `quality-gate`。对象可覆盖 `compile` / `test` / `lint` / `typecheck` /
    `security_scan` / `report_dir`；若 gate 失败，workflow 最终标记为 failed，并在输出中附带
    `quality_gate` 摘要与 `post_gate` 详细结果。
    """
    wf_task = new_task("workflow")
    wf_task.status = "running"
    events: List[Dict[str, Any]] = []
    wf_path = Path(path).expanduser().resolve()
    data = _load_workflow_file(str(wf_path))
    steps_data = data["steps"]
    on_error = _normalize_on_error(data)
    merge_strategy = str(data.get("merge_strategy", "require_manual")).strip().lower()
    if merge_strategy not in ("require_manual", "last_wins", "role_priority"):
        merge_strategy = "require_manual"
    budget_max = _parse_budget_max_tokens(data)
    quality_gate_cfg = _parse_workflow_quality_gate(data)
    aggregate_enabled = bool(data.get("aggregate") or data.get("aggregates"))

    results: List[Dict[str, Any]] = []
    total_elapsed = 0
    total_tool_calls = 0
    total_errors = 0

    instincts_roots: set[str] = set()

    idx = 1
    while idx <= len(steps_data):
        raw_step = steps_data[idx - 1]
        if not isinstance(raw_step, dict):
            raise ValueError(f"workflow.steps[{idx - 1}] 必须是 JSON object")
        pg_raw = raw_step.get("parallel_group")
        parallel_group = str(pg_raw).strip() if isinstance(pg_raw, str) and pg_raw.strip() else None
        batch: list[tuple[int, dict[str, Any]]] = [(idx, raw_step)]
        if parallel_group is not None:
            j = idx + 1
            while j <= len(steps_data):
                cand = steps_data[j - 1]
                if not isinstance(cand, dict):
                    raise ValueError(f"workflow.steps[{j - 1}] 必须是 JSON object")
                cpg = cand.get("parallel_group")
                cpg_name = str(cpg).strip() if isinstance(cpg, str) and cpg.strip() else None
                if cpg_name != parallel_group:
                    break
                batch.append((j, cand))
                j += 1

        next_idx = idx + len(batch)

        if budget_max is not None and _tokens_used_executed(results) >= budget_max:
            _append_workflow_skipped_range(
                settings,
                steps_data,
                idx,
                len(steps_data),
                reason="budget_exceeded",
                results=results,
                events=events,
                wf_task=wf_task,
            )
            break

        skipped_for_condition = False
        for bi, br in batch:
            ok_when, reason = _step_matches_condition(results, br.get("when"))
            if ok_when:
                continue
            _append_workflow_skipped_range(
                settings,
                steps_data,
                bi,
                bi,
                reason=reason or "when_condition_false",
                results=results,
                events=events,
                wf_task=wf_task,
            )
            skipped_for_condition = True
        if skipped_for_condition:
            idx = next_idx
            continue

        for bi, br in batch:
            bname = str(br.get("name") or f"step-{bi}").strip()
            events.append(
                {
                    "event": "workflow.step.started",
                    "task_id": wf_task.task_id,
                    "workflow_task_id": wf_task.task_id,
                    "step_index": bi,
                    "name": bname,
                    "parallel_group": parallel_group,
                },
            )

        batch_results: list[tuple[dict[str, Any], dict[str, Any], str, list[dict[str, Any]]]] = []
        if parallel_group is not None and len(batch) > 1:
            with ThreadPoolExecutor(max_workers=len(batch)) as pool:
                futs = {
                    pool.submit(_run_step_with_retries, settings, br, bi): bi
                    for bi, br in batch
                }
                for fut in as_completed(futs):
                    batch_results.append(fut.result())
        else:
            for bi, br in batch:
                batch_results.append(_run_step_with_retries(settings, br, bi))

        batch_results.sort(key=lambda x: int((x[0].get("index") or 0)))
        for step_result, step_event, workspace, retry_events in batch_results:
            for retry_event in retry_events:
                retry_event["task_id"] = wf_task.task_id
                retry_event["workflow_task_id"] = wf_task.task_id
                events.append(retry_event)
            results.append(step_result)
            step_event["task_id"] = wf_task.task_id
            step_event["workflow_task_id"] = wf_task.task_id
            events.append(step_event)
            total_elapsed += int(step_result.get("elapsed_ms") or 0)
            total_tool_calls += int(step_result.get("tool_calls_count") or 0)
            total_errors += int(step_result.get("error_count") or 0)
            instincts_roots.add(workspace)

        batch_failed = any(
            _step_execution_failed(sr) for sr, _, _, _ in batch_results
        )
        if on_error == "fail_fast" and batch_failed:
            _append_workflow_skipped_range(
                settings,
                steps_data,
                next_idx,
                len(steps_data),
                reason="fail_fast_prior_batch",
                results=results,
                events=events,
                wf_task=wf_task,
            )
            break

        if budget_max is not None and _tokens_used_executed(results) >= budget_max:
            _append_workflow_skipped_range(
                settings,
                steps_data,
                next_idx,
                len(steps_data),
                reason="budget_exceeded",
                results=results,
                events=events,
                wf_task=wf_task,
            )
            break

        idx = next_idx

    merge_inputs = [r for r in results if _step_ok_for_merge(r)]
    conflicts = _detect_conflicts(merge_inputs)
    merge_decision = _merge_decision_for_strategy(merge_strategy, conflicts, merge_inputs)

    skipped_count = sum(1 for r in results if r.get("skipped"))
    tok_used = _tokens_used_executed(results)
    budget_exceeded = budget_max is not None and (
        tok_used > budget_max
        or any(str(r.get("skip_reason") or "") == "budget_exceeded" for r in results)
    )
    fail_fast_tail = on_error == "fail_fast" and any(
        str(r.get("skip_reason") or "") == "fail_fast_prior_batch" for r in results
    )
    ran_failed = any(_step_execution_failed(r) for r in results)
    pre_gate_failed = fail_fast_tail or total_errors > 0 or ran_failed or budget_exceeded
    post_gate: Dict[str, Any] | None = None
    quality_gate_summary: dict[str, Any] = {
        "requested": bool(quality_gate_cfg.get("requested")),
        "ran": False,
        "ok": None,
        "failed_count": None,
        "skip_reason": None,
        "report_dir": _resolve_report_dir(str(wf_path.parent), quality_gate_cfg.get("report_dir")),
    }
    if quality_gate_summary["requested"]:
        if pre_gate_failed:
            quality_gate_summary["skip_reason"] = "workflow_failed"
            events.append(
                {
                    "event": "workflow.quality_gate.skipped",
                    "task_id": wf_task.task_id,
                    "workflow_task_id": wf_task.task_id,
                    "reason": "workflow_failed",
                },
            )
        elif not any(not r.get("skipped") for r in results):
            quality_gate_summary["skip_reason"] = "no_executed_steps"
            events.append(
                {
                    "event": "workflow.quality_gate.skipped",
                    "task_id": wf_task.task_id,
                    "workflow_task_id": wf_task.task_id,
                    "reason": "no_executed_steps",
                },
            )
        else:
            post_gate = run_quality_gate(
                settings,
                enable_compile=(
                    settings.quality_gate_compile
                    if quality_gate_cfg.get("compile") is None
                    else bool(quality_gate_cfg.get("compile"))
                ),
                enable_test=(
                    settings.quality_gate_test
                    if quality_gate_cfg.get("test") is None
                    else bool(quality_gate_cfg.get("test"))
                ),
                enable_lint=(
                    settings.quality_gate_lint
                    if quality_gate_cfg.get("lint") is None
                    else bool(quality_gate_cfg.get("lint"))
                ),
                enable_typecheck=(
                    settings.quality_gate_typecheck
                    if quality_gate_cfg.get("typecheck") is None
                    else bool(quality_gate_cfg.get("typecheck"))
                ),
                enable_security_scan=(
                    settings.quality_gate_security_scan
                    if quality_gate_cfg.get("security_scan") is None
                    else bool(quality_gate_cfg.get("security_scan"))
                ),
                report_dir=quality_gate_summary["report_dir"],
            )
            quality_gate_summary.update(
                {
                    "ran": True,
                    "ok": bool(post_gate.get("ok")),
                    "failed_count": int(post_gate.get("failed_count", 0) or 0),
                },
            )
            events.append(
                {
                    "event": "workflow.quality_gate.completed",
                    "task_id": wf_task.task_id,
                    "workflow_task_id": wf_task.task_id,
                    "ok": bool(post_gate.get("ok")),
                    "failed_count": int(post_gate.get("failed_count", 0) or 0),
                    "report_dir": quality_gate_summary["report_dir"],
                },
            )
    summary = {
        "steps_count": len(results),
        "parallel_steps_count": sum(
            1
            for r in results
            if isinstance(r.get("parallel_group"), str) and str(r.get("parallel_group")).strip()
        ),
        "parallel_groups_count": len(
            {
                str(r.get("parallel_group"))
                for r in results
                if isinstance(r.get("parallel_group"), str) and str(r.get("parallel_group")).strip()
            },
        ),
        "elapsed_ms_total": total_elapsed,
        "elapsed_ms_avg": int(total_elapsed / len(results)) if results else 0,
        "tool_calls_total": total_tool_calls,
        "tool_errors_total": total_errors,
        "conflicts": conflicts,
        "merge_decision": merge_decision,
        "merge_confidence": _merge_confidence(
            merge_decision,
            len(conflicts),
            total_steps=max(len(results), 1),
        ),
        "merge_strategy": merge_strategy,
        "on_error": on_error,
        "steps_skipped": skipped_count,
        "merge_steps_considered": len(merge_inputs),
        "budget_limit": budget_max,
        "budget_used": tok_used,
        "budget_exceeded": budget_exceeded,
        "quality_gate_requested": bool(quality_gate_summary["requested"]),
        "quality_gate_ran": bool(quality_gate_summary["ran"]),
        "quality_gate_ok": quality_gate_summary["ok"],
        "quality_gate_failed_count": quality_gate_summary["failed_count"],
        "quality_gate_skip_reason": quality_gate_summary["skip_reason"],
    }
    aggregate = _build_workflow_aggregate(results, enabled=aggregate_enabled)
    subagent_io = _build_subagent_io_summary(
        settings=settings,
        steps=results,
        merge_strategy=merge_strategy,
        merge_decision=merge_decision,
        merge_confidence=str(summary.get("merge_confidence") or "low"),
        conflicts=conflicts,
    )

    try:
        if instincts_roots:
            ran_only = [r for r in results if not r.get("skipped")]
            sess_like = {
                "goal": " ; ".join(str(r.get("goal", "")) for r in ran_only),
                "answer": "\n\n".join(str(r.get("answer", "")) for r in ran_only),
            }
            instincts = extract_basic_instincts_from_session(sess_like)
            for root in instincts_roots:
                save_instincts(root, instincts)
    except Exception:
        pass

    wf_task.ended_at = time.time()
    wf_task.elapsed_ms = int((wf_task.ended_at - wf_task.started_at) * 1000)
    if fail_fast_tail:
        wf_task.status = "failed"
        wf_task.error = "workflow_fail_fast"
    elif total_errors > 0 or ran_failed:
        wf_task.status = "failed"
        wf_task.error = "workflow_has_step_errors"
    elif budget_exceeded:
        wf_task.status = "failed"
        wf_task.error = "workflow_budget_exceeded"
    elif quality_gate_summary["requested"] and quality_gate_summary["ran"] and not quality_gate_summary["ok"]:
        wf_task.status = "failed"
        wf_task.error = "workflow_quality_gate_failed"
    else:
        wf_task.status = "completed"
        wf_task.error = None
    events.append(
        {
            "event": "workflow.finished",
            "task_id": wf_task.task_id,
            "workflow_task_id": wf_task.task_id,
            "steps_count": len(results),
            "merge_decision": merge_decision,
            "merge_strategy": merge_strategy,
            "tool_errors_total": total_errors,
            "on_error": on_error,
            "steps_skipped": skipped_count,
            "budget_limit": budget_max,
            "budget_used": tok_used,
            "budget_exceeded": budget_exceeded,
            "quality_gate_requested": bool(quality_gate_summary["requested"]),
            "quality_gate_ran": bool(quality_gate_summary["ran"]),
            "quality_gate_ok": quality_gate_summary["ok"],
        },
    )
    return {
        "schema_version": "workflow_run_v1",
        "task_id": wf_task.task_id,
        "task": wf_task.to_dict(),
        "subagent_io_schema_version": "1.1",
        "subagent_io": subagent_io,
        "steps": results,
        "summary": summary,
        "aggregate": aggregate,
        "quality_gate": quality_gate_summary,
        "post_gate": post_gate,
        "events": events,
    }
