"""Subagent manager for background task execution."""

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger


@dataclass
class SubagentTaskInfo:
    """Information about a running subagent task."""
    task_id: str
    label: str
    task: str
    status: str = "running"  # running, completed, failed, cancelled
    created_at: datetime = field(default_factory=datetime.now)
    origin: dict[str, str] = field(default_factory=dict)
    iteration: int = 0
    last_activity: datetime = field(default_factory=datetime.now)
    profile: str | None = None
    result: str | None = None  # Final result when completed
    error: str | None = None  # Error message if failed
    completed_at: datetime | None = None  # When task finished

from nanobot.bus.events import InboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.providers.base import LLMProvider
from nanobot.agent.tools.registry import ToolRegistry
from nanobot.agent.tools.filesystem import ReadFileTool, WriteFileTool, EditFileTool, ListDirTool
from nanobot.agent.tools.shell import ExecTool
from nanobot.agent.tools.web import WebSearchTool, WebFetchTool
from nanobot.agent.tools.todo import TodoTool
from nanobot.agent.tools.multiedit import MultiEditTool


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
        self.brave_api_key = brave_api_key
        self.exec_config = exec_config or ExecToolConfig()
        self.restrict_to_workspace = restrict_to_workspace
        self.config = config
        self._running_tasks: dict[str, asyncio.Task[None]] = {}
        self._task_info: dict[str, SubagentTaskInfo] = {}
    
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
        
        Returns:
            Status message indicating the subagent was started.
        """
        task_id = str(uuid.uuid4())[:8]
        display_label = label or task[:30] + ("..." if len(task) > 30 else "")
        
        origin = {
            "channel": origin_channel,
            "chat_id": origin_chat_id,
        }
        
        # Create background task
        bg_task = asyncio.create_task(
            self._run_subagent(task_id, task, display_label, origin, profile)
        )
        self._running_tasks[task_id] = bg_task

        # Track task info
        profile_name = self._get_profile_name(profile) if profile else None
        task_info = SubagentTaskInfo(
            task_id=task_id,
            label=display_label,
            task=task,
            origin=origin,
            profile=profile_name,
        )
        self._task_info[task_id] = task_info

        # Cleanup old task info and write status
        self._cleanup_old_task_info()

        # Cleanup when done
        def cleanup(_: asyncio.Task[None]) -> None:
            self._running_tasks.pop(task_id, None)
            # Keep task_info for a bit for status queries, cleanup later

        bg_task.add_done_callback(cleanup)
        
        logger.info(f"Spawned subagent [{task_id}]: {display_label}")
        return f"Subagent [{display_label}] started (id: {task_id}). I'll notify you when it completes."
    
    async def _run_subagent(
        self,
        task_id: str,
        task: str,
        label: str,
        origin: dict[str, str],
        profile: "AgentProfile | None" = None,
    ) -> None:
        """Execute the subagent task and announce the result."""
        logger.info(f"Subagent [{task_id}] starting task: {label}")

        # Resolve workspace (use profile-specific if provided)
        workspace = Path(self.workspace)
        if profile and profile.workspace:
            workspace = Path(profile.workspace).expanduser()
            workspace.mkdir(parents=True, exist_ok=True)

        # Create shared results directory for subagent collaboration
        shared_results = workspace / ".subagent_results"
        shared_results.mkdir(parents=True, exist_ok=True)

        # Get profile name for todo/multiedit tools
        profile_name = self._get_profile_name(profile) if profile else None

        try:
            # Build subagent tools (no message tool, no spawn tool)
            tools = ToolRegistry()
            allowed_dir = workspace if self.restrict_to_workspace else None
            tools.register(ReadFileTool(allowed_dir=allowed_dir))
            tools.register(WriteFileTool(allowed_dir=allowed_dir))
            tools.register(EditFileTool(allowed_dir=allowed_dir))
            tools.register(ListDirTool(allowed_dir=allowed_dir))
            tools.register(ExecTool(
                working_dir=str(workspace),
                timeout=self.exec_config.timeout,
                restrict_to_workspace=self.restrict_to_workspace,
            ))
            tools.register(WebSearchTool(api_key=self.brave_api_key))
            tools.register(WebFetchTool())
            # Add todo and multiedit tools for subagents
            tools.register(TodoTool(workspace, profile=profile_name))
            tools.register(MultiEditTool(allowed_dir=allowed_dir))

            # Build messages with subagent-specific prompt
            system_prompt = self._build_subagent_prompt(task, profile=profile)

            # Use profile-specific model if provided
            model = profile.model if profile and profile.model else self.model

            messages: list[dict[str, Any]] = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": task},
            ]
            
            # Run agent loop (limited iterations)
            max_iterations = 15
            iteration = 0
            final_result: str | None = None
            last_action: str | None = None

            while iteration < max_iterations:
                iteration += 1

                # Update task info
                if task_id in self._task_info:
                    self._task_info[task_id].iteration = iteration
                    self._task_info[task_id].last_activity = datetime.now()

                # Write status file every 3 iterations
                if iteration % 3 == 0:
                    self._write_status_file()

                # Send progress update every 3 iterations
                if iteration % 3 == 0 and iteration > 0:
                    await self._announce_progress(task_id, label, iteration, last_action, origin)

                # Check for cancellation
                if task_id in self._task_info and self._task_info[task_id].status == "cancelled":
                    logger.info(f"Subagent [{task_id}] was cancelled")
                    await self._announce_result(task_id, label, task, "Task was cancelled.", origin, "cancelled")
                    return
                
                response = await self.provider.chat(
                    messages=messages,
                    tools=tools.get_definitions(),
                    model=model,
                )
                
                if response.has_tool_calls:
                    # Add assistant message with tool calls
                    tool_call_dicts = [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": json.dumps(tc.arguments),
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
                        args_str = json.dumps(tool_call.arguments)
                        logger.debug(f"Subagent [{task_id}] executing: {tool_call.name} with arguments: {args_str}")
                        last_action = f"{tool_call.name}"
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

            # Update task info status
            if task_id in self._task_info:
                self._task_info[task_id].status = "completed"
                self._task_info[task_id].result = final_result
                self._task_info[task_id].completed_at = datetime.now()
            # Write status file
            self._write_status_file()

            if final_result is None:
                final_result = "Task completed but no final response was generated."

            logger.info(f"Subagent [{task_id}] completed successfully")
            await self._announce_result(task_id, label, task, final_result, origin, "ok")

        except asyncio.CancelledError:
            logger.info(f"Subagent [{task_id}] was cancelled")
            if task_id in self._task_info:
                self._task_info[task_id].status = "cancelled"
                self._task_info[task_id].completed_at = datetime.now()
            self._write_status_file()
            await self._announce_result(task_id, label, task, "Task was cancelled.", origin, "cancelled")
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            logger.error(f"Subagent [{task_id}] failed: {e}")
            if task_id in self._task_info:
                self._task_info[task_id].status = "failed"
                self._task_info[task_id].error = error_msg
                self._task_info[task_id].completed_at = datetime.now()
            self._write_status_file()
            await self._announce_result(task_id, label, task, error_msg, origin, "error")
    
    async def _announce_result(
        self,
        task_id: str,
        label: str,
        task: str,
        result: str,
        origin: dict[str, str],
        status: str,
    ) -> None:
        """Announce the subagent result to the main agent via the message bus."""
        status_text = "completed successfully" if status == "ok" else "failed"
        
        announce_content = f"""[Subagent '{label}' {status_text}]

Task: {task}

Result:
{result}

Summarize this naturally for the user. Keep it brief (1-2 sentences). Do not mention technical details like "subagent" or task IDs."""
        
        # Inject as system message to trigger main agent
        msg = InboundMessage(
            channel="system",
            sender_id="subagent",
            chat_id=f"{origin['channel']}:{origin['chat_id']}",
            content=announce_content,
        )
        
        await self.bus.publish_inbound(msg)
        logger.debug(f"Subagent [{task_id}] announced result to {origin['channel']}:{origin['chat_id']}")

    async def _announce_progress(
        self,
        task_id: str,
        label: str,
        iteration: int,
        last_action: str | None,
        origin: dict[str, str],
    ) -> None:
        """Announce subagent progress to the main agent via the message bus."""
        action_text = f" (last: {last_action})" if last_action else ""

        announce_content = f"""[Subagent '{label}' progress update]

Working on task... (iteration {iteration}{action_text})

This is an automated progress update. The subagent is still working and will announce when complete."""

        # Inject as system message to trigger main agent
        msg = InboundMessage(
            channel="system",
            sender_id="subagent",
            chat_id=f"{origin['channel']}:{origin['chat_id']}",
            content=announce_content,
        )

        await self.bus.publish_inbound(msg)
        logger.debug(f"Subagent [{task_id}] sent progress update (iteration {iteration})")

    async def cancel(self, task_id: str) -> bool:
        """
        Cancel a running subagent.

        Args:
            task_id: The ID of the task to cancel.

        Returns:
            True if the task was found and cancellation was requested, False otherwise.
        """
        if task_id in self._running_tasks:
            self._running_tasks[task_id].cancel()
            if task_id in self._task_info:
                self._task_info[task_id].status = "cancelled"
            self._write_status_file()
            logger.info(f"Requested cancellation for subagent [{task_id}]")
            return True
        return False

    def get_running_tasks(self) -> list[SubagentTaskInfo]:
        """
        Get information about all running and recently completed subagents.

        Returns:
            List of SubagentTaskInfo objects.
        """
        return list(self._task_info.values())
    
    def _build_subagent_prompt(self, task: str, profile: 'AgentProfile | None' = None) -> str:
        """Build a focused system prompt for the subagent."""
        from datetime import datetime
        import time as _time
        now = datetime.now().strftime("%Y-%m-%d %H:%M (%A)")
        tz = _time.strftime("%Z") or "UTC"

        # Resolve workspace (use profile-specific if provided)
        workspace = Path(self.workspace)
        if profile and profile.workspace:
            workspace = Path(profile.workspace).expanduser()

        # Load relevant memory context for the task
        memory_context = ""
        profile_name = None
        memory_isolation = "shared"

        if profile:
            profile_name = self._get_profile_name(profile)
            memory_isolation = profile.memory_isolation
            from nanobot.agent.memory import MemoryStore
            memory_store = MemoryStore(workspace, profile=profile_name)
            memory_context = memory_store.get_relevant_context(task, max_chars=1500)
            if memory_context:
                memory_context = f"\n## Relevant Memory\n{memory_context}\n"

        # Build custom prompt if profile provides one
        if profile and profile.system_prompt:
            if profile.inherit_base_prompt:
                # Merge with base prompt
                custom = profile.system_prompt
            else:
                # Use only custom prompt
                custom = profile.system_prompt

                return f"""# Subagent

## Current Time
{now} ({tz})
{f'## Profile\n{profile_name}' if profile_name else ''}

{custom}
{memory_context}
## Workspace
Your workspace is at: {workspace}
Skills are available at: {workspace}/profiles/{profile_name}/skills/ and {workspace}/skills/ (read SKILL.md files as needed)

## What You Can Do
- Read, write, and edit files in the workspace
- Use multi_edit for atomic changes across multiple files
- Execute shell commands
- Search the web and fetch web pages
- Use the todo tool to manage subtasks
- **Collaborate with other subagents** via shared results directory
- Complete the task thoroughly

## What You Cannot Do
- Send messages directly to users (no message tool available)
- Spawn other subagents
- Access the main agent's conversation history

## Subagent Collaboration
You can share data with other subagents through the shared results directory:
- Location: `{workspace}/.subagent_results/`
- **Write results**: Save files here for other subagents to read (e.g., `schema_design.json`)
- **Read results**: Other subagents may have left data here for you
- **Common pattern**: Subagent A writes analysis → Subagent B reads and implements

Example:
```python
# Subagent A (designer) writes:
write_file(path=".subagent_results/database_schema.json", content=json.dumps(schema))

# Subagent B (implementer) reads:
schema = json.loads(read_file(path=".subagent_results/database_schema.json"))
# Now implement based on the schema
```

When you have completed the task, provide a clear summary of your findings or actions."""
        else:
            custom = None

        # Standard subagent prompt
        base_prompt = f"""# Subagent

## Current Time
{now} ({tz})
{f'## Profile\n{profile_name}' if profile_name else ''}

You are a subagent spawned by the main agent to complete a specific task.
{memory_context}
## Rules
1. Stay focused - complete only the assigned task, nothing else
2. Your final response will be reported back to the main agent
3. Do not initiate conversations or take on side tasks
4. Be concise but informative in your findings

## What You Can Do
- Read, write, and edit files in the workspace
- Use multi_edit for atomic changes across multiple files
- Execute shell commands
- Search the web and fetch web pages
- Use the todo tool to manage subtasks
- **Collaborate with other subagents** via shared results directory
- Complete the task thoroughly

## What You Cannot Do
- Send messages directly to users (no message tool available)
- Spawn other subagents
- Access the main agent's conversation history

## Workspace
Your workspace is at: {workspace}
Skills are available at: {workspace}/profiles/{profile_name}/skills/ and {workspace}/skills/ (read SKILL.md files as needed)

## Subagent Collaboration
You can share data with other subagents through the shared results directory:
- Location: `{workspace}/.subagent_results/`
- **Write results**: Save files here for other subagents to read (e.g., `schema_design.json`)
- **Read results**: Other subagents may have left data here for you
- **Common pattern**: Subagent A writes analysis → Subagent B reads and implements

Example:
```python
# Subagent A (designer) writes:
write_file(path=".subagent_results/database_schema.json", content=json.dumps(schema))

# Subagent B (implementer) reads:
schema = json.loads(read_file(path=".subagent_results/database_schema.json"))
# Now implement based on the schema
```

When you have completed the task, provide a clear summary of your findings or actions."""

        if custom:
            return f"{base_prompt}\n\n## Additional Instructions\n{custom}"
        return base_prompt

    def _get_profile_name(self, profile: 'AgentProfile') -> str | None:
        """Get the profile name from the profile object by looking it up in config."""
        if not self.config:
            return None
        for name, p in self.config.agents.profiles.items():
            if p is profile:
                return name
        return None
    
    def get_running_count(self) -> int:
        """Return the number of currently running subagents."""
        return len(self._running_tasks)

    def _write_status_file(self) -> None:
        """Write current subagent status to a JSON file for monitoring."""
        status_file = self.workspace / ".subagent_status.json"

        try:
            status_data = {
                "timestamp": datetime.now().isoformat(),
                "running_count": len(self._running_tasks),
                "subagents": {},
            }

            for task_id, info in self._task_info.items():
                status_data["subagents"][task_id] = {
                    "label": info.label,
                    "task": info.task[:100] + "..." if len(info.task) > 100 else info.task,
                    "status": info.status,
                    "profile": info.profile,
                    "iteration": info.iteration,
                    "created_at": info.created_at.isoformat(),
                    "last_activity": info.last_activity.isoformat(),
                }
                if info.completed_at:
                    status_data["subagents"][task_id]["completed_at"] = info.completed_at.isoformat()
                if info.result:
                    status_data["subagents"][task_id]["result"] = info.result[:200] + "..." if len(info.result) > 200 else info.result
                if info.error:
                    status_data["subagents"][task_id]["error"] = info.error[:200] + "..." if len(info.error) > 200 else info.error

            status_file.write_text(json.dumps(status_data, indent=2))
        except Exception as e:
            logger.warning(f"Failed to write status file: {e}")

    def _cleanup_old_task_info(self) -> None:
        """Remove old completed task info to prevent memory buildup."""
        import time as _time
        now = _time.time()

        # Remove tasks completed more than 5 minutes ago
        to_remove = []
        for task_id, info in self._task_info.items():
            if info.status in ("completed", "failed", "cancelled"):
                if info.completed_at:
                    elapsed = (datetime.now() - info.completed_at).total_seconds()
                    if elapsed > 300:  # 5 minutes
                        to_remove.append(task_id)

        for task_id in to_remove:
            del self._task_info[task_id]

        # Always write status after cleanup
        self._write_status_file()
