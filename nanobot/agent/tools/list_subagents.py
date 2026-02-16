"""List subagents tool for checking running subagent status."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from nanobot.agent.tools.base import Tool

if TYPE_CHECKING:
    from nanobot.agent.subagent import SubagentManager


class ListSubagentsTool(Tool):
    """Tool to list running and recently completed subagents."""

    def __init__(self, manager: "SubagentManager"):
        self._manager = manager

    @property
    def name(self) -> str:
        return "list_subagents"

    @property
    def description(self) -> str:
        return (
            "List all running and recently completed subagents with detailed status. "
            "Shows task ID, label, task description, profile, status, iteration count, "
            "last activity time, result/error message, and completion time."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "Optional specific task ID to get detailed information for",
                },
            },
            "required": [],
        }

    async def execute(self, task_id: str | None = None, **kwargs: Any) -> str:
        """List all subagents or get details for a specific task."""
        tasks = self._manager.get_running_tasks()

        if not tasks:
            return "No subagents running or recently completed."

        # If specific task requested
        if task_id:
            task = next((t for t in tasks if t.task_id == task_id), None)
            if not task:
                return f"Task '{task_id}' not found. Available IDs: {', '.join(t.task_id for t in tasks)}"
            return self._format_task_detail(task)

        # List all tasks
        lines = [f"📋 Subagents ({len(tasks)} total)\n"]

        # Group by status
        running = [t for t in tasks if t.status == "running"]
        completed = [t for t in tasks if t.status == "completed"]
        failed = [t for t in tasks if t.status in ("failed", "cancelled")]

        if running:
            lines.append("## Running")
            for task in running:
                elapsed = (task.last_activity - task.created_at).total_seconds()
                profile_text = f" [{task.profile}]" if task.profile else ""
                lines.append(f"  [{task.task_id}] {task.label}{profile_text}")
                lines.append(f"      Status: {task.status} | Iteration: {task.iteration} | Elapsed: {elapsed:.1f}s")
                # Show task description
                task_preview = task.task[:60] + "..." if len(task.task) > 60 else task.task
                lines.append(f"      Task: {task_preview}")
            lines.append("")

        if completed:
            lines.append("## Completed")
            for task in completed:
                profile_text = f" [{task.profile}]" if task.profile else ""
                lines.append(f"  [{task.task_id}] {task.label}{profile_text}")
                if task.completed_at:
                    duration = (task.completed_at - task.created_at).total_seconds()
                    lines.append(f"      Completed in: {duration:.1f}s")
                # Show result preview
                if task.result:
                    result_preview = task.result[:80] + "..." if len(task.result) > 80 else task.result
                    lines.append(f"      Result: {result_preview}")
            lines.append("")

        if failed:
            lines.append("## Failed/Cancelled")
            for task in failed:
                profile_text = f" [{task.profile}]" if task.profile else ""
                lines.append(f"  [{task.task_id}] {task.label}{profile_text} ({task.status})")
                # Show error
                if task.error:
                    error_preview = task.error[:80] + "..." if len(task.error) > 80 else task.error
                    lines.append(f"      Error: {error_preview}")
            lines.append("")

        return "\n".join(lines)

    def _format_task_detail(self, task) -> str:
        """Format detailed information for a single task."""
        lines = [
            f"📋 Subagent Task: {task.label}",
            f"",
            f"Task ID: {task.task_id}",
            f"Status: {task.status}",
            f"Profile: {task.profile or 'default'}",
            f"Created: {task.created_at.strftime('%Y-%m-%d %H:%M:%S')}",
        ]

        if task.completed_at:
            lines.append(f"Completed: {task.completed_at.strftime('%Y-%m-%d %H:%M:%S')}")
            duration = (task.completed_at - task.created_at).total_seconds()
            lines.append(f"Duration: {duration:.1f}s")
        else:
            elapsed = (task.last_activity - task.created_at).total_seconds()
            lines.append(f"Elapsed: {elapsed:.1f}s")
            lines.append(f"Iteration: {task.iteration}")

        lines.extend([
            f"",
            f"Task Description:",
            f"  {task.task}",
        ])

        if task.result:
            lines.extend([
                f"",
                f"Result:",
                f"  {task.result}",
            ])

        if task.error:
            lines.extend([
                f"",
                f"Error:",
                f"  {task.error}",
            ])

        return "\n".join(lines)
