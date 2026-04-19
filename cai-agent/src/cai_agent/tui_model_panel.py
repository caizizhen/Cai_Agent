"""TUI：模型 profile 面板（Sprint 3 M4）。

列表、Enter 切换、`a` 新增、`e` 编辑、`d` 删除、`t` 连通测试；空态引导；
写回 ``cai-agent.toml`` 时复用 ``profiles.write_models_to_toml`` 与 CLI 相同语义。
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Footer, Input, Label, OptionList, Static
from textual.widgets.option_list import Option

from cai_agent.models import ping_profile
from cai_agent.profiles import (
    Profile,
    ProfilesError,
    add_profile,
    apply_preset,
    build_profile,
    edit_profile,
    remove_profile,
    write_models_to_toml,
)

from cai_agent.config import Settings


def _toml_write_target(settings: Settings) -> Path:
    if settings.config_loaded_from:
        return Path(settings.config_loaded_from).expanduser().resolve()
    return (Path.cwd() / "cai-agent.toml").resolve()


def _next_active_id(
    current_active: str | None,
    profiles: tuple[Profile, ...],
    *,
    prefer: str | None = None,
) -> str | None:
    if prefer and any(p.id == prefer for p in profiles):
        return prefer
    if current_active and any(p.id == current_active for p in profiles):
        return current_active
    return profiles[0].id if profiles else None


def _short_text(s: str, max_len: int) -> str:
    t = (s or "").strip().replace("\n", " ")
    if len(t) <= max_len:
        return t
    return t[: max(1, max_len - 1)] + "…"


def _profile_row(p: Profile, *, active_id: str) -> str:
    """``id | model | provider | base_url | notes | [active]``（与 backlog §3.1 对齐）。"""
    mark = "[active] " if p.id == active_id else ""
    notes = _short_text(p.notes or "", 28)
    base = _short_text(p.base_url or "", 40)
    tail_notes = f" | {notes}" if notes else ""
    return (
        f"{mark}{p.id} | {p.model} | {p.provider} | {base}{tail_notes}"
    )


class ConfirmDeleteScreen(ModalScreen[bool]):
    """``y`` 确认删除，Esc 取消。"""

    BINDINGS = [Binding("escape", "dismiss_false", "取消", show=True)]

    def __init__(self, profile_id: str) -> None:
        super().__init__()
        self._profile_id = profile_id

    def compose(self) -> ComposeResult:
        yield Static(
            f"确认删除 profile [cyan]{self._profile_id}[/] ？\n"
            "[dim]按 [bold]y[/] 确认，Esc 取消[/]",
            markup=True,
        )

    def on_key(self, event: Any) -> None:
        if getattr(event, "key", None) == "y":
            self.dismiss(True)

    def action_dismiss_false(self) -> None:
        self.dismiss(False)


class ProfileAddFormScreen(ModalScreen[dict[str, Any] | None]):
    """向导式新增：preset + id + model，可选设为 active。"""

    BINDINGS = [Binding("escape", "cancel", "取消", show=True)]

    def compose(self) -> ComposeResult:
        yield Label("新增 profile（Esc 取消）")
        yield Static(
            "预设: openai / anthropic / lmstudio / ollama / openrouter / vllm / gateway",
            classes="dim",
        )
        yield Input(placeholder="preset（默认 lmstudio）", id="add-preset", value="lmstudio")
        yield Input(placeholder="profile id（必填，字母数字-_）", id="add-id")
        yield Input(placeholder="model 名称（必填）", id="add-model")
        yield Checkbox("保存后设为当前 active", value=True, id="add-active")
        with Horizontal():
            yield Button("保存", variant="primary", id="add-save")
            yield Button("取消", id="add-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "add-cancel":
            self.dismiss(None)
            return
        if event.button.id != "add-save":
            return
        preset = self.query_one("#add-preset", Input).value.strip().lower() or "lmstudio"
        pid = self.query_one("#add-id", Input).value.strip()
        model = self.query_one("#add-model", Input).value.strip()
        set_active = self.query_one("#add-active", Checkbox).value
        if not pid or not model:
            self.app.notify("id 与 model 不能为空", severity="warning")
            return
        try:
            raw = apply_preset({"id": pid, "model": model}, preset)
            build_profile(raw, hint=f"panel add {pid}")
        except ProfilesError as e:
            self.app.notify(str(e), severity="error", timeout=8.0)
            return
        self.dismiss(
            {
                "ok": True,
                "preset": preset,
                "pid": pid,
                "model": model,
                "set_active": set_active,
            },
        )

    def action_cancel(self) -> None:
        self.dismiss(None)


class ProfileEditFormScreen(ModalScreen[dict[str, Any] | None]):
    """编辑当前条目的 model / base_url / notes / temperature。"""

    BINDINGS = [Binding("escape", "cancel", "取消", show=True)]

    def __init__(self, profile: Profile) -> None:
        super().__init__()
        self._profile = profile

    def compose(self) -> ComposeResult:
        yield Label(f"编辑 profile [cyan]{self._profile.id}[/]（Esc 取消）", markup=True)
        yield Input(
            placeholder="model",
            id="ed-model",
            value=self._profile.model,
        )
        yield Input(
            placeholder="base_url",
            id="ed-base",
            value=self._profile.base_url,
        )
        yield Input(
            placeholder="notes",
            id="ed-notes",
            value=self._profile.notes or "",
        )
        yield Input(
            placeholder="temperature",
            id="ed-temp",
            value=str(self._profile.temperature),
        )
        with Horizontal():
            yield Button("保存", variant="primary", id="ed-save")
            yield Button("取消", id="ed-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "ed-cancel":
            self.dismiss(None)
            return
        if event.button.id != "ed-save":
            return
        model = self.query_one("#ed-model", Input).value.strip()
        base_url = self.query_one("#ed-base", Input).value.strip()
        notes = self.query_one("#ed-notes", Input).value.strip()
        temp_s = self.query_one("#ed-temp", Input).value.strip()
        if not model or not base_url:
            self.app.notify("model 与 base_url 不能为空", severity="warning")
            return
        try:
            float(temp_s)
        except ValueError:
            self.app.notify("temperature 必须是数字", severity="warning")
            return
        self.dismiss(
            {
                "ok": True,
                "model": model,
                "base_url": base_url,
                "notes": notes or None,
                "temperature": float(temp_s),
            },
        )

    def action_cancel(self) -> None:
        self.dismiss(None)


class ModelPanelScreen(ModalScreen[str | None]):
    """模型 profile 面板：列表 + 子动作；Enter 选中并 ``dismiss(profile_id)``。"""

    BINDINGS = [
        Binding("escape", "dismiss", "关闭", show=True),
        Binding("t", "ping_highlighted", "测试", show=True, priority=True),
        Binding("a", "add_profile", "新增", show=True, priority=True),
        Binding("e", "edit_profile", "编辑", show=True, priority=True),
        Binding("d", "delete_profile", "删除", show=True, priority=True),
    ]

    def __init__(
        self,
        settings: Settings,
        *,
        reload_settings: Callable[[], Settings],
    ) -> None:
        super().__init__()
        self._settings = settings
        self._reload_settings = reload_settings

    def _header_text(self) -> str:
        s = self._settings
        sub = getattr(s, "subagent_profile_id", None) or "-"
        pln = getattr(s, "planner_profile_id", None) or "-"
        return (
            f"active={s.active_profile_id}  subagent={sub}  planner={pln}\n"
            "Enter 切换 · a 新增 · e 编辑 · d 删除 · t 测试 · Esc 关闭"
        )

    def compose(self) -> ComposeResult:
        chat_api = (getattr(self._settings, "base_url", "") or "").strip() or "(未知)"
        yield Static(
            f"[dim]聊天请求发往[/] [cyan]{chat_api}[/] [dim]（当前 profile 的 base_url）。[/]",
            id="model-panel-hint",
            markup=True,
        )
        yield Static(self._header_text(), id="model-panel-header", markup=True)
        profs = tuple(self._settings.profiles or ())
        yield Static(
            (
                "[yellow]还没有模型 profile。[/] 按 [bold]a[/] 添加第一个，"
                "或先在项目根执行 [cyan]cai-agent init[/] / [cyan]cai-agent models add[/]。"
            )
            if not profs
            else "",
            id="model-panel-empty",
            markup=True,
        )
        opts: list[Option] = [
            Option(_profile_row(p, active_id=self._settings.active_profile_id), id=p.id)
            for p in profs
        ]
        yield OptionList(*opts, id="model-panel-list")
        yield Footer()

    def on_mount(self) -> None:
        profs = tuple(self._settings.profiles or ())
        empty = self.query_one("#model-panel-empty", Static)
        empty.display = not bool(profs)
        ol = self.query_one("#model-panel-list", OptionList)
        if ol.option_count == 0:
            ol.display = False
            return
        ol.display = True
        for i, p in enumerate(self._settings.profiles):
            if p.id == self._settings.active_profile_id:
                ol.highlighted = i
                break
        ol.focus()

    def _current_highlighted_profile(self) -> Profile | None:
        ol = self.query_one("#model-panel-list", OptionList)
        if ol.option_count == 0:
            return None
        try:
            opt = ol.get_option_at_index(ol.highlighted)
        except Exception:
            return None
        if opt is None or not opt.id:
            return None
        oid = str(opt.id)
        return next((p for p in self._settings.profiles if p.id == oid), None)

    def _refresh_after_disk_write(self) -> None:
        self._settings = self._reload_settings()
        try:
            self.query_one("#model-panel-header", Static).update(self._header_text())
        except Exception:
            pass
        hint = self.query_one("#model-panel-hint", Static)
        chat_api = (getattr(self._settings, "base_url", "") or "").strip() or "(未知)"
        hint.update(
            f"[dim]聊天请求发往[/] [cyan]{chat_api}[/] [dim]（当前 profile 的 base_url）。[/]",
        )
        empty = self.query_one("#model-panel-empty", Static)
        profs = tuple(self._settings.profiles or ())
        empty.display = not bool(profs)
        if not profs:
            empty.update(
                "[yellow]还没有模型 profile。[/] 按 [bold]a[/] 添加第一个，"
                "或先在项目根执行 [cyan]cai-agent init[/] / [cyan]cai-agent models add[/]。",
            )
        else:
            empty.update("")
        ol = self.query_one("#model-panel-list", OptionList)
        ol.display = True
        ol.clear_options()
        for p in self._settings.profiles:
            ol.add_option(
                Option(_profile_row(p, active_id=self._settings.active_profile_id), id=p.id),
            )
        if ol.option_count == 0:
            ol.display = False
            return
        for i, p in enumerate(self._settings.profiles):
            if p.id == self._settings.active_profile_id:
                ol.highlighted = i
                break
        ol.focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        oid = event.option.id
        if oid:
            self.dismiss(str(oid))

    def action_dismiss(self) -> None:
        self.dismiss(None)

    def action_ping_highlighted(self) -> None:
        prof = self._current_highlighted_profile()
        if prof is None:
            self.app.notify("列表为空，按 a 添加 profile", severity="information", timeout=2.5)
            return
        r = ping_profile(
            prof,
            trust_env=self._settings.http_trust_env,
            timeout_sec=min(15.0, float(self._settings.llm_timeout_sec)),
        )
        status = r.get("status")
        msg = (r.get("message") or "").strip()
        http = r.get("http_status")
        extra = f" http={http}" if http is not None else ""
        tail = f" {msg}" if msg else ""
        self.app.notify(f"{prof.id}: {status}{extra}{tail}", timeout=8.0)

    def action_add_profile(self) -> None:
        def _after_add(result: dict[str, Any] | None) -> None:
            if not result or not result.get("ok"):
                return
            preset = str(result.get("preset") or "")
            pid = str(result.get("pid") or "")
            model = str(result.get("model") or "")
            set_active = bool(result.get("set_active"))
            target = _toml_write_target(self._settings)
            base_profiles: tuple[Profile, ...] = (
                self._settings.profiles if self._settings.profiles_explicit else ()
            )
            base_active = (
                self._settings.active_profile_id if self._settings.profiles_explicit else None
            )
            try:
                raw = apply_preset({"id": pid, "model": model}, preset)
                new_p = build_profile(raw, hint=f"panel add {pid}")
                new_profiles = add_profile(base_profiles, new_p)
                next_active = _next_active_id(
                    base_active,
                    new_profiles,
                    prefer=new_p.id if set_active else None,
                )
                write_models_to_toml(
                    target,
                    new_profiles,
                    active=next_active,
                    subagent=self._settings.subagent_profile_id,
                    planner=self._settings.planner_profile_id,
                )
            except ProfilesError as e:
                self.app.notify(str(e), severity="error", timeout=8.0)
                return
            except OSError as e:
                self.app.notify(f"写入配置失败: {e}", severity="error", timeout=8.0)
                return
            self.app.notify(f"已写入 profile [cyan]{pid}[/]", timeout=3.0)
            self._refresh_after_disk_write()

        self.app.push_screen(ProfileAddFormScreen(), _after_add)

    def action_edit_profile(self) -> None:
        prof = self._current_highlighted_profile()
        if prof is None:
            self.app.notify("没有可编辑的条目", severity="warning")
            return

        def _after_edit(result: dict[str, Any] | None) -> None:
            if not result or not result.get("ok"):
                return
            if not self._settings.profiles_explicit:
                self.app.notify(
                    "当前为 [llm] 隐式 default profile；请先用 CLI "
                    "`cai-agent models add` 显式化后再在面板内编辑。",
                    severity="warning",
                    timeout=5.0,
                )
                return
            target = _toml_write_target(self._settings)
            try:
                new_profiles = edit_profile(
                    tuple(self._settings.profiles),
                    prof.id,
                    {
                        "model": result.get("model"),
                        "base_url": result.get("base_url"),
                        "notes": result.get("notes"),
                        "temperature": result.get("temperature"),
                    },
                )
                write_models_to_toml(
                    target,
                    new_profiles,
                    active=self._settings.active_profile_id,
                    subagent=self._settings.subagent_profile_id,
                    planner=self._settings.planner_profile_id,
                )
            except ProfilesError as e:
                self.app.notify(str(e), severity="error", timeout=8.0)
                return
            except OSError as e:
                self.app.notify(f"写入配置失败: {e}", severity="error", timeout=8.0)
                return
            self.app.notify(f"已更新 profile [cyan]{prof.id}[/]", timeout=3.0)
            self._refresh_after_disk_write()

        self.app.push_screen(ProfileEditFormScreen(prof), _after_edit)

    def action_delete_profile(self) -> None:
        prof = self._current_highlighted_profile()
        if prof is None:
            self.app.notify("没有可删除的条目", severity="warning")
            return
        if len(self._settings.profiles) <= 1:
            self.app.notify("不能删除最后一个 profile", severity="warning", timeout=3.5)
            return
        if not self._settings.profiles_explicit:
            self.app.notify(
                "隐式 default profile 不能在此删除；请编辑 cai-agent.toml 或先用 CLI 显式化。",
                severity="warning",
                timeout=5.0,
            )
            return

        def _after_del(ok: bool) -> None:
            if not ok:
                return
            target = _toml_write_target(self._settings)
            try:
                new_profiles = remove_profile(tuple(self._settings.profiles), prof.id)
                next_active = _next_active_id(
                    self._settings.active_profile_id,
                    new_profiles,
                    prefer=None,
                )
                write_models_to_toml(
                    target,
                    new_profiles,
                    active=next_active,
                    subagent=self._settings.subagent_profile_id,
                    planner=self._settings.planner_profile_id,
                )
            except ProfilesError as e:
                self.app.notify(str(e), severity="error", timeout=8.0)
                return
            except OSError as e:
                self.app.notify(f"写入配置失败: {e}", severity="error", timeout=8.0)
                return
            self.app.notify(f"已删除 [cyan]{prof.id}[/]", timeout=3.0)
            self._refresh_after_disk_write()

        self.app.push_screen(ConfirmDeleteScreen(prof.id), _after_del)
