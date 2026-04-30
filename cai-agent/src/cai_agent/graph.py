from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, Literal, NotRequired, TypedDict

from langgraph.graph import END, START, StateGraph

from cai_agent.config import Settings
from cai_agent.context_compaction import (
    build_llm_compaction_prompt,
    compact_messages,
    evaluate_compaction_retention,
)
from cai_agent.context import augment_system_prompt
from cai_agent.llm import estimate_tokens_from_messages, extract_json_object, get_last_usage
from cai_agent.llm_factory import chat_completion_by_role, peek_last_profile_route_decision
from cai_agent.progress_ring import global_ring
from cai_agent.tools import dispatch, tools_spec_markdown


def _emit(
    progress: Callable[[dict[str, Any]], None] | None,
    payload: dict[str, Any],
) -> None:
    # 始终写入 global ring（低开销；ring 全局生命周期内自动轮转）
    try:
        global_ring().push(payload)
    except Exception:
        pass
    if not progress:
        return
    try:
        progress(payload)
    except Exception:
        pass


def _args_summary(args: dict[str, Any], limit: int = 120) -> str:
    try:
        s = json.dumps(args, ensure_ascii=False)
    except TypeError:
        s = str(args)
    return s if len(s) <= limit else s[: limit - 1] + "…"


class AgentState(TypedDict, total=False):
    messages: list[dict[str, Any]]
    iteration: int
    pending: dict[str, Any] | None
    finished: bool
    answer: str
    compact_hint_sent: NotRequired[bool]
    # 成功完成的工具轮次数（dispatch 未返回「工具执行失败」前缀）。
    tool_call_count: NotRequired[int]
    # 最近一次注入「工具里程碑」压缩提示时的 tool_call_count。
    compact_milestone_last_tc: NotRequired[int]
    # tools_node 在工具失败时置 True；llm_node 注入一次性收束提示后清 False。
    tool_error_compact_pending: NotRequired[bool]
    # F2 · 仅触发一次的收束提示（与 milestone / iteration 提示互补）。
    compact_pre_retry_sent: NotRequired[bool]
    compact_research_done_sent: NotRequired[bool]
    compact_generation: NotRequired[int]
    compact_last_message_count: NotRequired[int]
    compact_last_prompt_tokens: NotRequired[int]
    compact_summary: NotRequired[str]


def _core_system_prompt(workspace: str) -> str:
    return (
        f"你是 CAI Agent（本地或远程 OpenAI 兼容 API）。工作区根目录（所有相对路径以此为根）:\n{workspace}\n\n"
        "每轮只输出**一个** JSON 对象，不要用 Markdown 代码块包裹以外的多余说明。\n"
        "格式只能是以下之一：\n"
        '1) 结束：{"type":"finish","message":"给用户的最终回答"}\n'
        '2) 调工具：{"type":"tool","name":"工具名","args":{...}}\n\n'
        + tools_spec_markdown()
        + "\n建议：先用 list_tree / list_dir / glob_search / search_text / git_status 了解代码；"
        "如需外部能力可先 mcp_list_tools 再 mcp_call_tool；"
        "若配置已启用 fetch_url，可用 fetch_url 拉取只读网页文本（默认 HTTPS + 主机白名单；unrestricted 时无白名单并允许 http）。"
        "需要空目录时用 make_dir；写文件用 write_file；需要终端命令再用 run_command。"
    )


def build_system_prompt(settings: Settings) -> str:
    return augment_system_prompt(settings, _core_system_prompt(settings.workspace))


def build_app(
    settings: Settings,
    *,
    progress: Callable[[dict[str, Any]], None] | None = None,
    should_stop: Callable[[], bool] | None = None,
    role: str = "active",
):
    """构建主循环图。

    ``role``：调用 LLM 时走 :func:`cai_agent.llm_factory.chat_completion_by_role`
    传入的角色，决定使用 active / subagent / planner 哪一个 profile。
    workflow 的子代理步骤会传 ``role="subagent"``。
    """
    role_name = (role or "active").strip().lower() or "active"
    def _is_stopped() -> bool:
        if not should_stop:
            return False
        try:
            return bool(should_stop())
        except Exception:
            return False

    def llm_node(state: AgentState) -> dict[str, Any]:
        if state.get("finished"):
            return {}
        if _is_stopped():
            _emit(progress, {"phase": "stopped"})
            return {
                "finished": True,
                "answer": "已手动停止本次运行。",
                "pending": None,
                "compact_hint_sent": bool(state.get("compact_hint_sent")),
            }
        messages = list(state["messages"])
        iteration = int(state.get("iteration", 0)) + 1
        if iteration > settings.max_iterations:
            _emit(
                progress,
                {"phase": "limit", "iteration": iteration},
            )
            prev = state.get("answer")
            if isinstance(prev, str) and prev.strip():
                ans = prev
            else:
                ans = "已达到最大推理轮次，已停止。"
            return {
                "iteration": iteration,
                "finished": True,
                "answer": ans,
                "pending": None,
                "compact_hint_sent": bool(state.get("compact_hint_sent")),
            }

        extra_state: dict[str, Any] = {}
        estimated_prompt_tokens = estimate_tokens_from_messages(messages)
        window = int(getattr(settings, "context_window", 0) or 0)
        mode = str(getattr(settings, "context_compact_mode", "heuristic") or "heuristic").strip().lower()
        if mode not in {"off", "heuristic", "llm"}:
            mode = "heuristic"
        ratio = float(getattr(settings, "context_compact_trigger_ratio", 0.85) or 0.0)
        last_compact_count = int(state.get("compact_last_message_count") or 0)
        should_auto_compact = (
            mode != "off"
            and ratio > 0
            and window > 0
            and estimated_prompt_tokens >= int(window * ratio)
            and len(messages) >= int(getattr(settings, "context_compact_min_messages", 8) or 8)
            and len(messages) > last_compact_count
        )
        if should_auto_compact:
            summary_payload: dict[str, Any] | None = None
            summary_source = "heuristic"
            fallback_reason: str | None = None
            if mode == "llm":
                try:
                    prompt = build_llm_compaction_prompt(
                        messages,
                        max_source_chars=int(getattr(settings, "context_compact_summary_max_chars", 6000) or 6000) * 2,
                    )
                    summary_text = chat_completion_by_role(
                        settings,
                        prompt,
                        role=role_name,
                        route_conversation_phase="review",
                    )
                    parsed = extract_json_object(summary_text)
                    if isinstance(parsed, dict):
                        summary_payload = parsed
                        summary_source = "llm"
                    else:
                        fallback_reason = "llm_compaction_failed: non_json_summary"
                        _emit(
                            progress,
                            {
                                "phase": "compact_fallback",
                                "mode": "llm",
                                "fallback": "heuristic",
                                "error": fallback_reason,
                            },
                        )
                except Exception as exc:
                    fallback_reason = f"llm_compaction_failed: {exc}"
                    summary_source = "heuristic"
                    _emit(
                        progress,
                        {
                            "phase": "compact_fallback",
                            "mode": "llm",
                            "fallback": "heuristic",
                            "error": str(exc),
                        },
                    )
            comp = compact_messages(
                messages,
                keep_tail_messages=int(getattr(settings, "context_compact_keep_tail_messages", 8) or 8),
                summary_max_chars=int(getattr(settings, "context_compact_summary_max_chars", 6000) or 6000),
                summary_payload=summary_payload,
                summary_source=summary_source,
                fallback_reason=fallback_reason,
            )
            if summary_source == "llm":
                retention = evaluate_compaction_retention(
                    messages,
                    comp.messages,
                    keep_tail_messages=int(getattr(settings, "context_compact_keep_tail_messages", 8) or 8),
                )
                if not retention.passed:
                    fallback_reason = f"llm_compaction_quality_failed: {retention.reason}"
                    summary_source = "heuristic"
                    comp = compact_messages(
                        messages,
                        keep_tail_messages=int(getattr(settings, "context_compact_keep_tail_messages", 8) or 8),
                        summary_max_chars=int(getattr(settings, "context_compact_summary_max_chars", 6000) or 6000),
                        summary_source=summary_source,
                        fallback_reason=fallback_reason,
                    )
                    _emit(
                        progress,
                        {
                            "phase": "compact_fallback",
                            "mode": "llm",
                            "fallback": "heuristic",
                            "error": fallback_reason,
                            "retention": retention.payload,
                        },
                    )
            if (
                summary_source == "llm"
                and (not comp.compacted or comp.compacted_estimated_tokens >= comp.original_estimated_tokens)
            ):
                fallback_reason = "llm_compaction_not_smaller"
                summary_source = "heuristic"
                comp = compact_messages(
                    messages,
                    keep_tail_messages=int(getattr(settings, "context_compact_keep_tail_messages", 8) or 8),
                    summary_max_chars=int(getattr(settings, "context_compact_summary_max_chars", 6000) or 6000),
                    summary_source=summary_source,
                    fallback_reason=fallback_reason,
                )
                _emit(
                    progress,
                    {
                        "phase": "compact_fallback",
                        "mode": "llm",
                        "fallback": "heuristic",
                        "error": fallback_reason,
                    },
                )
            if comp.compacted and comp.compacted_estimated_tokens < comp.original_estimated_tokens:
                messages = comp.messages
                generation = int(state.get("compact_generation") or 0) + 1
                summary_text = ""
                if comp.summary_message:
                    summary_text = str(comp.summary_message.get("content") or "")
                extra_state.update(
                    {
                        "compact_generation": generation,
                        "compact_last_message_count": comp.original_message_count,
                        "compact_last_prompt_tokens": comp.compacted_estimated_tokens,
                        "compact_summary": summary_text,
                    },
                )
                estimated_prompt_tokens = comp.compacted_estimated_tokens
                _emit(
                    progress,
                    {
                        "phase": "compact",
                        "mode": mode,
                        "summary_source": summary_source,
                        "fallback": bool(fallback_reason),
                        "generation": generation,
                        "original_message_count": comp.original_message_count,
                        "compacted_message_count": comp.compacted_message_count,
                        "original_estimated_tokens": comp.original_estimated_tokens,
                        "compacted_estimated_tokens": comp.compacted_estimated_tokens,
                        "context_window": window,
                    },
                )

        if bool(state.get("tool_error_compact_pending")):
            if getattr(settings, "context_compact_on_tool_error", True):
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "[工具执行失败后的压缩建议] 上一轮工具未成功；请先向用户说明失败原因或补救思路，"
                            "避免在同一问题上重复无效调用；必要时缩短对上下文的依赖，并考虑使用 "
                            '{"type":"finish","message":"..."} 结束本轮。'
                        ),
                    },
                )
            extra_state["tool_error_compact_pending"] = False

        th_tool = int(getattr(settings, "context_compact_after_tool_calls", 0) or 0)
        tc = int(state.get("tool_call_count") or 0)
        last_m = int(state.get("compact_milestone_last_tc") or 0)
        if th_tool > 0 and tc > 0 and tc % th_tool == 0 and last_m < tc:
            messages.append(
                {
                    "role": "user",
                    "content": (
                        f"[工具里程碑，已成功工具轮次={tc}] 上下文已较长；请优先用 "
                        '{"type":"finish","message":"..."} 给出阶段性摘要，'
                        "或仅保留下一步最关键的一次工具调用。"
                    ),
                },
            )
            extra_state["compact_milestone_last_tc"] = tc

        prior_compact = bool(state.get("compact_hint_sent"))
        compact_hint_sent = prior_compact
        if (
            not prior_compact
            and settings.context_compact_after_iterations > 0
            and iteration >= settings.context_compact_after_iterations
        ):
            n_non_sys = sum(1 for m in messages if m.get("role") != "system")
            if n_non_sys >= settings.context_compact_min_messages:
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "[对话已较长] 若当前信息已足够回答用户，请优先使用 "
                            '{"type":"finish","message":"..."} 给出阶段性摘要或最终结论，'
                            "避免继续无明确收益的工具调用。"
                        ),
                    },
                )
                compact_hint_sent = True
                budget = int(getattr(settings, "cost_budget_max_tokens", 0) or 0)
                if budget > 0:
                    snap = get_last_usage()
                    total_u = int(snap.get("total_tokens") or 0)
                    if total_u > int(budget * 0.85):
                        messages.append(
                            {
                                "role": "user",
                                "content": (
                                    f"[成本提示] 累计 tokens≈{total_u}，已接近配置预算 {budget}；"
                                    "请压缩输出或结束本轮。"
                                ),
                            },
                        )

        max_it = max(1, int(settings.max_iterations))
        tc_route = int(state.get("tool_call_count") or 0)
        if tc_route == 0:
            route_phase = "explore"
        elif iteration >= max_it - 1:
            route_phase = "review"
        else:
            route_phase = "implement"

        if route_phase == "implement" and tc_route == 1 and not state.get("compact_research_done_sent"):
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "[compact:research_done] 已完成首轮有效工具调用；请把结论与下一步写清，"
                        '若信息足够可 {"type":"finish","message":"..."} 收束，避免无增量探索。'
                    ),
                },
            )
            extra_state["compact_research_done_sent"] = True
        if iteration == max_it and not state.get("compact_pre_retry_sent"):
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "[compact:pre_retry] 已达本轮最后一次模型迭代预算；"
                        "请只保留最高价值的一次工具调用或直接 finish。"
                    ),
                },
            )
            extra_state["compact_pre_retry_sent"] = True

        _emit(
            progress,
            {
                "phase": "llm",
                "iteration": iteration,
                "step": "请求模型",
            },
        )
        try:
            text = chat_completion_by_role(
                settings,
                messages,
                role=role_name,
                route_conversation_phase=route_phase,
            )
            prd = peek_last_profile_route_decision()
            if prd:
                _emit(
                    progress,
                    {
                        "phase": "profile_route",
                        "profile_route_decision": prd,
                    },
                )
        except Exception as llm_exc:
            err_msg = f"LLM 请求失败: {llm_exc}"
            messages.append(
                {
                    "role": "user",
                    "content": err_msg,
                },
            )
            _emit(progress, {"phase": "error", "iteration": iteration, "error": err_msg})
            return {
                "messages": messages,
                "iteration": iteration,
                "finished": True,
                "answer": err_msg,
                "pending": None,
                "compact_hint_sent": compact_hint_sent,
                **extra_state,
            }
        usage_snapshot = get_last_usage()
        _emit(
            progress,
            {
                "phase": "usage",
                "iteration": iteration,
                "prompt_tokens": int(usage_snapshot.get("prompt_tokens", 0)),
                "completion_tokens": int(usage_snapshot.get("completion_tokens", 0)),
                "total_tokens": int(usage_snapshot.get("total_tokens", 0)),
                "context_window": int(getattr(settings, "context_window", 0) or 0),
            },
        )
        if _is_stopped():
            _emit(progress, {"phase": "stopped"})
            return {
                "messages": messages,
                "iteration": iteration,
                "finished": True,
                "answer": "已手动停止本次运行。",
                "pending": None,
                "compact_hint_sent": compact_hint_sent,
                **extra_state,
            }
        messages.append({"role": "assistant", "content": text})
        _emit(
            progress,
            {
                "phase": "llm",
                "iteration": iteration,
                "step": "解析输出",
            },
        )

        try:
            obj = extract_json_object(text)
        except (ValueError, json.JSONDecodeError) as e:
            messages.append(
                {
                    "role": "user",
                    "content": (
                        f"无法解析 JSON：{e}。请只输出一个 JSON 对象，"
                        '例如 {{"type":"finish","message":"..."}}。'
                    ),
                },
            )
            return {
                "messages": messages,
                "iteration": iteration,
                "pending": None,
                "compact_hint_sent": compact_hint_sent,
                **extra_state,
            }

        t = obj.get("type")
        if t == "finish":
            _emit(
                progress,
                {"phase": "finish", "iteration": iteration},
            )
            return {
                "messages": messages,
                "iteration": iteration,
                "finished": True,
                "answer": str(obj.get("message", "")),
                "pending": None,
                "compact_hint_sent": compact_hint_sent,
                **extra_state,
            }
        if t == "tool":
            name = str(obj.get("name", ""))
            args = obj.get("args")
            if not isinstance(args, dict):
                args = {}
            _emit(
                progress,
                {
                    "phase": "planned_tool",
                    "iteration": iteration,
                    "name": name,
                    "summary": _args_summary(args),
                },
            )
            return {
                "messages": messages,
                "iteration": iteration,
                "pending": {"name": name, "args": args},
                "compact_hint_sent": compact_hint_sent,
                **extra_state,
            }

        messages.append(
            {
                "role": "user",
                "content": (
                    f'无效的 type={t!r}。请使用 "finish" 或 "tool"。'
                ),
            },
        )
        return {
            "messages": messages,
            "iteration": iteration,
            "pending": None,
            "compact_hint_sent": compact_hint_sent,
            **extra_state,
        }

    def tools_node(state: AgentState) -> dict[str, Any]:
        pending = state.get("pending")
        if not pending:
            return {}
        if _is_stopped():
            _emit(progress, {"phase": "stopped"})
            return {
                "finished": True,
                "answer": "已手动停止本次运行。",
                "pending": None,
                "compact_hint_sent": bool(state.get("compact_hint_sent")),
            }
        messages = list(state["messages"])
        name = str(pending.get("name", ""))
        args = pending.get("args") if isinstance(pending.get("args"), dict) else {}
        tool_evt: dict[str, Any] = {
            "phase": "tool",
            "name": name,
            "summary": _args_summary(args),
        }
        if name == "run_command":
            from cai_agent.runtime.registry import get_runtime_backend

            _rb = str(getattr(settings, "runtime_backend", "local") or "local").strip().lower() or "local"
            tool_evt["runtime_backend"] = get_runtime_backend(_rb, settings=settings).name
        _emit(progress, tool_evt)
        try:
            out = dispatch(settings, name, args)
        except Exception as e:
            out = f"工具执行失败: {e}"
        _emit(progress, {"phase": "tool_done", "name": name})
        payload = {"tool": name, "result": out}
        raw = json.dumps(payload, ensure_ascii=False)
        if len(raw) > 100_000:
            raw = raw[:100_000] + "…[截断]"
        messages.append({"role": "user", "content": raw})
        is_err = isinstance(out, str) and out.startswith("工具执行失败")
        prev_tc = int(state.get("tool_call_count") or 0)
        tool_call_count = prev_tc + (0 if is_err else 1)
        return {
            "messages": messages,
            "pending": None,
            "tool_call_count": tool_call_count,
            "tool_error_compact_pending": bool(is_err),
        }

    def route_after_llm(state: AgentState) -> Literal["end", "tools", "again"]:
        if state.get("finished"):
            return "end"
        if state.get("pending"):
            return "tools"
        return "again"

    graph = StateGraph(AgentState)
    graph.add_node("llm", llm_node)
    graph.add_node("tools", tools_node)
    graph.add_edge(START, "llm")
    graph.add_conditional_edges(
        "llm",
        route_after_llm,
        {
            "end": END,
            "tools": "tools",
            "again": "llm",
        },
    )
    graph.add_edge("tools", "llm")
    return graph.compile()


def initial_state(settings: Settings, user_goal: str) -> AgentState:
    return {
        "messages": [
            {"role": "system", "content": build_system_prompt(settings)},
            {"role": "user", "content": user_goal},
        ],
        "iteration": 0,
        "pending": None,
        "finished": False,
        "tool_call_count": 0,
        "compact_milestone_last_tc": 0,
        "tool_error_compact_pending": False,
        "compact_pre_retry_sent": False,
        "compact_research_done_sent": False,
        "compact_generation": 0,
        "compact_last_message_count": 0,
        "compact_last_prompt_tokens": 0,
    }
