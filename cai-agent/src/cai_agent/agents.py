from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Literal

from cai_agent.config import Settings
from cai_agent.graph import AgentState, build_app, initial_state


AgentRole = Literal["default", "explorer", "reviewer", "security"]


@dataclass(frozen=True)
class AgentConfig:
    """轻量级 Agent 配置，用于区分不同子 Agent 的行为倾向。

    当前实现主要通过 system prompt 与 max_iterations 约束行为，
    避免对现有 LangGraph 状态机做侵入式修改。
    """

    role: AgentRole = "default"
    max_iterations: int | None = None


@dataclass
class Agent:
    """对 LangGraph 编译结果的轻量封装。

    - 默认复用现有 `build_app` / `initial_state`
    - 通过 AgentConfig 传入角色信息，后续可在 system prompt 中使用
    """

    settings: Settings
    config: AgentConfig
    progress: Callable[[dict[str, Any]], None] | None = None

    def _effective_settings(self) -> Settings:
        """返回当前 Agent 的实际运行配置。"""

        base = self.settings
        if (
            self.config.max_iterations is not None
            and self.config.max_iterations != base.max_iterations
        ):
            from dataclasses import replace

            return replace(base, max_iterations=self.config.max_iterations)
        return base

    def _build_state(self, goal: str) -> AgentState:
        base = self._effective_settings()
        state = initial_state(base, goal)
        # 角色信息仅作为 metadata 附在第一条 user message 上，便于后续扩展。
        if state["messages"] and self.config.role != "default":
            first_user = state["messages"][1]
            if isinstance(first_user, dict) and first_user.get("role") == "user":
                meta_prefix = f"[agent_role={self.config.role}] "
                content = str(first_user.get("content", ""))
                if not content.startswith(meta_prefix):
                    first_user["content"] = meta_prefix + content
        return state

    def run(self, goal: str) -> dict[str, Any]:
        """执行单轮任务并返回最终状态字典。

        非 default 角色默认走 ``subagent`` profile 路由；若未配置 subagent，
        ``llm_factory`` 会回退到 active，和历史行为等价。
        """

        effective = self._effective_settings()
        role_route = "subagent" if self.config.role != "default" else "active"
        app = build_app(effective, progress=self.progress, role=role_route)
        state = self._build_state(goal)
        final = app.invoke(state)
        return final


def create_agent(
    settings: Settings,
    role: AgentRole = "default",
    *,
    max_iterations: int | None = None,
    progress: Callable[[dict[str, Any]], None] | None = None,
) -> Agent:
    """工厂方法：为不同角色创建预设 Agent。

    - explorer: 偏向只读探索，可在后续版本中结合只读工具白名单
    - reviewer: 代码审查/重构建议
    - security: 安全审计相关任务
    """

    cfg = AgentConfig(role=role, max_iterations=max_iterations)
    return Agent(settings=settings, config=cfg, progress=progress)

