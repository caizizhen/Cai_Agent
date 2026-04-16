from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import replace
from importlib import resources
from pathlib import Path

from cai_agent import __version__
from cai_agent.config import Settings
from cai_agent.doctor import run_doctor
from cai_agent.graph import build_app, initial_state
from cai_agent.llm import chat_completion, get_usage_counters, reset_usage_counters
from cai_agent.models import fetch_models
from cai_agent.rules import load_rule_text
from cai_agent.session import list_session_files, load_session, save_session
from cai_agent.tools import dispatch, tools_spec_markdown
from cai_agent.workflow import run_workflow


def _collect_tool_stats(messages: list[dict[str, object]]) -> tuple[int, list[str], str | None, int]:
    names: list[str] = []
    errors = 0
    last_tool: str | None = None
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
            tool_name = tn.strip()
            names.append(tool_name)
            last_tool = tool_name
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
    return len(names), uniq, last_tool, errors


def _cmd_init(*, force: bool) -> int:
    dest = Path.cwd() / "cai-agent.toml"
    if dest.exists() and not force:
        print(
            "当前目录已存在 cai-agent.toml；若需覆盖请添加 --force",
            file=sys.stderr,
        )
        return 1
    try:
        tpl = resources.files("cai_agent").joinpath("templates/cai-agent.example.toml")
        data = tpl.read_bytes()
    except Exception as e:
        print(f"读取内置配置模板失败: {e}", file=sys.stderr)
        return 1
    dest.write_bytes(data)
    print(f"已生成 {dest.resolve()}")
    return 0


def main(argv: list[str] | None = None) -> int:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--config",
        default=None,
        metavar="PATH",
        help="TOML 配置文件（未指定时可用环境变量 CAI_CONFIG 或当前目录 cai-agent.toml）",
    )
    common.add_argument(
        "--model",
        default=None,
        metavar="MODEL_ID",
        help="临时覆盖当前模型（优先级高于配置文件/环境变量）",
    )

    parser = argparse.ArgumentParser(prog="cai-agent")
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    init_p = sub.add_parser(
        "init",
        help="在当前目录生成 cai-agent.toml（来自内置示例）",
    )
    init_p.add_argument(
        "--force",
        action="store_true",
        help="覆盖已存在的 cai-agent.toml",
    )

    plan_p = sub.add_parser(
        "plan",
        parents=[common],
        help="仅生成实现计划草案（不实际调用工具），类似 Claude Code 的 Plan 模式",
    )
    plan_p.add_argument(
        "goal",
        nargs="+",
        help="要规划的任务描述（可多个词）",
    )
    plan_p.add_argument(
        "-w",
        "--workspace",
        default=None,
        help="工作区根目录（默认当前目录或环境变量 CAI_WORKSPACE）",
    )
    plan_p.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="以一行 JSON 输出规划结果（便于脚本或其他 Agent 调用）",
    )

    run_p = sub.add_parser(
        "run",
        parents=[common],
        help="根据自然语言目标运行本地 Agent",
    )
    run_p.add_argument(
        "goal",
        nargs="+",
        help="任务描述（可多个词）",
    )
    run_p.add_argument(
        "-w",
        "--workspace",
        default=None,
        help="工作区根目录（默认当前目录或环境变量 CAI_WORKSPACE）",
    )
    run_p.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="只打印最终回答，不打印过程",
    )
    run_p.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="将 answer 与迭代次数等以一行 JSON 打印到 stdout（隐含不打印过程日志）",
    )
    run_p.add_argument(
        "--save-session",
        default=None,
        metavar="PATH",
        help="将本轮运行后的会话写入 JSON 文件",
    )
    run_p.add_argument(
        "--load-session",
        default=None,
        metavar="PATH",
        help="先从 JSON 会话恢复 messages，再追加本次 goal 继续运行",
    )

    doctor_p = sub.add_parser(
        "doctor",
        parents=[common],
        help="打印当前解析后的配置与工作区诊断信息（API Key 打码）",
    )
    doctor_p.add_argument(
        "-w",
        "--workspace",
        default=None,
        help="覆盖工作区目录（默认来自配置 / 当前目录）",
    )

    cont_p = sub.add_parser(
        "continue",
        parents=[common],
        help="基于历史会话 JSON 继续提问（等价于 run --load-session）",
    )
    cont_p.add_argument(
        "session",
        help="历史会话 JSON 文件路径（通常由 --save-session 生成）",
    )
    cont_p.add_argument(
        "goal",
        nargs="+",
        help="继续追问的任务描述",
    )
    cont_p.add_argument(
        "-w",
        "--workspace",
        default=None,
        help="工作区根目录（默认当前目录或环境变量 CAI_WORKSPACE）",
    )
    cont_p.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="只打印最终回答，不打印过程",
    )
    cont_p.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="将 answer 与迭代次数等以一行 JSON 打印到 stdout",
    )
    cont_p.add_argument(
        "--save-session",
        default=None,
        metavar="PATH",
        help="将继续运行后的会话写入 JSON 文件",
    )

    models_p = sub.add_parser(
        "models",
        parents=[common],
        help="从当前 provider 的 OpenAI 兼容 /models 端点列出可用模型",
    )
    models_p.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="以 JSON 数组输出模型列表",
    )
    mcp_p = sub.add_parser(
        "mcp-check",
        parents=[common],
        help="检查 MCP Bridge 连通性并打印可用工具",
    )
    mcp_p.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="以 JSON 输出检查结果",
    )
    mcp_p.add_argument(
        "--force",
        action="store_true",
        help="强制刷新工具列表（跳过本地缓存）",
    )
    mcp_p.add_argument(
        "--verbose",
        action="store_true",
        help="输出更多诊断信息（provider/model/耗时等）",
    )
    mcp_p.add_argument(
        "--tool",
        default=None,
        metavar="TOOL_NAME",
        help="额外调用一个 MCP 工具做真实探活",
    )
    mcp_p.add_argument(
        "--args",
        default="{}",
        metavar="JSON",
        help="与 --tool 配合使用的 JSON 参数，默认 {}",
    )
    sess_p = sub.add_parser(
        "sessions",
        help="列出当前目录近期会话文件（默认 .cai-session-*.json）",
    )
    sess_p.add_argument(
        "--pattern",
        default=".cai-session*.json",
        help="匹配模式（相对当前目录）",
    )
    sess_p.add_argument(
        "--limit",
        type=int,
        default=20,
        help="最多显示条目数",
    )
    sess_p.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="以 JSON 数组输出",
    )
    sess_p.add_argument(
        "--details",
        action="store_true",
        help="输出每个会话的摘要（消息数/工具调用数/最后回答预览）",
    )

    stats_p = sub.add_parser(
        "stats",
        help="汇总当前目录近期会话的耗时与工具调用等指标（基于保存的会话 JSON）",
    )
    stats_p.add_argument(
        "--pattern",
        default=".cai-session*.json",
        help="匹配模式（相对当前目录）",
    )
    stats_p.add_argument(
        "--limit",
        type=int,
        default=50,
        help="最多统计的会话文件数",
    )
    stats_p.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="以 JSON 对象输出汇总结果",
    )

    wf_p = sub.add_parser(
        "workflow",
        parents=[common],
        help="根据 JSON workflow 文件依次运行多个步骤任务",
    )
    wf_p.add_argument(
        "file",
        help="workflow JSON 文件路径（包含 steps 数组）",
    )
    wf_p.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="以 JSON 对象输出全部步骤结果与汇总",
    )

    ui_p = sub.add_parser(
        "ui",
        parents=[common],
        help="交互式终端界面（Textual，类 Claude Code 会话）",
    )
    ui_p.add_argument(
        "-w",
        "--workspace",
        default=None,
        help="工作区根目录（默认当前目录或环境变量 CAI_WORKSPACE）",
    )

    args = parser.parse_args(argv)

    if args.command == "init":
        return _cmd_init(force=args.force)

    if args.command == "doctor":
        try:
            settings = Settings.from_env(config_path=args.config)
        except FileNotFoundError as e:
            print(str(e), file=sys.stderr)
            return 2
        if args.model:
            settings = replace(settings, model=str(args.model).strip())
        if args.workspace:
            settings = replace(
                settings,
                workspace=os.path.abspath(args.workspace),
            )
        return run_doctor(settings)

    if args.command == "plan":
        try:
            settings = Settings.from_env(config_path=args.config)
        except FileNotFoundError as e:
            print(str(e), file=sys.stderr)
            return 2
        if args.model:
            settings = replace(settings, model=str(args.model).strip())
        if args.workspace:
            settings = replace(
                settings,
                workspace=os.path.abspath(args.workspace),
            )
        goal = " ".join(args.goal).strip()
        if not goal:
            print("goal 不能为空", file=sys.stderr)
            return 2

        rules_text = load_rule_text(settings)
        rules_block = (
            "\n\n下面是与本项目相关的工程规则与安全约定，请在规划中严格遵守：\n"
            f"{rules_text}\n"
        ) if rules_text else ""

        system = (
            "你是 CAI Agent 的规划助手，只负责在执行前给出实现方案，"
            "不会真正修改文件或运行命令。\n"
            "请以分步结构化方式输出：\n"
            "1) 总体目标与风险\n"
            "2) 需要修改/创建的文件列表\n"
            "3) 每个步骤的大致实现要点\n"
            "4) 验证与回滚策略\n\n"
            f"工作区根目录: {settings.workspace}\n\n"
            "下列是 Agent 在执行阶段可用的工具说明（只读/写入/搜索等）：\n"
            f"{tools_spec_markdown()}\n"
            "本次仅输出规划文本，不要再输出 JSON 工具调用指令。"
            f"{rules_block}"
        )
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": goal},
        ]
        reset_usage_counters()
        started = time.perf_counter()
        try:
            plan_text = chat_completion(settings, messages)
        except Exception as e:
            print(f"生成计划失败: {e}", file=sys.stderr)
            return 2
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        usage = get_usage_counters()
        if args.json_output:
            payload = {
                "goal": goal,
                "plan": plan_text.strip(),
                "workspace": settings.workspace,
                "provider": settings.provider,
                "model": settings.model,
                "elapsed_ms": elapsed_ms,
                "usage": usage,
            }
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(plan_text.strip())
            print(
                f"\n[plan] provider={settings.provider} model={settings.model} "
                f"elapsed_ms={elapsed_ms} "
                f"tokens={usage.get('total_tokens', 0)}",
                file=sys.stderr,
            )
        return 0

    if args.command == "models":
        try:
            settings = Settings.from_env(config_path=args.config)
        except FileNotFoundError as e:
            print(str(e), file=sys.stderr)
            return 2
        if args.model:
            settings = replace(settings, model=str(args.model).strip())
        try:
            models = fetch_models(settings)
        except Exception as e:
            print(f"获取模型列表失败: {e}", file=sys.stderr)
            return 2
        if args.json_output:
            print(json.dumps(models, ensure_ascii=False))
        else:
            if not models:
                print("(无模型)")
            else:
                for m in models:
                    print(m)
        return 0

    if args.command == "mcp-check":
        try:
            settings = Settings.from_env(config_path=args.config)
        except FileNotFoundError as e:
            print(str(e), file=sys.stderr)
            return 2
        if args.model:
            settings = replace(settings, model=str(args.model).strip())
        started = time.perf_counter()
        try:
            txt = dispatch(settings, "mcp_list_tools", {"force": bool(args.force)})
            ok = not txt.startswith("[mcp_list_tools 失败]")
        except Exception as e:
            ok = False
            txt = f"{type(e).__name__}: {e}"
        probe_result = None
        if ok and args.tool:
            try:
                probe_args = json.loads(args.args)
                if not isinstance(probe_args, dict):
                    raise ValueError("--args 必须是 JSON object")
                probe_result = dispatch(
                    settings,
                    "mcp_call_tool",
                    {"name": str(args.tool).strip(), "args": probe_args},
                )
                if isinstance(probe_result, str) and probe_result.startswith("[mcp_call_tool 失败]"):
                    ok = False
            except Exception as e:
                ok = False
                probe_result = f"{type(e).__name__}: {e}"
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        if args.json_output:
            payload = {
                "ok": ok,
                "provider": settings.provider,
                "model": settings.model,
                "mcp_enabled": settings.mcp_enabled,
                "mcp_base_url": settings.mcp_base_url,
                "force": bool(args.force),
                "tool": args.tool,
                "elapsed_ms": elapsed_ms,
                "result": txt,
                "probe_result": probe_result,
            }
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(f"ok={ok}")
            print(f"mcp_enabled={settings.mcp_enabled}")
            print(f"mcp_base_url={settings.mcp_base_url}")
            if args.verbose:
                print(f"provider={settings.provider}")
                print(f"model={settings.model}")
                print(f"force={bool(args.force)}")
                print(f"tool={args.tool}")
                print(f"elapsed_ms={elapsed_ms}")
            print(txt)
            if probe_result is not None:
                print("--- tool probe ---")
                print(probe_result)
        return 0 if ok else 2

    if args.command == "sessions":
        files = list_session_files(
            cwd=os.getcwd(),
            pattern=str(args.pattern),
            limit=int(args.limit),
        )
        details: list[dict[str, object]] = []
        if args.details:
            for p in files:
                try:
                    sess = load_session(str(p))
                except Exception:
                    details.append(
                        {
                            "name": p.name,
                            "path": str(p),
                            "error": "parse_failed",
                        },
                    )
                    continue
                msgs = sess.get("messages")
                msg_list = msgs if isinstance(msgs, list) else []
                tc, used, last_tool, err_count = _collect_tool_stats(
                    msg_list if isinstance(msg_list, list) else [],
                )
                ans = sess.get("answer")
                ans_preview = ""
                if isinstance(ans, str) and ans.strip():
                    ans_preview = ans.strip()[:120] + ("…" if len(ans.strip()) > 120 else "")
                details.append(
                    {
                        "name": p.name,
                        "path": str(p),
                        "messages_count": len(msg_list),
                        "tool_calls_count": tc,
                        "used_tools": used,
                        "last_tool": last_tool,
                        "error_count": err_count,
                        "answer_preview": ans_preview,
                    },
                )
        if args.json_output:
            arr = []
            for i, p in enumerate(files):
                item: dict[str, object] = {
                    "name": p.name,
                    "path": str(p),
                    "mtime": int(p.stat().st_mtime),
                    "size": p.stat().st_size,
                }
                if args.details and i < len(details) and isinstance(details[i], dict):
                    item.update(details[i])
                arr.append(item)
            print(json.dumps(arr, ensure_ascii=False))
        else:
            if not files:
                print("(无会话文件)")
            for i, p in enumerate(files, start=1):
                st = p.stat()
                print(f"{i:>2}. {p.name}\t{st.st_size} bytes")
                if args.details and i - 1 < len(details):
                    d = details[i - 1]
                    if "error" in d:
                        print("    [parse_failed]")
                    else:
                        print(
                            "    "
                            f"messages={d.get('messages_count')} "
                            f"tool_calls={d.get('tool_calls_count')} "
                            f"errors={d.get('error_count')} "
                            f"last_tool={d.get('last_tool')}",
                        )
                        ap = d.get("answer_preview")
                        if isinstance(ap, str) and ap:
                            print(f"    answer={ap}")
        return 0

    if args.command == "stats":
        files = list_session_files(
            cwd=os.getcwd(),
            pattern=str(args.pattern),
            limit=int(args.limit),
        )
        total = 0
        total_elapsed = 0
        total_tool_calls = 0
        total_errors = 0
        by_model: dict[str, int] = {}

        for p in files:
            try:
                sess = load_session(str(p))
            except Exception:
                continue
            total += 1
            elapsed = sess.get("elapsed_ms")
            if isinstance(elapsed, int):
                total_elapsed += elapsed
            model = sess.get("model")
            if isinstance(model, str) and model.strip():
                by_model[model] = by_model.get(model, 0) + 1
            msgs = sess.get("messages")
            msg_list = msgs if isinstance(msgs, list) else []
            tc, _, _, err_count = _collect_tool_stats(
                msg_list if isinstance(msg_list, list) else [],
            )
            total_tool_calls += tc
            total_errors += err_count

        summary = {
            "sessions_count": total,
            "elapsed_ms_total": total_elapsed,
            "elapsed_ms_avg": int(total_elapsed / total) if total else 0,
            "tool_calls_total": total_tool_calls,
            "tool_calls_avg": float(total_tool_calls) / total if total else 0.0,
            "tool_errors_total": total_errors,
            "tool_errors_avg": float(total_errors) / total if total else 0.0,
            "models_distribution": by_model,
        }
        if args.json_output:
            print(json.dumps(summary, ensure_ascii=False))
        else:
            print(f"sessions_count={summary['sessions_count']}")
            print(f"elapsed_ms_total={summary['elapsed_ms_total']}")
            print(f"elapsed_ms_avg={summary['elapsed_ms_avg']}")
            print(f"tool_calls_total={summary['tool_calls_total']}")
            print(f"tool_calls_avg={summary['tool_calls_avg']:.2f}")
            print(f"tool_errors_total={summary['tool_errors_total']}")
            print(f"tool_errors_avg={summary['tool_errors_avg']:.2f}")
            if by_model:
                print("models_distribution:")
                for m, cnt in by_model.items():
                    print(f"  {m}: {cnt}")
        return 0

    if args.command == "workflow":
        try:
            settings = Settings.from_env(config_path=args.config)
        except FileNotFoundError as e:
            print(str(e), file=sys.stderr)
            return 2
        if args.model:
            settings = replace(settings, model=str(args.model).strip())
        if args.workspace:
            settings = replace(
                settings,
                workspace=os.path.abspath(args.workspace),
            )
        try:
            result = run_workflow(settings, args.file)
        except Exception as e:
            print(f"运行 workflow 失败: {e}", file=sys.stderr)
            return 2
        if args.json_output:
            print(json.dumps(result, ensure_ascii=False))
        else:
            steps = result.get("steps") or []
            summary = result.get("summary") or {}
            print(f"steps_count={summary.get('steps_count', len(steps))}")
            print(f"elapsed_ms_total={summary.get('elapsed_ms_total', 0)}")
            print(f"elapsed_ms_avg={summary.get('elapsed_ms_avg', 0)}")
            print(f"tool_calls_total={summary.get('tool_calls_total', 0)}")
            print(f"tool_errors_total={summary.get('tool_errors_total', 0)}")
            for step in steps:
                name = step.get("name") or ""
                goal = (step.get("goal") or "")[:80]
                elapsed_ms = step.get("elapsed_ms")
                tools = step.get("tool_calls_count")
                errors = step.get("error_count")
                print(
                    f"- [{name}] elapsed_ms={elapsed_ms} "
                    f"tool_calls={tools} errors={errors} goal={goal!r}"
                )
        return 0

    if args.command in ("run", "continue"):
        try:
            settings = Settings.from_env(config_path=args.config)
        except FileNotFoundError as e:
            print(str(e), file=sys.stderr)
            return 2
        if args.model:
            settings = replace(settings, model=str(args.model).strip())
        if args.workspace:
            settings = replace(
                settings,
                workspace=os.path.abspath(args.workspace),
            )
        goal = " ".join(args.goal).strip()
        if not goal:
            print("goal 不能为空", file=sys.stderr)
            return 2

        reset_usage_counters()
        app = build_app(settings)
        load_session_path = args.load_session if args.command == "run" else args.session
        if load_session_path:
            try:
                sess = load_session(load_session_path)
            except Exception as e:
                print(f"读取会话失败: {e}", file=sys.stderr)
                return 2
            messages = sess.get("messages")
            if not isinstance(messages, list) or not messages:
                print("会话文件不合法：messages 必须是非空数组", file=sys.stderr)
                return 2
            state = {
                "messages": list(messages) + [{"role": "user", "content": goal}],
                "iteration": 0,
                "pending": None,
                "finished": False,
            }
        else:
            state = initial_state(settings, goal)
        started = time.perf_counter()
        final = app.invoke(state)
        elapsed_ms = int((time.perf_counter() - started) * 1000)

        if (
            not args.quiet
            and not args.json_output
            and final.get("messages")
        ):
            print("--- messages (last assistant) ---", file=sys.stderr)
            for m in final["messages"][-6:]:
                role = m.get("role", "")
                content = (m.get("content") or "")[:2000]
                print(f"[{role}]\n{content}\n", file=sys.stderr)

        usage = get_usage_counters()
        if args.json_output:
            msgs = final.get("messages") if isinstance(final.get("messages"), list) else []
            tool_calls_count, used_tools, last_tool, error_count = _collect_tool_stats(msgs)
            payload = {
                "answer": (final.get("answer") or "").strip(),
                "iteration": final.get("iteration"),
                "finished": final.get("finished"),
                "config": settings.config_loaded_from,
                "workspace": settings.workspace,
                "provider": settings.provider,
                "model": settings.model,
                "mcp_enabled": settings.mcp_enabled,
                "elapsed_ms": elapsed_ms,
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
                "tool_calls_count": tool_calls_count,
                "used_tools": used_tools,
                "last_tool": last_tool,
                "error_count": error_count,
            }
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(final.get("answer", "").strip())

        if args.save_session:
            payload = {
                "version": 2,
                "workspace": settings.workspace,
                "config": settings.config_loaded_from,
                "provider": settings.provider,
                "model": settings.model,
                "mcp_enabled": settings.mcp_enabled,
                "elapsed_ms": elapsed_ms,
                "messages": final.get("messages") or [],
                "answer": final.get("answer"),
            }
            try:
                save_session(args.save_session, payload)
            except Exception as e:
                print(f"写入会话失败: {e}", file=sys.stderr)
                return 2
        return 0

    if args.command == "ui":
        from cai_agent.tui import run_tui

        try:
            settings = Settings.from_env(config_path=args.config)
        except FileNotFoundError as e:
            print(str(e), file=sys.stderr)
            return 2
        if args.model:
            settings = replace(settings, model=str(args.model).strip())
        if args.workspace:
            settings = replace(
                settings,
                workspace=os.path.abspath(args.workspace),
            )
        run_tui(settings)
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
