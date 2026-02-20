"""Subagent manager for background task execution."""

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from nanobot.bus.events import InboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.providers.base import LLMProvider
from nanobot.agent.tools.registry import ToolRegistry
from nanobot.agent.tools.filesystem import ReadFileTool, WriteFileTool, EditFileTool, ListDirTool
from nanobot.agent.tools.shell import ExecTool
from nanobot.agent.tools.web import WebSearchTool, WebFetchTool


@dataclass
class SubagentTask:
    """Represents a subagent task with state tracking."""
    task_id: str
    label: str
    task: str
    profile: str | None = None
    status: str = "running"  # running, completed, failed, cancelled
    iteration: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None
    result: str | None = None
    error: str | None = None
    origin_channel: str = "cli"
    origin_chat_id: str = "direct"


class SubagentManager:
    """
    Manages background subagent execution.

    Subagents are lightweight agent instances that run in the background
    to handle specific tasks. They share the same LLM provider but have
    isolated context and a focused system prompt.
    """

    def __init__(
        self,
        provider: LLMProvider,
        workspace: Path,
        bus: MessageBus,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        brave_api_key: str | None = None,
        exec_config: "ExecToolConfig | None" = None,
        restrict_to_workspace: bool = False,
        config: "Config | None" = None,
    ):
        from nanobot.config.schema import ExecToolConfig, Config
        self.provider = provider
        self.workspace = workspace
        self.bus = bus
        self.model = model or provider.get_default_model()
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.brave_api_key = brave_api_key
        self.exec_config = exec_config or ExecToolConfig()
        self.restrict_to_workspace = restrict_to_workspace
        self.config = config
        self._running_tasks: dict[str, asyncio.Task[None]] = {}
        self._task_states: dict[str, SubagentTask] = {}  # Track task state

    async def spawn(
        self,
        task: str,
        label: str | None = None,
        origin_channel: str = "cli",
        origin_chat_id: str = "direct",
        profile: "AgentProfile | None" = None,
    ) -> str:
        """
        Spawn a subagent to execute a task in the background.

        Args:
            task: The task description for the subagent.
            label: Optional human-readable label for the task.
            origin_channel: The channel to announce results to.
            origin_chat_id: The chat ID to announce results to.
            profile: Optional agent profile to use for this subagent.

        Returns:
            Status message indicating the subagent was started.
        """
        task_id = str(uuid.uuid4())[:8]
        display_label = label or task[:30] + ("..." if len(task) > 30 else "")

        # Get profile name if profile object provided
        profile_name = None
        if profile:
            # Find profile name from config
            if self.config:
                for name, p in self.config.agents.profiles.items():
                    if p == profile:
                        profile_name = name
                        break

        # Create task state
        task_state = SubagentTask(
            task_id=task_id,
            label=display_label,
            task=task,
            profile=profile_name,
            origin_channel=origin_channel,
            origin_chat_id=origin_chat_id,
        )
        self._task_states[task_id] = task_state

        origin = {
            "channel": origin_channel,
            "chat_id": origin_chat_id,
        }

        # Create background task
        bg_task = asyncio.create_task(
            self._run_subagent(task_id, task, display_label, origin, profile)
        )
        self._running_tasks[task_id] = bg_task

        # Cleanup when done
        def cleanup(_: asyncio.Task) -> None:
            self._running_tasks.pop(task_id, None)
            # Keep task state for history (don't delete immediately)

        bg_task.add_done_callback(cleanup)

        logger.info("Spawned subagent [{}]: {}", task_id, display_label)
        return f"Subagent [{display_label}] started (id: {task_id}). I'll notify you when it completes."

    def get_running_tasks(self) -> list[SubagentTask]:
        """Get all tracked tasks (running and recently completed)."""
        # Clean up very old completed tasks (older than 1 hour)
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(hours=1)
        self._task_states = {
            k: v for k, v in self._task_states.items()
            if v.status == "running" or v.completed_at and v.completed_at > cutoff
        }
        return list(self._task_states.values())

    async def cancel(self, task_id: str) -> bool:
        """Cancel a running subagent by task ID."""
        task = self._running_tasks.get(task_id)
        if not task:
            return False

        task.cancel()
        # Update state
        if task_id in self._task_states:
            self._task_states[task_id].status = "cancelled"
            self._task_states[task_id].completed_at = datetime.now()
            self._task_states[task_id].error = "Cancelled by user"

        logger.info("Subagent [{}] cancelled", task_id)
        return True
    
    async def _run_subagent(
        self,
        task_id: str,
        task: str,
        label: str,
        origin: dict[str, str],
        profile: "AgentProfile | None" = None,
    ) -> None:
        """Execute the subagent task and announce the result."""
        logger.info("Subagent [{}] starting task: {}", task_id, label)

        task_state = self._task_states.get(task_id)
        if not task_state:
            logger.error("Subagent [{}] task state not found", task_id)
            return

        try:
            # Resolve model and temperature from profile if provided
            model = self.model
            temperature = self.temperature
            max_tokens = self.max_tokens

            if profile:
                model = profile.model or model
                temperature = profile.temperature or temperature
                max_tokens = profile.max_tokens or max_tokens

            # Build subagent tools (no message tool, no spawn tool)
            tools = ToolRegistry()
            allowed_dir = self.workspace if self.restrict_to_workspace else None
            tools.register(ReadFileTool(workspace=self.workspace, allowed_dir=allowed_dir))
            tools.register(WriteFileTool(workspace=self.workspace, allowed_dir=allowed_dir))
            tools.register(EditFileTool(workspace=self.workspace, allowed_dir=allowed_dir))
            tools.register(ListDirTool(workspace=self.workspace, allowed_dir=allowed_dir))
            tools.register(ExecTool(
                working_dir=str(self.workspace),
                timeout=self.exec_config.timeout,
                restrict_to_workspace=self.restrict_to_workspace,
            ))
            tools.register(WebSearchTool(api_key=self.brave_api_key))
            tools.register(WebFetchTool())

            # Build messages with subagent-specific prompt
            system_prompt = self._build_subagent_prompt(task, profile)
            messages: list[dict[str, Any]] = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": task},
            ]

            # Run agent loop (limited iterations)
            max_iterations = 15
            iteration = 0
            final_result: str | None = None

            while iteration < max_iterations:
                iteration += 1

                # Update task state
                if task_id in self._task_states:
                    self._task_states[task_id].iteration = iteration
                    self._task_states[task_id].last_activity = datetime.now()

                response = await self.provider.chat(
                    messages=messages,
                    tools=tools.get_definitions(),
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )

                if response.has_tool_calls:
                    # Add assistant message with tool calls
                    tool_call_dicts = [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                            },
                        }
                        for tc in response.tool_calls
                    ]
                    messages.append({
                        "role": "assistant",
                        "content": response.content or "",
                        "tool_calls": tool_call_dicts,
                    })

                    # Execute tools
                    for tool_call in response.tool_calls:
                        args_str = json.dumps(tool_call.arguments, ensure_ascii=False)
                        logger.debug("Subagent [{}] executing: {} with arguments: {}", task_id, tool_call.name, args_str)
                        result = await tools.execute(tool_call.name, tool_call.arguments)
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": tool_call.name,
                            "content": result,
                        })
                else:
                    final_result = response.content
                    break

            if final_result is None:
                final_result = "Task completed but no final response was generated."

            logger.info("Subagent [{}] completed successfully", task_id)

            # Update task state
            if task_id in self._task_states:
                self._task_states[task_id].status = "completed"
                self._task_states[task_id].completed_at = datetime.now()
                self._task_states[task_id].result = final_result[:1000]  # Store first 1000 chars

            await self._announce_result(task_id, label, task, final_result, origin, "ok")

        except asyncio.CancelledError:
            logger.info("Subagent [{}] was cancelled", task_id)
            if task_id in self._task_states:
                self._task_states[task_id].status = "cancelled"
                self._task_states[task_id].completed_at = datetime.now()
                self._task_states[task_id].error = "Cancelled"
            await self._announce_result(task_id, label, task, "Task was cancelled", origin, "cancelled")
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            logger.error("Subagent [{}] failed: {}", task_id, e)
            if task_id in self._task_states:
                self._task_states[task_id].status = "failed"
                self._task_states[task_id].completed_at = datetime.now()
                self._task_states[task_id].error = error_msg[:500]
            await self._announce_result(task_id, label, task, error_msg, origin, "error")

    def _build_subagent_prompt(self, task: str, profile: "AgentProfile | None" = None) -> str:
        """Build a focused system prompt for the subagent."""
        from datetime import datetime
        import time as _time
        now = datetime.now().strftime("%Y-%m-%d %H:%M (%A)")
        tz = _time.strftime("%Z") or "UTC"

        # Build custom prompt section if profile has one
        custom_prompt = ""
        if profile and profile.system_prompt:
            if profile.inherit_base_prompt:
                custom_prompt = f"\n\n## Additional Instructions\n{profile.system_prompt}"
            else:
                custom_prompt = f"\n\n{profile.system_prompt}\n\n---\n\n"

        return f"""# Subagent

## Current Time
{now} ({tz})

You are a subagent spawned by the main agent to complete a specific task.{custom_prompt}

## Rules
1. Stay focused - complete only the assigned task, nothing else
2. Your final response will be reported back to the main agent
3. Do not initiate conversations or take on side tasks
4. Be concise but informative in your findings

## What You Can Do
- Read and write files in the workspace
- Execute shell commands
- Search the web and fetch web pages
- Complete the task thoroughly

## What You Cannot Do
- Send messages directly to users (no message tool available)
- Spawn other subagents
- Access the main agent's conversation history

## Workspace
Your workspace is at: {self.workspace}
Skills are available at: {self.workspace}/skills/ (read SKILL.md files as needed)

When you have completed the task, provide a clear summary of your findings or actions."""

    def get_running_count(self) -> int:
        """Return the number of currently running subagents."""
        return len(self._running_tasks)
