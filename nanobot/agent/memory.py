"""Memory system for persistent agent memory."""

from pathlib import Path

from nanobot.utils.helpers import ensure_dir


class MemoryStore:
    """Two-layer memory: MEMORY.md (long-term facts) + HISTORY.md (grep-searchable log)."""

    def __init__(self, workspace: Path, profile: str | None = None):
        self.workspace = workspace
        self.profile = profile
        self.memory_dir = ensure_dir(workspace / "memory")

        # Set up profile-specific memory paths
        if profile:
            self.profile_memory_dir = ensure_dir(self.memory_dir / "profiles" / profile)
            self.memory_file = self.profile_memory_dir / "MEMORY.md"
            self.history_file = self.profile_memory_dir / "HISTORY.md"
        else:
            self.profile_memory_dir = None
            self.memory_file = self.memory_dir / "MEMORY.md"
            self.history_file = self.memory_dir / "HISTORY.md"

    def _get_global_memory_file(self) -> Path:
        """Get the global memory file path."""
        return self.memory_dir / "MEMORY.md"

    def _get_global_history_file(self) -> Path:
        """Get the global history file path."""
        return self.memory_dir / "HISTORY.md"

    def read_long_term(self, include_global: bool = True) -> str:
        """Read long-term memory. For profile-specific stores, also include global if requested."""
        parts = []

        # Read profile memory first (if applicable)
        if self.profile and self.memory_file.exists():
            content = self.memory_file.read_text(encoding="utf-8")
            if content:
                parts.append(f"## Profile Memory ({self.profile})\n{content}")

        # Read global memory
        if include_global:
            global_file = self._get_global_memory_file()
            if global_file.exists():
                content = global_file.read_text(encoding="utf-8")
                if content:
                    parts.append(f"## Global Memory\n{content}")

        return "\n\n".join(parts) if parts else ""

    def write_long_term(self, content: str) -> None:
        """Write to the appropriate memory file."""
        self.memory_file.parent.mkdir(parents=True, exist_ok=True)
        self.memory_file.write_text(content, encoding="utf-8")

    def append_history(self, entry: str) -> None:
        """Append to the appropriate history file."""
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.history_file, "a", encoding="utf-8") as f:
            f.write(entry.rstrip() + "\n\n")

    def get_memory_context(
        self,
        isolation: str = "shared",
        include_global: bool = True,
    ) -> str:
        """
        Get memory context based on isolation mode.

        Args:
            isolation: Memory isolation mode ("shared", "isolated", "hierarchical")
            include_global: Whether to include global memory (only for hierarchical mode)

        Returns:
            Formatted memory context string.
        """
        if isolation == "isolated" or self.profile is None:
            # Isolated: only profile memory, or global if no profile
            long_term = self.read_long_term(include_global=False)
            return f"## Long-term Memory\n{long_term}" if long_term else ""

        elif isolation == "hierarchical":
            # Hierarchical: profile memory + global memory
            long_term = self.read_long_term(include_global=include_global)
            if long_term:
                return f"## Long-term Memory\n{long_term}"
            return ""

        else:  # shared
            # Shared: always use global memory
            global_file = self._get_global_memory_file()
            if global_file.exists():
                content = global_file.read_text(encoding="utf-8")
                return f"## Long-term Memory\n{content}" if content else ""
            return ""

    def read_global_memory(self) -> str:
        """Read only the global memory file."""
        global_file = self._get_global_memory_file()
        if global_file.exists():
            return global_file.read_text(encoding="utf-8")
        return ""

    def write_global_memory(self, content: str) -> None:
        """Write to the global memory file."""
        global_file = self._get_global_memory_file()
        global_file.parent.mkdir(parents=True, exist_ok=True)
        global_file.write_text(content, encoding="utf-8")

    def get_relevant_context(
        self,
        task: str,
        max_chars: int = 2000,
    ) -> str:
        """
        Get relevant memory context for a specific task.
        Searches global and profile-specific history for relevant entries.

        Args:
            task: The task description to match against.
            max_chars: Maximum characters to return.

        Returns:
            Relevant memory entries concatenated together.
        """
        import re

        # Extract key terms from task (simple approach: words 4+ chars)
        words = re.findall(r"\b\w{4,}\b", task.lower())
        if not words:
            return ""

        # Build regex pattern for any matching term
        pattern = "|".join(re.escape(w) for w in set(words[:5]))  # Use top 5 terms
        if not pattern:
            return ""

        results = []

        # Search profile history if applicable
        if self.profile and self.history_file.exists():
            content = self.history_file.read_text(encoding="utf-8")
            matches = re.findall(r".{0,200}" + pattern + ".{0,200}", content, re.IGNORECASE)
            if matches:
                results.append(f"## Profile History ({self.profile})\n" + "\n".join(matches[:3]))

        # Search global history
        global_history = self._get_global_history_file()
        if global_history.exists():
            content = global_history.read_text(encoding="utf-8")
            matches = re.findall(r".{0,200}" + pattern + ".{0,200}", content, re.IGNORECASE)
            if matches:
                results.append(f"## Global History\n" + "\n".join(matches[:3]))

        if not results:
            return ""

        combined = "\n\n".join(results)
        return combined[:max_chars] if len(combined) > max_chars else combined
