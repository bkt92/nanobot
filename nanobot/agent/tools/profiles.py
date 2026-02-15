"""Tool for listing available agent profiles."""

from typing import Any

from nanobot.agent.tools.base import Tool


class ListProfilesTool(Tool):
    """Tool to list available agent profiles."""

    def __init__(self, config: "Config | None" = None):
        self._config = config

    @property
    def name(self) -> str:
        return "list_profiles"

    @property
    def description(self) -> str:
        return (
            "List all available agent profiles configured in nanobot. "
            "Returns profile names with their models and descriptions. "
            "Use this to see what profiles are available before spawning a subagent."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
        }

    async def execute(self, **kwargs: Any) -> str:
        """List all available agent profiles."""
        if not self._config:
            return "Error: Config not available. Cannot list profiles."

        profiles = self._config.agents.profiles

        if not profiles:
            return "No agent profiles configured. Add profiles to config.json under agents.profiles."

        lines = ["Available agent profiles:\n"]

        for name, profile in profiles.items():
            lines.append(f"- {name}")
            lines.append(f"  Model: {profile.model}")
            lines.append(f"  Temperature: {profile.temperature}")

            if profile.system_prompt:
                prompt_preview = profile.system_prompt[:80] + "..." if len(profile.system_prompt) > 80 else profile.system_prompt
                lines.append(f"  System Prompt: {prompt_preview}")

            if profile.workspace:
                lines.append(f"  Workspace: {profile.workspace}")

            lines.append("")

        return "\n".join(lines)
