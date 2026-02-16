"""Cancel subagents tool for stopping running subagents."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from nanobot.agent.tools.base import Tool

if TYPE_CHECKING:
    from nanobot.agent.subagent import SubagentManager


class CancelSubagentsTool(Tool):
    """Tool to cancel running subagents."""

    def __init__(self, manager: "SubagentManager"):
        self._manager = manager

    @property
    def name(self) -> str:
        return "cancel_subagent"

    @property
    def description(self) -> str:
        return (
            "Cancel a running subagent by its task ID. "
            "Use list_subagents to see running subagents and their IDs."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "The task ID of the subagent to cancel",
                },
            },
            "required": ["task_id"],
        }

    async def execute(self, task_id: str, **kwargs: Any) -> str:
        """Cancel a subagent."""
        success = await self._manager.cancel(task_id)

        if success:
            return f"✅ Subagent [{task_id}] cancellation requested."
        else:
            # List available task IDs
            tasks = self._manager.get_running_tasks()
            available = [t.task_id for t in tasks]
            return f"❌ Task '{task_id}' not found. Available task IDs: {', '.join(available) or 'none'}"
