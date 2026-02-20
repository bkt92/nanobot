"""Team Manager skill for orchestrating multi-agent workflows.

This skill enables the main agent to act as a project manager,
spawning and coordinating multiple subagents to complete complex tasks.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from nanobot.agent.tools.base import Tool


class TeamManagerSkill:
    """Team Manager skill for multi-agent orchestration."""

    def __init__(self, workspace: str | Path = "."):
        self.workspace = Path(workspace)
        self.plans_dir = self.workspace / "team_manager" / "plans"
        self.plans_dir.mkdir(parents=True, exist_ok=True)

    def get_tools(self) -> list[type[Tool]]:
        """Return the tools provided by this skill."""
        return [
            CreatePlanTool,
            SpawnAgentTool,
            WaitForAgentsTool,
            SynthesizeResultsTool,
            ListProfilesTool,
        ]


class CreatePlanTool(Tool):
    """Tool to create an execution plan for multi-agent workflows."""

    @property
    def name(self) -> str:
        return "create_plan"

    @property
    def description(self) -> str:
        return (
            "Create a structured execution plan for a complex task. "
            "Break down the task into steps, identify what needs to be done in parallel vs sequential, "
            "and specify which agent profiles should handle each step. "
            "This helps orchestrate multiple subagents effectively."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "goal": {
                    "type": "string",
                    "description": "The main goal/objective to achieve",
                },
                "steps": {
                    "type": "array",
                    "description": "List of steps in the execution plan",
                    "items": {
                        "type": "object",
                        "properties": {
                            "step_id": {"type": "string", "description": "Unique step identifier"},
                            "description": {"type": "string", "description": "What this step does"},
                            "profile": {"type": "string", "description": "Agent profile to use (optional)"},
                            "depends_on": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Step IDs that must complete first (optional)",
                            },
                            "parallel_group": {
                                "type": "string",
                                "description": "Group ID for parallel execution (optional)",
                            },
                        },
                        "required": ["step_id", "description"],
                    },
                },
                "todo_list": {
                    "type": "string",
                    "description": "Todo list name to track progress (e.g., 'team_manager/project_x')",
                },
            },
            "required": ["goal", "steps"],
        }

    async def execute(
        self,
        goal: str,
        steps: list[dict[str, Any]],
        todo_list: str | None = None,
        **kwargs: Any,
    ) -> str:
        """Create an execution plan."""
        plan = {
            "goal": goal,
            "created_at": datetime.now().isoformat(),
            "steps": steps,
            "status": "planned",
        }

        # Save plan
        plan_id = goal.lower().replace(" ", "_")[:30]
        plan_file = self.plans_dir / f"{plan_id}.json"

        try:
            with open(plan_file, "w") as f:
                json.dump(plan, f, indent=2)

            # Create todo list if specified
            todo_info = ""
            if todo_list:
                todo_info = f"\n\nTodo list: {todo_list}"

            return f"""✓ Execution plan created: {plan_id}

Goal: {goal}
Steps: {len(steps)}

Execution flow:
{self._format_plan(steps)}

Plan saved to: {plan_file}{todo_info}

Use spawn_agent() to start executing steps."""
        except Exception as e:
            return f"Error creating plan: {e}"

    def _format_plan(self, steps: list[dict[str, Any]]) -> str:
        """Format the execution plan for display."""
        lines = []
        for step in steps:
            deps = f" (after: {step.get('depends_on', [])})" if step.get("depends_on") else ""
            parallel = f" [parallel: {step.get('parallel_group')}]" if step.get("parallel_group") else ""
            profile = f" [{step.get('profile', 'default')}]" if step.get("profile") else ""
            lines.append(f"  • {step['step_id']}{profile}{deps}{parallel}: {step['description']}")
        return "\n".join(lines)


class SpawnAgentTool(Tool):
    """Tool to spawn a subagent with a specific task."""

    @property
    def name(self) -> str:
        return "spawn_agent"

    @property
    def description(self) -> str:
        return (
            "Spawn a subagent to handle a specific task. "
            "The subagent runs asynchronously and reports back when complete. "
            "Use this for parallel execution or delegating specialized work."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "The task for the subagent to complete",
                },
                "label": {
                    "type": "string",
                    "description": "Short label for this subagent (e.g., 'Research Topic A')",
                },
                "profile": {
                    "type": "string",
                    "description": "Agent profile to use (e.g., 'researcher', 'coder', 'writer'). Use list_profiles to see available.",
                },
                "context": {
                    "type": "string",
                    "description": "Additional context or input data for the subagent (optional)",
                },
            },
            "required": ["task", "label"],
        }

    async def execute(
        self,
        task: str,
        label: str,
        profile: str | None = None,
        context: str | None = None,
        **kwargs: Any,
    ) -> str:
        """Spawn a subagent with the given task."""
        # This is a wrapper around the spawn tool
        # The actual spawn will be handled by the spawn tool
        # This tool adds metadata for team management
        full_task = task
        if context:
            full_task = f"{context}\n\nTask: {task}"

        if profile:
            return f"Spawn subagent with profile '{profile}':\n  Label: {label}\n  Task: {full_task}"
        else:
            return f"Spawn subagent:\n  Label: {label}\n  Task: {full_task}"


class WaitForAgentsTool(Tool):
    """Tool to wait for specific subagents to complete."""

    @property
    def name(self) -> str:
        return "wait_for_agents"

    @property
    def description(self) -> str:
        return (
            "Check the status of running subagents and wait for specific ones to complete. "
            "Use this to synchronize workflow steps - ensure required agents finish before proceeding."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "step_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Step IDs or agent labels to wait for",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Maximum wait time in seconds (default: 300)",
                },
            },
            "required": ["step_ids"],
        }

    async def execute(
        self,
        step_ids: list[str],
        timeout: int = 300,
        **kwargs: Any,
    ) -> str:
        """Wait for specified agents to complete."""
        return f"Waiting for agents: {', '.join(step_ids)}. Use list_subagents() to check status."


class SynthesizeResultsTool(Tool):
    """Tool to synthesize results from multiple agents."""

    @property
    def name(self) -> str:
        return "synthesize_results"

    @property
    def description(self) -> str:
        return (
            "Combine and synthesize results from multiple subagents into a coherent output. "
            "Use this after parallel agents have completed to merge their work."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "results": {
                    "type": "array",
                    "description": "Array of results from different agents",
                    "items": {
                        "type": "object",
                        "properties": {
                            "source": {"type": "string", "description": "Agent/step name"},
                            "content": {"type": "string", "description": "Result content"},
                        },
                    },
                },
                "output_format": {
                    "type": "string",
                    "description": "Desired output format (e.g., 'report', 'table', 'summary', 'code')",
                },
                "output_file": {
                    "type": "string",
                    "description": "File path to save synthesized output (optional)",
                },
            },
            "required": ["results", "output_format"],
        }

    async def execute(
        self,
        results: list[dict[str, Any]],
        output_format: str,
        output_file: str | None = None,
        **kwargs: Any,
    ) -> str:
        """Synthesize results from multiple agents."""
        synthesis = f"""Synthesize the following results into a {output_format}:

"""
        for i, result in enumerate(results, 1):
            source = result.get("source", f"Agent {i}")
            content = result.get("content", "")
            synthesis += f"\n## {source}\n\n{content}\n"

        if output_file:
            synthesis += f"\n\nOutput should be saved to: {output_file}"

        return synthesis


class ListProfilesTool(Tool):
    """Tool to list available agent profiles."""

    @property
    def name(self) -> str:
        return "list_profiles"

    @property
    def description(self) -> str:
        return "List all available agent profiles that can be used when spawning subagents."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
        }

    async def execute(self, **kwargs: Any) -> str:
        """List available profiles."""
        return "Use the list_profiles tool to see available agent profiles."
