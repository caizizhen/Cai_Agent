"""TUI：模型 profile 列表面板（M4 最小可用版）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Footer, OptionList, Static
from textual.widgets.option_list import Option

from cai_agent.models import ping_profile
from cai_agent.profiles import Profile

if TYPE_CHECKING:
    from cai_agent.config import Settings


def _profile_row(p: Profile, *, active_id: str) -> str:
    mark = "[active] " if p.id == active_id else ""
    notes = (p.notes or "").strip().replace("\n", " ")
    if len(notes) > 40:
        notes = notes[:37] + "..."
    tail = f"  |  {notes}" if notes else ""
    return f"{mark}{p.id}  |  {p.provider}  |  {p.model}{tail}"


class ModelPanelScreen(ModalScreen[str | None]):
    """列出 ``Settings.profiles``；Enter 选中一条 profile id 并 ``dismiss``；Esc 放弃。"""

    BINDINGS = [
        Binding("escape", "dismiss", "关闭", show=True),
        Binding("t", "ping_highlighted", "测试", show=True, priority=True),
    ]

    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self._settings = settings

    def _header_text(self) -> str:
        s = self._settings
        sub = getattr(s, "subagent_profile_id", None) or "-"
        pln = getattr(s, "planner_profile_id", None) or "-"
        return (
            f"active={s.active_profile_id}  subagent={sub}  planner={pln}\n"
            "Enter 切换（仅内存，不写 cai-agent.toml） · t 连通测试 · Esc 关闭"
        )

    def compose(self) -> ComposeResult:
        yield Static(self._header_text(), id="model-panel-header")
        opts = [
            Option(_profile_row(p, active_id=self._settings.active_profile_id), id=p.id)
            for p in self._settings.profiles
        ]
        yield OptionList(*opts, id="model-panel-list")
        yield Footer()

    def on_mount(self) -> None:
        ol = self.query_one("#model-panel-list", OptionList)
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
        ol = self.query_one("#model-panel-list", OptionList)
        try:
            opt = ol.get_option_at_index(ol.highlighted)
        except Exception:
            self.app.notify("无法读取当前选项", severity="warning")
            return
        if opt is None or not opt.id:
            return
        prof = next((p for p in self._settings.profiles if p.id == opt.id), None)
        if prof is None:
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
        self.app.notify(f"{opt.id}: {status}{extra}{tail}", timeout=8.0)
