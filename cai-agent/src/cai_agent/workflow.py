from __future__ import annotations

import json
import os
import time
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, List

from cai_agent.config import Settings
from cai_agent.graph import build_app, initial_state
from cai_agent.llm import get_usage_counters, reset_usage_counters


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


def run_workflow(settings: Settings, path: str) -> Dict[str, Any]:
    """
    运行基于 JSON 描述的多步骤 workflow。

    JSON 结构示例：
    {
      "steps": [
        {"name": "analyze", "goal": "分析当前项目结构"},
        {"name": "plan", "goal": "为登录功能生成实现计划", "workspace": ".", "model": "gpt-4o-mini"}
      ]
    }
    """
    data = _load_workflow_file(path)
    steps_data = data["steps"]

    results: List[Dict[str, Any]] = []
    total_elapsed = 0
    total_tool_calls = 0
    total_errors = 0

    for idx, raw_step in enumerate(steps_data, start=1):
        if not isinstance(raw_step, dict):
            raise ValueError(f"workflow.steps[{idx - 1}] 必须是 JSON object")
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

        reset_usage_counters()
        app = build_app(step_settings)
        state = initial_state(step_settings, goal)

        started = time.perf_counter()
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
        }
        results.append(step_result)

        total_elapsed += elapsed_ms
        total_tool_calls += int(stats.get("tool_calls_count", 0))
        total_errors += int(stats.get("error_count", 0))

    summary = {
        "steps_count": len(results),
        "elapsed_ms_total": total_elapsed,
        "elapsed_ms_avg": int(total_elapsed / len(results)) if results else 0,
        "tool_calls_total": total_tool_calls,
        "tool_errors_total": total_errors,
    }
    return {"steps": results, "summary": summary}

