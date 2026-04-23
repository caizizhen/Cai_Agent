from __future__ import annotations

import re
import shutil
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Iterable, List


def _skill_extract_should_use_llm(settings: Any) -> bool:
    if bool(getattr(settings, "mock", False)):
        return False
    if not str(getattr(settings, "api_key", "") or "").strip():
        return False
    profiles = getattr(settings, "profiles", None) or ()
    return bool(profiles)


def _draft_skill_markdown_via_llm(*, goal: str, answer: str, settings: Any) -> str | None:
    """调用 LLM 生成技能草稿正文；失败或输出过短则返回 None。"""
    try:
        from cai_agent.llm_factory import chat_completion_by_role
    except Exception:
        return None
    g = goal.strip()[:1200]
    a = (answer or "").strip()[:2400]
    messages = [
        {
            "role": "system",
            "content": (
                "你是技术文档助手。根据任务目标与答案摘要，输出一份 Markdown 技能草稿。"
                "第一行必须是标题: # Auto-extracted Skill Draft\n"
                "随后依次包含小节: ## 任务目标、## 答案摘要、## 可复用步骤建议、## 注意事项 / 坑。\n"
                "步骤与注意事项用 Markdown 列表编写；不要输出 HTML 注释或 <!-- TODO 占位符。"
            ),
        },
        {"role": "user", "content": f"## 任务目标\n\n{g}\n\n## 答案摘要\n\n{a or '（无）'}\n"},
    ]
    try:
        raw = chat_completion_by_role(settings, messages, role="active").strip()
    except Exception:
        return None
    if len(raw) < 80:
        return None
    if "<!-- TODO" in raw or "<!-- todo" in raw.lower():
        return None
    if not raw.startswith("#"):
        raw = "# Auto-extracted Skill Draft\n\n" + raw
    return raw


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


def auto_extract_skill_after_task(
    *,
    root: str | Path,
    goal: str,
    answer: str = "",
    write: bool = True,
    settings: Any | None = None,
) -> dict[str, Any]:
    """任务完成后自动提炼技能草稿（§25 补齐：任务后自动提炼）。

    在 ``skills/_evolution_<slug>.md`` 写入结构化草稿，包含：
    - 任务目标
    - 答案摘要
    - 可复用步骤建议（无可用 ``settings`` 时为占位模板；有 API 配置时尝试 LLM 生成）

    Args:
        root: 工作区根目录。
        goal: 本次任务目标字符串。
        answer: 任务最终答案（摘要或完整文本）。
        write: 是否真正写文件（默认 True）。
        settings: 可选运行时配置；提供有效 ``api_key`` 且非 mock 时走 LLM 提炼。

    Returns:
        ``skills_auto_extract_v1`` 结构（含 ``draft_method``: ``llm`` | ``template``）。
    """
    base = Path(root).expanduser().resolve()
    slug = _slug_goal(goal)
    rel = f"skills/_evolution_{slug}.md"
    path = base / rel

    answer_preview = (answer.strip()[:600] + "…") if len(answer.strip()) > 600 else answer.strip()
    draft_method = "template"
    body = (
        "# Auto-extracted Skill Draft\n\n"
        f"> 生成时间：{datetime.now(UTC).isoformat()}\n\n"
        "## 任务目标\n\n"
        f"{goal.strip()}\n\n"
        "## 答案摘要\n\n"
        f"{answer_preview or '（无答案摘要）'}\n\n"
        "## 可复用步骤建议\n\n"
        "<!-- TODO: 将本次执行中可复用的操作步骤整理到此处 -->\n"
        "- [ ] 步骤 1\n"
        "- [ ] 步骤 2\n\n"
        "## 注意事项 / 坑\n\n"
        "<!-- TODO: 记录踩过的坑或特殊注意事项 -->\n\n"
        "## 后续\n\n"
        "- [ ] 复核命名与目录约定\n"
        "- [ ] 从 `_evolution_` 前缀迁出并纳入正式 `skills/`\n"
    )
    if settings is not None and _skill_extract_should_use_llm(settings):
        drafted = _draft_skill_markdown_via_llm(goal=goal, answer=answer, settings=settings)
        if drafted:
            body = drafted + (
                "\n\n## 后续\n\n"
                "- [ ] 复核命名与目录约定\n"
                "- [ ] 从 `_evolution_` 前缀迁出并纳入正式 `skills/`\n"
            )
            draft_method = "llm"
    existed_before = path.is_file()
    written = False
    if write and not existed_before:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
        written = True
    return {
        "schema_version": "skills_auto_extract_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "workspace": str(base),
        "suggested_path": rel.replace("\\", "/"),
        "write_requested": bool(write),
        "written": written,
        "file_existed_before": existed_before,
        "goal_preview": goal.strip()[:120],
        "draft_method": draft_method,
        "preview": body[:800],
    }


def build_skills_hub_manifest(*, root: str | Path) -> dict[str, Any]:
    """Skills Hub 分发清单（``skills_hub_manifest_v1``）：扫描工作区 ``skills/`` 下可分发文件。"""
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
        entries.append(
            {
                "name": s.name,
                "path": rel_s,
                "size_bytes": int(st.st_size),
                "mtime_iso": datetime.fromtimestamp(st.st_mtime, tz=UTC).isoformat(),
            },
        )
    skills_dir = base / "skills"
    return {
        "schema_version": "skills_hub_manifest_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "workspace": str(base),
        "skills_dir": str(skills_dir),
        "skills_dir_exists": skills_dir.is_dir(),
        "count": len(entries),
        "entries": entries,
    }


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
    copied: list[dict[str, str]] = []
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
        if not dry_run:
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, out)
        copied.append({"from": str(src), "to": str(out)})
    return {
        "schema_version": "skills_hub_pack_install_v1",
        "dry_run": dry_run,
        "dest": str(dest),
        "copied": copied,
        "skipped": skipped,
    }


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
    - ``GET /manifest`` → skills_hub_manifest_v1 JSON
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

