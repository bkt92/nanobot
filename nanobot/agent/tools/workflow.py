"""Advanced workflow tools for pipeline and hybrid agent patterns."""

import asyncio
from typing import Any, TYPE_CHECKING

from nanobot.agent.tools.base import Tool

if TYPE_CHECKING:
    from nanobot.agent.subagent import SubagentManager


class AwaitAgentTool(Tool):
    """Tool to wait for a specific subagent to complete."""

    def __init__(self, manager: "SubagentManager"):
        self._manager = manager

    @property
    def name(self) -> str:
        return "await_agent"

    @property
    def description(self) -> str:
        return (
            "Wait for a specific subagent to complete and return its result. "
            "Use this for pipeline patterns where the next step depends on a previous agent's output."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "The task ID of the subagent to wait for (from spawn result)",
                },
                "timeout": {
                    "type": "number",
                    "description": "Maximum wait time in seconds (default: 300)",
                },
            },
            "required": ["task_id"],
        }

    async def execute(self, task_id: str, timeout: float = 300, **kwargs: Any) -> str:
        """Wait for a subagent to complete."""
        try:
            completed_task = await self._manager.await_agent(task_id, timeout)

            if completed_task.status == "completed":
                return f"Agent {completed_task.label} completed successfully.\n\nResult:\n{completed_task.result}"
            elif completed_task.status == "failed":
                return f"Agent {completed_task.label} failed.\n\nError: {completed_task.error}"
            elif completed_task.status == "cancelled":
                return f"Agent {completed_task.label} was cancelled."
            else:
                return f"Agent {completed_task.label} status: {completed_task.status}"

        except ValueError as e:
            return f"Error: {e}"
        except asyncio.TimeoutError:
            return f"Timeout: Agent {task_id} did not complete within {timeout} seconds"


class GetAgentResultTool(Tool):
    """Tool to get the result from a completed subagent."""

    def __init__(self, manager: "SubagentManager"):
        self._manager = manager

    @property
    def name(self) -> str:
        return "get_agent_result"

    @property
    def description(self) -> str:
        return (
            "Get the result from a completed subagent without waiting. "
            "Use this to retrieve outputs for passing to other agents."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "The task ID of the completed subagent",
                },
            },
            "required": ["task_id"],
        }

    async def execute(self, task_id: str, **kwargs: Any) -> str:
        """Get result from a completed subagent."""
        result = self._manager.get_agent_result(task_id)

        if result is None:
            state = self._manager._task_states.get(task_id)
            if state:
                if state.status == "running":
                    return f"Agent {task_id} is still running. Use await_agent() to wait for it."
                else:
                    return f"Agent {task_id} {state.status}. No result available."
            return f"Agent {task_id} not found."

        return f"Result from agent {task_id}:\n\n{result}"


class ParallelGroupTool(Tool):
    """Tool to create a parallel group of subagents."""

    def __init__(self, manager: "SubagentManager"):
        self._manager = manager

    @property
    def name(self) -> str:
        return "parallel_group"

    @property
    def description(self) -> str:
        return (
            "Spawn multiple subagents in parallel as a named group. "
            "Use await_group() to wait for all agents in the group to complete."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "group_id": {
                    "type": "string",
                    "description": "Unique identifier for this group (e.g., 'research_phase_1')",
                },
                "tasks": {
                    "type": "array",
                    "description": "List of tasks to execute in parallel",
                    "items": {
                        "type": "object",
                        "properties": {
                            "task": {"type": "string", "description": "The task description"},
                            "label": {"type": "string", "description": "Short label"},
                            "profile": {"type": "string", "description": "Agent profile to use"},
                        },
                        "required": ["task", "label"],
                    },
                },
            },
            "required": ["group_id", "tasks"],
        }

    async def execute(self, group_id: str, tasks: list[dict[str, Any]], **kwargs: Any) -> str:
        """Create a parallel group of subagents."""
        try:
            import asyncio
            task_ids = await self._manager.create_parallel_group(group_id, tasks)

            return f"""Spawned {len(task_ids)} agents in parallel group '{group_id}':

Task IDs: {', '.join(task_ids)}

Use: await_group(group_id="{group_id}") to wait for all to complete.
Use: list_subagents() to check status."""
        except Exception as e:
            return f"Error creating parallel group: {e}"


class AwaitGroupTool(Tool):
    """Tool to wait for all agents in a parallel group."""

    def __init__(self, manager: "SubagentManager"):
        self._manager = manager

    @property
    def name(self) -> str:
        return "await_group"

    @property
    def description(self) -> str:
        return (
            "Wait for all agents in a parallel group to complete. "
            "Returns results from all agents in the group."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "group_id": {
                    "type": "string",
                    "description": "The group ID to wait for",
                },
                "timeout": {
                    "type": "number",
                    "description": "Maximum wait time in seconds (default: 600)",
                },
            },
            "required": ["group_id"],
        }

    async def execute(self, group_id: str, timeout: float = 600, **kwargs: Any) -> str:
        """Wait for a parallel group to complete."""
        try:
            completed_tasks = await self._manager.await_group(group_id, timeout)

            results = []
            for task in completed_tasks:
                if task.status == "completed":
                    results.append(f"✓ {task.label}: {task.result[:100]}...")
                else:
                    results.append(f"✗ {task.label}: {task.status} - {task.error or 'Failed'}")

            return f"""Group '{group_id}' completed ({len(completed_tasks)} agents):

{chr(10).join(results)}"""
        except ValueError as e:
            return f"Error: {e}"
        except asyncio.TimeoutError:
            return f"Timeout: Group '{group_id}' did not complete within {timeout} seconds"


class SpawnChainTool(Tool):
    """Tool to execute a pipeline of sequential agents."""

    def __init__(self, manager: "SubagentManager"):
        self._manager = manager

    @property
    def name(self) -> str:
        return "spawn_chain"

    @property
    def description(self) -> str:
        return (
            "Execute a chain of tasks sequentially (pipeline pattern). "
            "Each task waits for the previous one to complete. "
            "Results from previous tasks can be passed to subsequent tasks."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "tasks": {
                    "type": "array",
                    "description": "List of tasks to execute in sequence",
                    "items": {
                        "type": "object",
                        "properties": {
                            "task": {"type": "string", "description": "The task description"},
                            "label": {"type": "string", "description": "Short label"},
                            "profile": {"type": "string", "description": "Agent profile to use"},
                            "use_result": {
                                "type": "boolean",
                                "description": "Include previous result in task context",
                            },
                        },
                        "required": ["task", "label"],
                    },
                },
            },
            "required": ["tasks"],
        }

    async def execute(self, tasks: list[dict[str, Any]], **kwargs: Any) -> str:
        """Execute a chain of tasks sequentially."""
        try:
            completed_tasks = await self._manager.spawn_chain(tasks)

            results = []
            for task in completed_tasks:
                if task.status == "completed":
                    results.append(f"✓ {task.label}: {task.result[:100]}...")
                else:
                    results.append(f"✗ {task.label}: {task.status}")

            return f"""Pipeline completed ({len(completed_tasks)} steps):

{chr(10).join(results)}"""
        except Exception as e:
            return f"Error in pipeline execution: {e}"


class WaitAllTool(Tool):
    """Tool to wait for multiple agents with flexible conditions."""

    def __init__(self, manager: "SubagentManager"):
        self._manager = manager

    @property
    def name(self) -> str:
        return "wait_all"

    @property
    def description(self) -> str:
        return (
            "Wait for multiple agents with flexible conditions. "
            "Can wait for ALL agents or ANY agent to complete."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of task IDs to wait for",
                },
                "mode": {
                    "type": "string",
                    "enum": ["all", "any"],
                    "description": "Wait for 'all' (everyone) or 'any' (first completion)",
                },
                "timeout": {
                    "type": "number",
                    "description": "Maximum wait time in seconds (default: 600)",
                },
            },
            "required": ["task_ids", "mode"],
        }

    async def execute(
        self,
        task_ids: list[str],
        mode: str,
        timeout: float = 600,
        **kwargs: Any
    ) -> str:
        """Wait for multiple agents."""
        try:
            results = await self._manager.wait_all(task_ids, mode, timeout)

            status_summary = []
            for tid, task in results.items():
                if task.status == "completed":
                    status_summary.append(f"✓ {tid} ({task.label}): completed")
                elif task.status == "running":
                    status_summary.append(f"⏳ {tid} ({task.label}): still running")
                else:
                    status_summary.append(f"✗ {tid} ({task.label}): {task.status}")

            return f"""Wait condition '{mode}' met:

{chr(10).join(status_summary)}"""
        except ValueError as e:
            return f"Error: {e}"
        except asyncio.TimeoutError:
            return f"Timeout: Tasks did not complete within {timeout} seconds"
