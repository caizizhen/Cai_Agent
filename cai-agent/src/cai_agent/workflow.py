from __future__ import annotations

import json
import os
import time
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, List

from cai_agent.config import Settings
from cai_agent.agents import create_agent
from cai_agent.graph import build_app, initial_state
from cai_agent.llm import get_usage_counters, reset_usage_counters
from cai_agent.memory import (
    extract_basic_instincts_from_session,
    save_instincts,
)
from cai_agent.task_state import new_task

ROLE_RANK = {"default": 1, "explorer": 2, "reviewer": 3, "security": 4}


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


def run_workflow(settings: Settings, path: str) -> Dict[str, Any]:
    """
    运行基于 JSON 描述的多步骤 workflow。

    JSON 结构示例：
    {
      "merge_strategy": "require_manual",
      "steps": [
        {"name": "analyze", "goal": "分析当前项目结构"},
        {"name": "plan", "goal": "为登录功能生成实现计划", "workspace": ".", "model": "gpt-4o-mini"}
      ]
    }
    """
    wf_task = new_task("workflow")
    wf_task.status = "running"
    events: List[Dict[str, Any]] = []
    data = _load_workflow_file(path)
    steps_data = data["steps"]
    merge_strategy = str(data.get("merge_strategy", "require_manual")).strip().lower()
    if merge_strategy not in ("require_manual", "last_wins", "role_priority"):
        merge_strategy = "require_manual"

    results: List[Dict[str, Any]] = []
    total_elapsed = 0
    total_tool_calls = 0
    total_errors = 0

    instincts_roots: set[str] = set()

    for idx, raw_step in enumerate(steps_data, start=1):
        if not isinstance(raw_step, dict):
            raise ValueError(f"workflow.steps[{idx - 1}] 必须是 JSON object")
        goal = str(raw_step.get("goal", "")).strip()
        if not goal:
            raise ValueError(f"workflow.steps[{idx - 1}] 缺少非空 goal")
        name = str(raw_step.get("name") or f"step-{idx}").strip()

        events.append(
            {
                "event": "workflow.step.started",
                "workflow_task_id": wf_task.task_id,
                "step_index": idx,
                "name": name,
            },
        )

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
            "protocol": {
                "input": {"goal": goal, "role": role_raw},
                "output": {"answer": (final.get("answer") or "").strip()},
                "error": None if int(stats.get("error_count", 0)) == 0 else "tool_error_detected",
            },
        }
        results.append(step_result)

        events.append(
            {
                "event": "workflow.step.completed",
                "workflow_task_id": wf_task.task_id,
                "step_index": idx,
                "name": name,
                "elapsed_ms": elapsed_ms,
                "tool_calls_count": int(stats.get("tool_calls_count", 0)),
                "error_count": int(stats.get("error_count", 0)),
            },
        )

        total_elapsed += elapsed_ms
        total_tool_calls += int(stats.get("tool_calls_count", 0))
        total_errors += int(stats.get("error_count", 0))

        instincts_roots.add(step_settings.workspace)

    conflicts = _detect_conflicts(results)
    merge_decision = _merge_decision_for_strategy(merge_strategy, conflicts, results)

    summary = {
        "steps_count": len(results),
        "elapsed_ms_total": total_elapsed,
        "elapsed_ms_avg": int(total_elapsed / len(results)) if results else 0,
        "tool_calls_total": total_tool_calls,
        "tool_errors_total": total_errors,
        "conflicts": conflicts,
        "merge_decision": merge_decision,
        "merge_strategy": merge_strategy,
    }

    try:
        if instincts_roots:
            sess_like = {
                "goal": " ; ".join(str(r.get("goal", "")) for r in results),
                "answer": "\n\n".join(str(r.get("answer", "")) for r in results),
            }
            instincts = extract_basic_instincts_from_session(sess_like)
            for root in instincts_roots:
                save_instincts(root, instincts)
    except Exception:
        pass

    wf_task.ended_at = time.time()
    wf_task.elapsed_ms = int((wf_task.ended_at - wf_task.started_at) * 1000)
    wf_task.status = "completed" if total_errors == 0 else "failed"
    wf_task.error = None if total_errors == 0 else "workflow_has_step_errors"
    events.append(
        {
            "event": "workflow.finished",
            "workflow_task_id": wf_task.task_id,
            "steps_count": len(results),
            "merge_decision": merge_decision,
            "merge_strategy": merge_strategy,
            "tool_errors_total": total_errors,
        },
    )
    return {
        "task": wf_task.to_dict(),
        "steps": results,
        "summary": summary,
        "events": events,
    }
