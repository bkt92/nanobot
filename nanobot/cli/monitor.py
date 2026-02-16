"""Monitor main agent ↔ subagent and subagent ↔ subagent communication."""

from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.columns import Columns
from rich.layout import Layout


class EventType(Enum):
    """Types of events to monitor."""
    MAIN_TO_SUB = "→ SUBAGENT"
    SUB_TO_MAIN = "→ MAIN"
    SUB_TO_SUB = "↔ SUBAGENT"
    PROGRESS = "⏳ PROGRESS"
    STATUS = "📊 STATUS"


@dataclass
class MonitorEvent:
    """A single monitor event."""
    timestamp: datetime
    event_type: EventType
    source: str
    target: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def __repr__(self) -> str:
        ts = self.timestamp.strftime("%H:%M:%S")
        return f"[{ts}] {self.event_type.value}: {self.source} → {self.target}"


class AgentMonitor:
    """Monitor agent communication in real-time."""

    def __init__(self, workspace: Path, console: Console | None = None):
        self.workspace = workspace
        self.console = console or Console()
        self.events: list[MonitorEvent] = []
        self.max_events = 50
        self._running = False
        self._shared_results_dir = workspace / ".subagent_results"
        self._shared_results_files: dict[str, float] = {}  # path -> mtime
        self._subagent_status_file = workspace / ".subagent_status.json"

    async def start(self) -> None:
        """Start monitoring agent communication."""
        self._running = True
        self.console.print("[bold cyan]Starting Agent Monitor[/bold cyan]")
        self.console.print(f"[dim]Workspace: {self.workspace}[/dim]")
        self.console.print(f"[dim]Shared results: {self._shared_results_dir}[/dim]")
        self.console.print("[dim]Press Ctrl+C to stop[/dim]\n")

        # Initialize file tracking
        if self._shared_results_dir.exists():
            for path in self._shared_results_dir.rglob("*"):
                if path.is_file():
                    self._shared_results_files[str(path)] = path.stat().st_mtime

        with Live(self._render(), console=self.console, refresh_per_second=2) as live:
            while self._running:
                # Check for file changes (subagent ↔ subagent)
                await self._check_file_changes()

                # Update display
                live.update(self._render())

                await asyncio.sleep(0.5)

    def stop(self) -> None:
        """Stop monitoring."""
        self._running = False

    def add_event(
        self,
        event_type: EventType,
        source: str,
        target: str,
        content: str,
        **metadata: Any,
    ) -> None:
        """Add a monitoring event."""
        event = MonitorEvent(
            timestamp=datetime.now(),
            event_type=event_type,
            source=source,
            target=target,
            content=content[:200] + "..." if len(content) > 200 else content,
            metadata=metadata,
        )
        self.events.append(event)
        if len(self.events) > self.max_events:
            self.events.pop(0)

    async def _check_file_changes(self) -> None:
        """Check for changes in shared results directory."""
        if not self._shared_results_dir.exists():
            return

        current_files: dict[str, float] = {}

        for path in self._shared_results_dir.rglob("*"):
            if path.is_file():
                mtime = path.stat().st_mtime
                current_files[str(path)] = mtime

                # Check if file is new or modified
                if str(path) not in self._shared_results_files:
                    # New file
                    self.add_event(
                        EventType.SUB_TO_SUB,
                        f"subagent",
                        f"file:{path.name}",
                        f"Created: {path.relative_to(self._shared_results_dir)}",
                        file_path=str(path),
                    )
                elif mtime > self._shared_results_files[str(path)]:
                    # Modified file
                    self.add_event(
                        EventType.SUB_TO_SUB,
                        f"subagent",
                        f"file:{path.name}",
                        f"Modified: {path.relative_to(self._shared_results_dir)}",
                        file_path=str(path),
                    )

        # Check for deleted files
        for path in list(self._shared_results_files.keys()):
            if path not in current_files:
                self.add_event(
                    EventType.SUB_TO_SUB,
                    f"file:{Path(path).name}",
                    "deleted",
                    f"Deleted: {Path(path).relative_to(self._shared_results_dir)}",
                    file_path=path,
                )

        self._shared_results_files = current_files

    def _render(self) -> Panel:
        """Render the monitoring display."""
        layout = Layout()

        # Split into top (events) and bottom (status + files)
        layout.split_column(
            Layout(name="events", ratio=3),
            Layout(name="bottom", ratio=2),
        )

        # Events panel
        layout["events"].update(self._render_events())

        # Bottom split
        layout["bottom"].split_row(
            Layout(name="status"),
            Layout(name="files"),
        )

        layout["status"].update(self._render_subagent_status())
        layout["files"].update(self._render_shared_files())

        return Panel(
            layout,
            title=f"[bold]Agent Communication Monitor[/bold]",
            border_style="cyan",
            padding=(0, 1),
        )

    def _render_events(self) -> Panel:
        """Render the events table."""
        table = Table(show_header=True, header_style="bold cyan", expand=True)
        table.add_column("Time", style="dim", width=8)
        table.add_column("Type", style="bold", width=15)
        table.add_column("Source", style="cyan", width=20)
        table.add_column("Target", style="green", width=20)
        table.add_column("Content", style="white")

        for event in reversed(self.events[-20:]):  # Show last 20 events
            ts = event.timestamp.strftime("%H:%M:%S")
            type_style = {
                EventType.MAIN_TO_SUB: "[blue]",
                EventType.SUB_TO_MAIN: "[green]",
                EventType.SUB_TO_SUB: "[yellow]",
                EventType.PROGRESS: "[dim]",
                EventType.STATUS: "[magenta]",
            }[event.event_type]

            table.add_row(
                Text(ts, style="dim"),
                Text(event.event_type.value, style=type_style + " bold"),
                Text(event.source, style="cyan"),
                Text(event.target, style="green"),
                Text(event.content, style="white"),
            )

        return Panel(
            table,
            title="Events",
            border_style="dim",
        )

    def _render_subagent_status(self) -> Panel:
        """Render subagent status from status file."""
        status_file = self._subagent_status_file

        if not status_file.exists():
            return Panel(
                Text("No subagent status available", style="dim"),
                title="Subagent Status",
                border_style="dim",
            )

        try:
            data = json.loads(status_file.read_text())
            subagents = data.get("subagents", {})

            if not subagents:
                return Panel(
                    Text("No running subagents", style="dim"),
                    title="Subagent Status",
                    border_style="dim",
                )

            table = Table(show_header=False, box=None, expand=True)
            table.add_column("Key", style="cyan")
            table.add_column("Value", style="white")

            for task_id, info in subagents.items():
                label = info.get("label", "Unknown")
                status = info.get("status", "unknown")
                iteration = info.get("iteration", 0)

                status_color = {
                    "running": "green",
                    "completed": "blue",
                    "failed": "red",
                    "cancelled": "yellow",
                }.get(status, "white")

                table.add_row(
                    Text(f"[{task_id}]", style="cyan"),
                    Text(f"{label}\n{Text(status, style=status_color)} (iter: {iteration})"),
                )

            return Panel(
                table,
                title=f"Subagent Status ({len(subagents)} active)",
                border_style="dim",
            )

        except Exception as e:
            return Panel(
                Text(f"Error reading status: {e}", style="red"),
                title="Subagent Status",
                border_style="dim",
            )

    def _render_shared_files(self) -> Panel:
        """Render shared results files."""
        if not self._shared_results_dir.exists():
            return Panel(
                Text("Shared results directory not found", style="dim"),
                title="Shared Files",
                border_style="dim",
            )

        files = list(self._shared_results_dir.rglob("*"))
        files = [f for f in files if f.is_file()]

        if not files:
            return Panel(
                Text("No files", style="dim"),
                title="Shared Files",
                border_style="dim",
            )

        table = Table(show_header=True, box=None, expand=True)
        table.add_column("File", style="yellow")
        table.add_column("Size", style="dim")

        for f in files[-10:]:  # Show last 10 files
            size = f"{f.stat().st_size}B"
            table.add_row(f.name, Text(size, style="dim"))

        return Panel(
            table,
            title=f"Shared Files ({len(files)} total)",
            border_style="dim",
        )


class StaticMonitor:
    """Static monitor for showing current state without live updates."""

    def __init__(self, workspace: Path, console: Console | None = None):
        self.workspace = workspace
        self.console = console or Console()
        self._shared_results_dir = workspace / ".subagent_results"
        self._subagent_status_file = workspace / ".subagent_status.json"

    def show(self) -> None:
        """Show the current monitoring state."""
        self.console.print("[bold cyan]Agent Communication Monitor[/bold cyan]")
        self.console.print(f"[dim]Workspace: {self.workspace}[/dim]\n")

        # Show subagent status
        self._show_subagent_status()

        # Show shared files
        self._show_shared_files()

    def _show_subagent_status(self) -> None:
        """Show subagent status."""
        status_file = self._subagent_status_file

        self.console.print("[bold]Subagent Status:[/bold]")

        if not status_file.exists():
            self.console.print("[dim]  No status file found[/dim]\n")
            return

        try:
            data = json.loads(status_file.read_text())
            subagents = data.get("subagents", {})

            if not subagents:
                self.console.print("[dim]  No running subagents[/dim]\n")
                return

            table = Table(show_header=True, header_style="bold cyan")
            table.add_column("Task ID")
            table.add_column("Label")
            table.add_column("Status")
            table.add_column("Profile")
            table.add_column("Iteration")

            for task_id, info in subagents.items():
                label = info.get("label", "Unknown")
                status = info.get("status", "unknown")
                profile = info.get("profile", "-")
                iteration = info.get("iteration", 0)

                status_color = {
                    "running": "[green]",
                    "completed": "[blue]",
                    "failed": "[red]",
                    "cancelled": "[yellow]",
                }.get(status, "")

                table.add_row(
                    task_id,
                    label,
                    Text(f"{status_color}{status}"),
                    profile,
                    str(iteration),
                )

            self.console.print(table)
            self.console.print()

        except Exception as e:
            self.console.print(f"[red]Error reading status: {e}[/red]\n")

    def _show_shared_files(self) -> None:
        """Show shared results files."""
        self.console.print("[bold]Shared Results Directory:[/bold]")

        if not self._shared_results_dir.exists():
            self.console.print(f"[dim]  Not found: {self._shared_results_dir}[/dim]")
            self.console.print("[dim]  (Will be created when subagents communicate)[/dim]\n")
            return

        files = list(self._shared_results_dir.rglob("*"))
        files = [f for f in files if f.is_file()]

        if not files:
            self.console.print("[dim]  No files[/dim]\n")
            return

        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("File")
        table.add_column("Size")
        table.add_column("Modified")

        for f in files:
            table.add_row(
                f.name,
                f"{f.stat().st_size} bytes",
                datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
            )

        self.console.print(table)
        self.console.print()

        # Show content of text/JSON files
        for f in files[:3]:  # Show up to 3 files
            if f.suffix in (".json", ".txt", ".md"):
                self.console.print(f"\n[bold]{f.name}:[/bold]")
                try:
                    content = f.read_text()
                    if f.suffix == ".json":
                        self.console.print_json(content)
                    else:
                        preview = content[:500] + "..." if len(content) > 500 else content
                        self.console.print(Text(preview, style="dim"))
                except Exception as e:
                    self.console.print(f"[dim]Error reading file: {e}[/dim]")


# Global monitor instance (for message bus callbacks)
_monitor: AgentMonitor | None = None


def get_monitor(workspace: Path) -> AgentMonitor:
    """Get or create the global monitor instance."""
    global _monitor
    if _monitor is None or _monitor.workspace != workspace:
        console = Console()
        _monitor = AgentMonitor(workspace, console)
    return _monitor
