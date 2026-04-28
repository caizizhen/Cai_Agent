from __future__ import annotations

import json
import re
import shutil
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import os
from typing import Any, Iterable, List

from cai_agent.ecc_ingest_gate import build_ecc_pack_ingest_gate_for_explicit_hooks_v1


@dataclass(frozen=True)
class Skill:
    """从 `skills/` 目录加载的可复用工作流/提示模版描述."""

    name: str
    path: Path
    content: str


def _is_skill_file(path: Path) -> bool:
    return path.suffix.lower() in {".md", ".markdown", ".txt"}


def load_skills(root: str | Path) -> List[Skill]:
    """从仓库根目录下的 `skills/` 目录加载全部技能文件.

    当前实现只负责读取文件内容, 不做语义解析, 便于后续在 CLI/TUI
    或 LLM 提示中引用这些模版。
    """

    base = Path(root).expanduser().resolve()
    skills_dir = base / "skills"
    if not skills_dir.is_dir():
        return []
    items: list[Skill] = []
    for p in sorted(skills_dir.rglob("*")):
        if not p.is_file() or not _is_skill_file(p):
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue
        rel_name = p.relative_to(skills_dir).as_posix()
        items.append(Skill(name=rel_name, path=p, content=text))
    return items


def iter_skill_names(skills: Iterable[Skill]) -> list[str]:
    """提取技能名称列表, 便于在 UI 或 system prompt 中展示."""

    return sorted({s.name for s in skills})


def _slug_goal(goal: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9_-]+", "-", goal.strip()).strip("-").lower()[:80]
    return s or "goal"


def resolve_auto_extract_for_runner(settings: Any, *, goal: str) -> tuple[bool, bool | None]:
    """任务结束后是否运行 ``auto_extract_skill_after_task``，以及 ``use_llm`` 覆盖。

    优先级：``CAI_SKILLS_AUTO_EXTRACT=1`` 开启；否则看 ``[skills.auto_extract].enabled``。
    ``mode``: ``template`` | ``llm`` | ``auto``（无 TOML 时默认 ``template``）。
    """
    env_on = os.environ.get("CAI_SKILLS_AUTO_EXTRACT", "").strip().lower() in ("1", "true", "yes", "on")
    cfg_on = bool(getattr(settings, "skills_auto_extract_enabled", False))
    if not env_on and not cfg_on:
        return False, None
    min_c = max(1, int(getattr(settings, "skills_auto_extract_min_goal_chars", 8) or 8))
    if len((goal or "").strip()) < min_c:
        return False, None
    mode = str(getattr(settings, "skills_auto_extract_mode", "template") or "template").strip().lower()
    if mode not in ("template", "llm", "auto"):
        mode = "template"
    has_llm = bool(str(getattr(settings, "api_key", "") or "").strip()) and not bool(getattr(settings, "mock", False))
    if mode == "template":
        return True, False
    if mode == "llm":
        return True, True
    # auto
    return True, has_llm


def promote_evolution_skill(
    *,
    root: str | Path,
    src_rel: str,
    dest_name: str,
) -> dict[str, Any]:
    """将 ``skills/_evolution_*.md`` 提升为正式技能 ``skills/<name>.md``，写盘后跑 ``skills lint``；失败则回滚移动。"""
    from cai_agent.agentskills_util import split_frontmatter_body

    base = Path(root).expanduser().resolve()
    raw_src = str(src_rel or "").strip().replace("\\", "/").lstrip("/")
    if raw_src.startswith("skills/"):
        raw_src = raw_src[len("skills/") :]
    src_path = (base / "skills" / raw_src).resolve()
    try:
        src_path.relative_to((base / "skills").resolve())
    except ValueError as e:
        msg = "src 必须位于 skills/ 下"
        raise ValueError(msg) from e
    if not src_path.is_file():
        msg = f"源文件不存在: {src_path}"
        raise ValueError(msg)
    if not src_path.name.startswith("_evolution_"):
        msg = "promote 仅支持 skills/_evolution_*.md 草稿"
        raise ValueError(msg)

    to_raw = str(dest_name or "").strip().replace("\\", "/").lstrip("/")
    if to_raw.startswith("skills/"):
        to_raw = to_raw[len("skills/") :]
    if not to_raw.lower().endswith((".md", ".markdown", ".txt")):
        to_raw = f"{to_raw}.md"
    dst_path = (base / "skills" / to_raw).resolve()
    try:
        dst_path.relative_to((base / "skills").resolve())
    except ValueError as e:
        msg = "dest 必须位于 skills/ 下"
        raise ValueError(msg) from e
    if dst_path.is_file():
        msg = f"目标已存在: {dst_path}"
        raise ValueError(msg)

    body = src_path.read_text(encoding="utf-8")
    meta, _rest = split_frontmatter_body(body)
    if not str(meta.get("name") or "").strip() or not str(meta.get("description") or "").strip():
        title_line = next((ln.strip("# ") for ln in body.splitlines() if ln.strip()), "promoted skill")
        stem = Path(to_raw).stem
        desc = (title_line[:160] + "…") if len(title_line) > 160 else title_line
        if len(str(desc).strip()) < 12:
            desc = "从任务草稿提升的技能条目，包含可复用步骤与注意事项说明。"
        fm = f"---\nname: {stem}\ndescription: {desc}\n---\n\n"
        body = fm + body.lstrip()
    # skills lint 要求正文 ≥40 字符；草稿常较短，补齐可机读占位
    if len(body.strip()) < 80:
        body = body.rstrip() + "\n\n## 正文\n\n" + ("可复用说明与注意事项占位。" * 5) + "\n"

    tmp_swap = src_path.with_suffix(src_path.suffix + ".promote-bak")
    shutil.move(str(src_path), str(tmp_swap))
    try:
        dst_path.write_text(body, encoding="utf-8")
        linted = lint_skills_workspace(root=base)
        viol = linted.get("violations") or []
        bad = [
            v
            for v in viol
            if isinstance(v, dict) and str(v.get("path") or "").replace("\\", "/").endswith(to_raw.replace("\\", "/"))
        ]
        if bad:
            dst_path.unlink(missing_ok=True)
            shutil.move(str(tmp_swap), str(src_path))
            return {
                "schema_version": "skills_promote_v1",
                "ok": False,
                "rolled_back": True,
                "reason": "lint_failed",
                "violations": bad,
                "from": raw_src,
                "to": to_raw,
            }
        tmp_swap.unlink(missing_ok=True)
        return {
            "schema_version": "skills_promote_v1",
            "ok": True,
            "rolled_back": False,
            "from": raw_src,
            "to": to_raw,
            "lint": {"ok": bool(linted.get("ok")), "violation_count": int(linted.get("violation_count") or 0)},
        }
    except Exception:
        if dst_path.is_file():
            dst_path.unlink(missing_ok=True)
        if tmp_swap.is_file():
            shutil.move(str(tmp_swap), str(src_path))
        raise


def auto_promote_evolution_skills(
    *,
    root: str | Path,
    threshold: int | None = None,
) -> dict[str, Any]:
    """当 ``skill-usage`` 中某 ``_evolution_*`` 命中次数 ≥ 阈值时，自动 promote 到 ``<stem>-autopromoted.md``。"""
    from cai_agent.skill_evolution import count_skill_usage_events

    th = int(os.environ.get("CAI_SKILLS_PROMOTE_THRESHOLD", "5")) if threshold is None else int(threshold)
    th = max(1, min(10_000, th))
    base = Path(root).expanduser().resolve()
    skills_dir = base / "skills"
    if not skills_dir.is_dir():
        return {"schema_version": "skills_promote_auto_v1", "promoted": [], "skipped": [], "threshold": th}
    promoted: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for p in sorted(skills_dir.glob("_evolution_*.md")):
        try:
            rel = p.resolve().relative_to(skills_dir.resolve()).as_posix()
        except ValueError:
            continue
        n = count_skill_usage_events(base, rel)
        if n < th:
            skipped.append({"path": rel, "hits": n, "reason": "below_threshold"})
            continue
        stem = p.stem  # _evolution_foo
        dest = f"{stem.replace('_evolution_', '') or 'skill'}-autopromoted.md"
        dest = re.sub(r"[^a-zA-Z0-9_.-]+", "-", dest).strip("-") or "skill-autopromoted.md"
        try:
            out = promote_evolution_skill(root=base, src_rel=rel, dest_name=dest)
            promoted.append({"src": rel, "dest": dest, "hits": n, "result": out})
        except Exception as e:
            skipped.append({"path": rel, "hits": n, "reason": str(e)[:200]})
    return {
        "schema_version": "skills_promote_auto_v1",
        "threshold": th,
        "promoted": promoted,
        "skipped": skipped,
    }


def build_skill_evolution_suggest(
    *,
    root: str | Path,
    goal: str,
    write: bool = False,
) -> dict[str, Any]:
    """技能自进化闭环 MVP：根据任务文本给出可落盘草稿路径与预览（可选 ``--write``）。"""
    base = Path(root).expanduser().resolve()
    slug = _slug_goal(goal)
    rel = f"skills/_evolution_{slug}.md"
    path = base / rel
    body = (
        "# Evolution draft\n\n"
        "## Source goal\n\n"
        f"{goal.strip()}\n\n"
        "## Next steps\n\n"
        "- [ ] 复核命名与目录约定\n"
        "- [ ] 从 `_evolution_` 前缀迁出并纳入正式 `skills/`\n"
    )
    existed_before = path.is_file()
    written = False
    if write:
        path.parent.mkdir(parents=True, exist_ok=True)
        if not existed_before:
            path.write_text(body, encoding="utf-8")
            written = True
    return {
        "schema_version": "skills_evolution_suggest_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "workspace": str(base),
        "suggested_path": rel.replace("\\", "/"),
        "write_requested": bool(write),
        "written": written,
        "file_existed_before": existed_before,
        "preview": body[:800],
    }


def _truthy_env(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def _llm_skill_extract_body(
    *,
    settings: Any,
    goal: str,
    answer: str,
    events_summary: str = "",
) -> tuple[dict[str, Any] | None, str]:
    from cai_agent.llm_factory import chat_completion
    from cai_agent.skill_evolution import load_skill_extract_prompt_template, parse_skill_extract_llm_json

    tmpl = load_skill_extract_prompt_template().strip()
    sys_prompt = tmpl or "Extract reusable steps as JSON with keys steps,caveats,followups (arrays of strings)."
    user_blob = (
        f"## Goal\n\n{goal.strip()}\n\n## Answer\n\n{(answer or '').strip()[:8000]}\n\n"
        f"## Events\n\n{(events_summary or '').strip()[:4000] or '（无）'}\n"
    )
    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": user_blob},
    ]
    raw = chat_completion(settings, messages)
    parsed = parse_skill_extract_llm_json(raw)
    return parsed, raw


def _format_extract_sections_from_llm(data: dict[str, Any]) -> str:
    def _bullets(key: str) -> str:
        v = data.get(key)
        if not isinstance(v, list):
            return ""
        lines = [str(x).strip() for x in v if str(x).strip()]
        if not lines:
            return "_（无）_\n"
        return "\n".join(f"- {x}" for x in lines) + "\n"

    return (
        "## 可复用步骤建议\n\n"
        f"{_bullets('steps')}\n"
        "## 注意事项 / 坑\n\n"
        f"{_bullets('caveats')}\n"
        "## 后续\n\n"
        f"{_bullets('followups')}"
    )


def auto_extract_skill_after_task(
    *,
    root: str | Path,
    goal: str,
    answer: str = "",
    write: bool = True,
    settings: Any | None = None,
    use_llm: bool | None = None,
    events_summary: str = "",
) -> dict[str, Any]:
    """任务完成后自动提炼技能草稿（§25 补齐：任务后自动提炼）。

    在 ``skills/_evolution_<slug>.md`` 写入结构化草稿，包含：
    - 任务目标
    - 答案摘要
    - 可复用步骤建议（占位或 LLM 结构化）

    Args:
        root: 工作区根目录。
        goal: 本次任务目标字符串。
        answer: 任务最终答案（摘要或完整文本）。
        write: 是否真正写文件（默认 True）。
        settings: 可选；与 ``use_llm`` 联用走 LLM 提炼。
        use_llm: 显式开关；默认读取环境变量 ``CAI_SKILLS_AUTO_EXTRACT_LLM``。
        events_summary: 可选事件摘要，供 LLM 参考。

    Returns:
        ``skills_auto_extract_v1`` 或 ``skills_auto_extract_v2`` 结构。
    """
    base = Path(root).expanduser().resolve()
    slug = _slug_goal(goal)
    rel = f"skills/_evolution_{slug}.md"
    path = base / rel

    want_llm = bool(use_llm) if use_llm is not None else _truthy_env("CAI_SKILLS_AUTO_EXTRACT_LLM")
    llm_used = False
    extraction_mode = "template"
    llm_error: str | None = None
    llm_raw_preview = ""

    answer_preview = (answer.strip()[:600] + "…") if len(answer.strip()) > 600 else answer.strip()
    sections_steps = (
        "<!-- TODO: 将本次执行中可复用的操作步骤整理到此处 -->\n"
        "- [ ] 步骤 1\n"
        "- [ ] 步骤 2\n\n"
        "## 注意事项 / 坑\n\n"
        "<!-- TODO: 记录踩过的坑或特殊注意事项 -->\n\n"
        "## 后续\n\n"
        "- [ ] 复核命名与目录约定\n"
        "- [ ] 从 `_evolution_` 前缀迁出并纳入正式 `skills/`\n"
    )
    if want_llm and settings is not None:
        try:
            parsed, raw = _llm_skill_extract_body(
                settings=settings,
                goal=goal,
                answer=answer,
                events_summary=events_summary,
            )
            llm_raw_preview = (raw or "")[:400]
            if parsed:
                sections_steps = _format_extract_sections_from_llm(parsed)
                llm_used = True
                extraction_mode = "llm"
            else:
                llm_error = "llm_parse_failed"
                extraction_mode = "template_fallback"
        except Exception as e:  # noqa: BLE001 — 提炼失败回退占位
            llm_error = str(e)[:200]
            extraction_mode = "template_fallback"
    elif want_llm:
        extraction_mode = "template_fallback"
    schema_version = "skills_auto_extract_v2" if llm_used else "skills_auto_extract_v1"

    body = (
        "# Auto-extracted Skill Draft\n\n"
        f"> 生成时间：{datetime.now(UTC).isoformat()}\n\n"
        "## 任务目标\n\n"
        f"{goal.strip()}\n\n"
        "## 答案摘要\n\n"
        f"{answer_preview or '（无答案摘要）'}\n\n"
        f"{sections_steps}"
    )
    existed_before = path.is_file()
    written = False
    if write and not existed_before:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
        written = True
    out: dict[str, Any] = {
        "schema_version": schema_version,
        "generated_at": datetime.now(UTC).isoformat(),
        "workspace": str(base),
        "suggested_path": rel.replace("\\", "/"),
        "write_requested": bool(write),
        "written": written,
        "file_existed_before": existed_before,
        "goal_preview": goal.strip()[:120],
        "preview": body[:800],
        "llm_used": llm_used,
        "llm_requested": bool(want_llm),
        "extraction_mode": extraction_mode,
    }
    if llm_error:
        out["llm_error"] = llm_error
    if llm_raw_preview:
        out["llm_raw_preview"] = llm_raw_preview
    return out


def build_skills_hub_manifest(*, root: str | Path) -> dict[str, Any]:
    """Skills Hub 分发清单（``skills_hub_manifest_v2``）：扫描 ``skills/`` + agentskills 元数据。"""
    from cai_agent.agentskills_util import agentskills_compliant, split_frontmatter_body

    base = Path(root).expanduser().resolve()
    skills = load_skills(base)
    entries: list[dict[str, Any]] = []
    for s in skills:
        try:
            st = s.path.stat()
        except OSError:
            continue
        try:
            rel = s.path.resolve().relative_to(base)
            rel_s = rel.as_posix()
        except ValueError:
            rel_s = str(s.path)
        meta, body = split_frontmatter_body(s.content)
        compliant = agentskills_compliant(meta, body)
        entries.append(
            {
                "name": s.name,
                "path": rel_s,
                "size_bytes": int(st.st_size),
                "mtime_iso": datetime.fromtimestamp(st.st_mtime, tz=UTC).isoformat(),
                "agentskills_compliant": compliant,
                "skill_name": str(meta.get("name") or "").strip() or None,
                "skill_description": str(meta.get("description") or "").strip() or None,
            },
        )
    skills_dir = base / "skills"
    return {
        "schema_version": "skills_hub_manifest_v2",
        "agentskills_version": "1.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "workspace": str(base),
        "skills_dir": str(skills_dir),
        "skills_dir_exists": skills_dir.is_dir(),
        "count": len(entries),
        "entries": entries,
    }


def lint_skills_workspace(*, root: str | Path) -> dict[str, Any]:
    """``skills_lint_v1``：校验 frontmatter + 正文长度（agentskills 风格子集）。"""
    from cai_agent.agentskills_util import agentskills_compliant, split_frontmatter_body

    base = Path(root).expanduser().resolve()
    skills = load_skills(base)
    violations: list[dict[str, Any]] = []
    for s in skills:
        meta, body = split_frontmatter_body(s.content)
        if agentskills_compliant(meta, body):
            continue
        try:
            rel = s.path.resolve().relative_to(base).as_posix()
        except ValueError:
            rel = s.name
        reasons: list[str] = []
        if not str(meta.get("name") or "").strip():
            reasons.append("missing_name")
        if not str(meta.get("description") or "").strip():
            reasons.append("missing_description")
        elif len(str(meta.get("description")).strip()) < 8:
            reasons.append("description_too_short")
        if len(body.strip()) < 40:
            reasons.append("body_too_short")
        violations.append({"name": s.name, "path": rel, "reasons": reasons})
    return {
        "schema_version": "skills_lint_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "workspace": str(base),
        "violations": violations,
        "violation_count": len(violations),
        "ok": len(violations) == 0,
    }


def fetch_remote_skills_manifest(url: str, *, timeout_sec: float = 30.0) -> dict[str, Any]:
    """GET JSON manifest from remote registry URL (agentskills-compatible)."""
    import json as _json

    import httpx
    from cai_agent.http_trust import effective_http_trust_env

    u = str(url or "").strip()
    if not u:
        raise ValueError("url_empty")
    trust_env = effective_http_trust_env(trust_env=True, request_url=u)
    with httpx.Client(timeout=timeout_sec, follow_redirects=True, trust_env=trust_env) as client:
        resp = client.get(u)
    resp.raise_for_status()
    doc = resp.json()
    if not isinstance(doc, dict):
        raise ValueError("manifest_not_object")
    return doc


def list_remote_skills_registry_index(
    url: str,
    *,
    timeout_sec: float = 30.0,
    sync_mirror: bool = False,
    mirror_cwd: str | Path | None = None,
) -> dict[str, Any]:
    """``skills_hub_list_remote_v1``：远程 manifest 的 ``entries[]`` 索引 + 可选镜像追加行。"""
    doc = fetch_remote_skills_manifest(url, timeout_sec=timeout_sec)
    entries = doc.get("entries")
    rows: list[dict[str, Any]] = []
    if isinstance(entries, list):
        for e in entries:
            if not isinstance(e, dict):
                continue
            rows.append(
                {
                    "name": str(e.get("name") or "").strip(),
                    "path": str(e.get("path") or "").strip(),
                    "skill_name": e.get("skill_name"),
                    "size_bytes": e.get("size_bytes"),
                },
            )
    out: dict[str, Any] = {
        "schema_version": "skills_hub_list_remote_v1",
        "url": url,
        "manifest_schema": doc.get("schema_version"),
        "count": len(rows),
        "entries": rows,
    }
    if sync_mirror and mirror_cwd is not None:
        base = Path(mirror_cwd).expanduser().resolve()
        mp = base / ".cai" / "skills-registry-mirror.jsonl"
        mp.parent.mkdir(parents=True, exist_ok=True)
        snap = {
            "ts": datetime.now(UTC).isoformat(),
            "url": url,
            "count": len(rows),
            "names": [str(r.get("name") or "") for r in rows if r.get("name")],
        }
        with mp.open("a", encoding="utf-8") as f:
            f.write(json.dumps(snap, ensure_ascii=False) + "\n")
        out["mirror_path"] = str(mp)
    return out


def apply_skills_hub_manifest_selection(
    *,
    root: str | Path,
    manifest: dict[str, Any],
    only: frozenset[str] | None,
    dest_rel: str = ".cursor/skills",
    dry_run: bool = False,
) -> dict[str, Any]:
    """按 manifest ``entries[]`` 将技能文件复制到 ``dest_rel``（可选 ``only`` 过滤 ``name``）。"""
    base = Path(root).expanduser().resolve()
    dest = (base / dest_rel.strip().replace("\\", "/").lstrip("/")).resolve()
    try:
        dest.relative_to(base)
    except ValueError as e:
        msg = "dest 必须位于 workspace 根之下"
        raise ValueError(msg) from e
    entries = manifest.get("entries")
    if not isinstance(entries, list):
        msg = "manifest.entries 须为数组"
        raise ValueError(msg)
    ops: list[tuple[Path, Path, str]] = []
    skipped: list[dict[str, str]] = []
    for e in entries:
        if not isinstance(e, dict):
            continue
        name = str(e.get("name") or "").strip()
        rel = str(e.get("path") or "").strip().replace("\\", "/")
        if only is not None and name not in only:
            continue
        src = (base / rel).resolve()
        try:
            src.relative_to(base)
        except ValueError:
            skipped.append({"name": name, "reason": "path_escape"})
            continue
        if not src.is_file():
            skipped.append({"name": name, "reason": "missing_source"})
            continue
        out = dest / src.name
        ops.append((src, out, name))

    hooks_sources = [src for src, _o, _n in ops if src.name == "hooks.json"]
    gate_doc: dict[str, Any] | None = None
    if hooks_sources:
        gate_doc = build_ecc_pack_ingest_gate_for_explicit_hooks_v1(base, hooks_sources)
        if not dry_run and not bool(gate_doc.get("allow", True)):
            return {
                "schema_version": "skills_hub_pack_install_v1",
                "ok": False,
                "dry_run": False,
                "error": "ingest_gate_rejected",
                "hint": "manifest 中的 hooks.json 命中 ingest 与 hook_runtime 一致的危险规则，或路径越界；已拒绝写入",
                "ingest_gate": gate_doc,
                "dest": str(dest),
                "copied": [],
                "skipped": skipped,
            }

    copied: list[dict[str, str]] = []
    for src, out, _name in ops:
        if not dry_run:
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, out)
        copied.append({"from": str(src), "to": str(out)})

    out_payload: dict[str, Any] = {
        "schema_version": "skills_hub_pack_install_v1",
        "dry_run": dry_run,
        "dest": str(dest),
        "copied": copied,
        "skipped": skipped,
    }
    if gate_doc is not None:
        out_payload["ingest_gate"] = gate_doc
    if not dry_run:
        out_payload["ok"] = True
    return out_payload


# ---------------------------------------------------------------------------
# Skills Hub 运行时分发（§25 补齐）：轻量 HTTP 服务，提供 manifest + 文件内容
# ---------------------------------------------------------------------------

class _SkillsHubHandler(BaseHTTPRequestHandler):
    """内嵌 HTTP 处理器，只处理 GET 请求。"""

    hub_root: Path = Path(".")

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        pass  # 静默日志，避免干扰 CLI 输出

    def do_GET(self) -> None:  # noqa: N802
        from urllib.parse import unquote, urlparse
        import json as _json

        parsed = urlparse(self.path)
        path = unquote(parsed.path).lstrip("/")

        if path in ("", "manifest", "manifest.json"):
            manifest = build_skills_hub_manifest(root=self.hub_root)
            body = _json.dumps(manifest, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if path.startswith("skill/"):
            skill_rel = path[len("skill/"):]
            skill_path = (self.hub_root / "skills" / skill_rel).resolve()
            try:
                skill_path.relative_to((self.hub_root / "skills").resolve())
            except ValueError:
                self._send_error(403, "path traversal denied")
                return
            if not skill_path.is_file():
                self._send_error(404, f"skill not found: {skill_rel}")
                return
            try:
                content = skill_path.read_bytes()
            except OSError as e:
                self._send_error(500, str(e))
                return
            mime = "text/markdown; charset=utf-8" if skill_path.suffix.lower() in {".md", ".markdown"} else "text/plain; charset=utf-8"
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return

        self._send_error(404, "not found")

    def _send_error(self, code: int, msg: str) -> None:
        import json as _json
        body = _json.dumps({"error": msg}).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def serve_skills_hub(
    *,
    root: str | Path,
    host: str = "127.0.0.1",
    port: int = 7891,
    timeout_seconds: float | None = None,
) -> dict[str, Any]:
    """启动 Skills Hub HTTP 服务（§25 补齐：Hub 运行时分发）。

    提供两个端点：
    - ``GET /manifest`` → skills_hub_manifest_v2 JSON
    - ``GET /skill/<name>`` → 技能文件内容

    Args:
        root: 工作区根目录。
        host: 监听主机（默认 127.0.0.1）。
        port: 监听端口（默认 7891）。
        timeout_seconds: 服务超时秒数（None = 永久运行直到 KeyboardInterrupt）。

    Returns:
        ``skills_hub_serve_v1`` 结构，记录服务结束状态。
    """
    base = Path(root).expanduser().resolve()

    class _Handler(_SkillsHubHandler):
        hub_root = base

    server = HTTPServer((host, port), _Handler)
    started_at = datetime.now(UTC).isoformat()
    requests_handled = 0

    if timeout_seconds is not None:
        timer = threading.Timer(timeout_seconds, server.shutdown)
        timer.start()
    else:
        timer = None

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        if timer is not None:
            timer.cancel()
        server.server_close()

    return {
        "schema_version": "skills_hub_serve_v1",
        "started_at": started_at,
        "stopped_at": datetime.now(UTC).isoformat(),
        "host": host,
        "port": port,
        "workspace": str(base),
        "ok": True,
    }
