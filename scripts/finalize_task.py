#!/usr/bin/env python3
"""Finalize a completed task and keep the active docs in sync.

This script is intentionally small and explicit: callers provide the completed
task ID, summary, and verification evidence. The script then moves that task out
of NEXT_ACTIONS, appends completion evidence to the archive, and writes a QA run
note. With --push it can also commit and push the selected changed files.
"""

from __future__ import annotations

import argparse
import datetime as dt
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
NEXT_ACTIONS = ROOT / "docs" / "NEXT_ACTIONS.zh-CN.md"
ARCHIVE = ROOT / "docs" / "COMPLETED_TASKS_ARCHIVE.zh-CN.md"
TEST_TODOS = ROOT / "docs" / "TEST_TODOS.zh-CN.md"
QA_RUNS = ROOT / "docs" / "qa" / "runs"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _split_sections(text: str) -> list[tuple[str, int, int]]:
    rows: list[tuple[str, int, int]] = []
    lines = text.splitlines()
    starts: list[tuple[str, int]] = []
    for idx, line in enumerate(lines):
        if line.startswith("## "):
            starts.append((line.strip(), idx))
    for pos, (title, start) in enumerate(starts):
        end = starts[pos + 1][1] if pos + 1 < len(starts) else len(lines)
        rows.append((title, start, end))
    return rows


def _section_bounds(lines: list[str], title: str) -> tuple[int, int] | None:
    starts: list[tuple[str, int]] = []
    for idx, line in enumerate(lines):
        if line.startswith("## "):
            starts.append((line.strip(), idx))
    for pos, (candidate, start) in enumerate(starts):
        if candidate == title:
            end = starts[pos + 1][1] if pos + 1 < len(starts) else len(lines)
            return start, end
    return None


def _remove_task_rows_from_section(lines: list[str], title: str, task_ids: list[str]) -> list[str]:
    bounds = _section_bounds(lines, title)
    if bounds is None:
        return lines
    start, end = bounds
    before = lines[:start]
    section = lines[start:end]
    after = lines[end:]
    filtered: list[str] = []
    for line in section:
        is_table_row = line.startswith("|")
        has_task = any(f"`{tid}`" in line or tid in line for tid in task_ids)
        if is_table_row and has_task:
            continue
        filtered.append(line)
    return before + filtered + after


def _insert_after_table_header(lines: list[str], title: str, row: str) -> list[str]:
    bounds = _section_bounds(lines, title)
    if bounds is None:
        lines.extend(["", title, "", row])
        return lines
    start, end = bounds
    insert_at = end
    for idx in range(start, end):
        if lines[idx].startswith("|---"):
            insert_at = idx + 1
            break
    if row in lines[start:end]:
        return lines
    return lines[:insert_at] + [row] + lines[insert_at:]


def update_next_actions(
    *,
    task_ids: list[str],
    summary: str,
    verification: list[str],
    date: str,
    next_row: str | None,
) -> None:
    text = _read(NEXT_ACTIONS)
    lines = text.splitlines()
    for idx, line in enumerate(lines):
        if line.startswith("> 最后同步："):
            lines[idx] = (
                f"> 最后同步：{date}。状态来源：`DEVELOPER_TODOS.zh-CN.md`、"
                "`TEST_TODOS.zh-CN.md`、`PRODUCT_GAP_ANALYSIS.zh-CN.md`、"
                "`ROADMAP_EXECUTION.zh-CN.md`、`IMPLEMENTATION_STATUS.zh-CN.md`。"
            )
            break
    lines = _remove_task_rows_from_section(lines, "## 现在做", task_ids)
    verify_text = "<br>".join(verification) if verification else "未记录"
    for task_id in task_ids:
        row = f"| `{task_id}` | {date} | {summary} | {verify_text} |"
        lines = _insert_after_table_header(lines, "## 刚完成", row)
    if next_row:
        lines = _insert_after_table_header(lines, "## 现在做", next_row)
    _write(NEXT_ACTIONS, "\n".join(lines).rstrip() + "\n")


def append_archive(*, task_ids: list[str], summary: str, verification: list[str], date: str) -> None:
    text = _read(ARCHIVE)
    marker = "## 自动完成归档"
    if marker not in text:
        text = (
            text.rstrip()
            + "\n\n"
            + marker
            + "\n\n"
            + "| Issue ID | 完成日期 | 交付摘要 | 验证 | 来源 / 备注 |\n"
            + "|---|---|---|---|---|\n"
        )
    verify_text = "<br>".join(verification) if verification else "未记录"
    rows = []
    for task_id in task_ids:
        row = f"| `{task_id}` | {date} | {summary} | {verify_text} | finalize_task |\n"
        if row not in text:
            rows.append(row)
    if rows:
        text = text.rstrip() + "\n" + "".join(rows)
    _write(ARCHIVE, text.rstrip() + "\n")


def append_test_todos(*, task_ids: list[str], verification: list[str], qa_path: Path, date: str) -> None:
    text = _read(TEST_TODOS)
    marker = "## 自动验证记录"
    if marker not in text:
        text = (
            text.rstrip()
            + "\n\n"
            + marker
            + "\n\n"
            + "| 日期 | 任务 | 验证 | 记录 |\n"
            + "|---|---|---|---|\n"
        )
    verify_text = "<br>".join(verification) if verification else "未记录"
    task_text = ", ".join(f"`{tid}`" for tid in task_ids)
    rel = qa_path.relative_to(ROOT).as_posix()
    row = f"| {date} | {task_text} | {verify_text} | [`{rel}`]({rel}) |\n"
    if row not in text:
        text = text.rstrip() + "\n" + row
    _write(TEST_TODOS, text.rstrip() + "\n")


def write_qa_run(*, task_ids: list[str], summary: str, verification: list[str], date: str) -> Path:
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    safe_id = "-".join(t.replace("/", "_") for t in task_ids)
    path = QA_RUNS / f"task-finalize-{stamp}-{safe_id}.md"
    checks = "\n".join(f"- {v}" for v in verification) if verification else "- 未记录"
    body = f"""# Task Finalize Run

- **Date**: {date}
- **Task ID(s)**: {", ".join(f"`{t}`" for t in task_ids)}
- **Summary**: {summary}

## Verification

{checks}

## Docs Updated

- `docs/NEXT_ACTIONS.zh-CN.md`
- `docs/COMPLETED_TASKS_ARCHIVE.zh-CN.md`
- `docs/TEST_TODOS.zh-CN.md`
- `{path.as_posix()}`
"""
    _write(path, body)
    return path


def _run(argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=str(ROOT),
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        shell=False,
    )


def commit_and_push(paths: list[Path], message: str) -> None:
    rels = [str(p.relative_to(ROOT)) for p in paths]
    add = _run(["git", "add", "--", *rels])
    if add.returncode != 0:
        raise RuntimeError(f"git add failed: {add.stderr.strip()}")
    commit = _run(["git", "commit", "-m", message])
    if commit.returncode != 0:
        raise RuntimeError(f"git commit failed: {commit.stderr.strip() or commit.stdout.strip()}")
    push = _run(["git", "push", "origin", "main"])
    if push.returncode != 0:
        raise RuntimeError(f"git push failed: {push.stderr.strip() or push.stdout.strip()}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Finalize a completed task and sync docs.")
    p.add_argument("--task-id", action="append", required=True, help="Completed task ID; repeatable.")
    p.add_argument("--summary", required=True, help="Short completion summary.")
    p.add_argument("--verification", action="append", default=[], help="Verification command/result; repeatable.")
    p.add_argument(
        "--next-row",
        default=None,
        help="Optional Markdown table row to add under NEXT_ACTIONS '现在做'.",
    )
    p.add_argument("--date", default=dt.date.today().isoformat())
    p.add_argument("--push", action="store_true", help="Commit changed finalize docs and push origin main.")
    p.add_argument("--commit-message", default=None)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    task_ids = [str(t).strip() for t in args.task_id if str(t).strip()]
    if not task_ids:
        print("--task-id cannot be empty", file=sys.stderr)
        return 2
    verification = [str(v).strip() for v in args.verification if str(v).strip()]

    update_next_actions(
        task_ids=task_ids,
        summary=str(args.summary).strip(),
        verification=verification,
        date=str(args.date),
        next_row=args.next_row,
    )
    append_archive(task_ids=task_ids, summary=str(args.summary).strip(), verification=verification, date=str(args.date))
    qa_path = write_qa_run(
        task_ids=task_ids,
        summary=str(args.summary).strip(),
        verification=verification,
        date=str(args.date),
    )
    append_test_todos(task_ids=task_ids, verification=verification, qa_path=qa_path, date=str(args.date))
    changed = [NEXT_ACTIONS, ARCHIVE, TEST_TODOS, qa_path]
    print("finalize_task: updated")
    for p in changed:
        print(f"- {p.relative_to(ROOT)}")
    if args.push:
        msg = args.commit_message or f"Finalize {' '.join(task_ids)} docs"
        commit_and_push(changed, msg)
        print("finalize_task: committed and pushed origin main")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
