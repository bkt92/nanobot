"""Todo list tool for task management."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from nanobot.agent.tools.base import Tool


class TodoStore:
    """Storage for todo items."""

    def __init__(self, workspace: Path, profile: str | None = None):
        self.workspace = workspace
        self.profile = profile

        # Set up todo storage path
        if profile:
            self.todo_dir = workspace / "profiles" / profile / "todos"
        else:
            self.todo_dir = workspace / "todos"

        self.todo_dir.mkdir(parents=True, exist_ok=True)
        self.todo_file = self.todo_dir / "todos.json"

    def _load(self) -> dict:
        """Load todos from file."""
        if not self.todo_file.exists():
            return {"todos": [], "next_id": 1}
        try:
            return json.loads(self.todo_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, IOError):
            return {"todos": [], "next_id": 1}

    def _save(self, data: dict) -> None:
        """Save todos to file."""
        self.todo_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def create(
        self,
        subject: str,
        description: str,
        metadata: dict | None = None,
    ) -> dict:
        """Create a new todo."""
        data = self._load()
        todo_id = str(data["next_id"])
        data["next_id"] += 1

        todo = {
            "id": todo_id,
            "subject": subject,
            "description": description,
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "metadata": metadata or {},
            "blocks": [],
            "blocked_by": [],
        }

        data["todos"].append(todo)
        self._save(data)
        return todo

    def list(self) -> list[dict]:
        """List all todos."""
        data = self._load()
        return data.get("todos", [])

    def get(self, todo_id: str) -> dict | None:
        """Get a specific todo."""
        data = self._load()
        for todo in data.get("todos", []):
            if todo["id"] == todo_id:
                return todo
        return None

    def update(
        self,
        todo_id: str,
        subject: str | None = None,
        description: str | None = None,
        status: str | None = None,
        add_blocks: list[str] | None = None,
        add_blocked_by: list[str] | None = None,
        metadata: dict | None = None,
    ) -> dict | None:
        """Update a todo."""
        data = self._load()

        for todo in data.get("todos", []):
            if todo["id"] == todo_id:
                if subject is not None:
                    todo["subject"] = subject
                if description is not None:
                    todo["description"] = description
                if status is not None:
                    todo["status"] = status
                if add_blocks is not None:
                    for block_id in add_blocks:
                        if block_id not in todo["blocks"]:
                            todo["blocks"].append(block_id)
                            # Add reverse dependency
                            for other in data.get("todos", []):
                                if other["id"] == block_id:
                                    if todo_id not in other.get("blocked_by", []):
                                        other["blocked_by"] = other.get("blocked_by", [])
                                        other["blocked_by"].append(todo_id)
                if add_blocked_by is not None:
                    for block_id in add_blocked_by:
                        if block_id not in todo["blocked_by"]:
                            todo["blocked_by"].append(block_id)
                            # Add reverse dependency
                            for other in data.get("todos", []):
                                if other["id"] == block_id:
                                    if todo_id not in other.get("blocks", []):
                                        other["blocks"] = other.get("blocks", [])
                                        other["blocks"].append(todo_id)
                if metadata is not None:
                    todo["metadata"] = {**todo.get("metadata", {}), **metadata}

                todo["updated_at"] = datetime.now().isoformat()
                self._save(data)
                return todo

        return None

    def delete(self, todo_id: str, delete: bool = False) -> dict | None:
        """Delete or mark a todo as deleted."""
        data = self._load()

        for i, todo in enumerate(data.get("todos", [])):
            if todo["id"] == todo_id:
                if delete:
                    # Actually remove from list
                    data["todos"].pop(i)
                    self._save(data)
                    return todo
                else:
                    # Mark as deleted
                    todo["status"] = "deleted"
                    todo["updated_at"] = datetime.now().isoformat()
                    self._save(data)
                    return todo

        return None


class TodoTool(Tool):
    """Tool for managing todo/task lists."""

    def __init__(self, workspace: Path, profile: str | None = None):
        self.workspace = workspace
        self.profile = profile
        self._store = TodoStore(workspace, profile)

    def set_context(self, profile: str) -> None:
        """Update profile context."""
        self.profile = profile
        self._store = TodoStore(self.workspace, profile)

    @property
    def name(self) -> str:
        return "todo"

    @property
    def description(self) -> str:
        return (
            "Manage todo/task lists. "
            "Actions: create, list, get, update, complete, delete. "
            "Tasks support dependencies (blocks/blocked_by)."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Action to perform",
                    "enum": ["create", "list", "get", "update", "complete", "delete"]
                },
                "id": {
                    "type": "string",
                    "description": "Task ID (for get, update, complete, delete actions)"
                },
                "subject": {
                    "type": "string",
                    "description": "Task subject/title (for create, update actions)"
                },
                "description": {
                    "type": "string",
                    "description": "Detailed task description (for create, update actions)"
                },
                "add_blocks": {
                    "type": "array",
                    "description": "List of task IDs this task blocks (for update action)",
                    "items": {"type": "string"}
                },
                "add_blocked_by": {
                    "type": "array",
                    "description": "List of task IDs that block this task (for update action)",
                    "items": {"type": "string"}
                },
                "metadata": {
                    "type": "object",
                    "description": "Additional metadata to attach to task (for create, update actions)"
                }
            },
            "required": ["action"]
        }

    async def execute(self, action: str, **kwargs: Any) -> str:
        """Execute todo action."""
        try:
            if action == "create":
                return self._create(**kwargs)
            elif action == "list":
                return self._list()
            elif action == "get":
                return self._get(**kwargs)
            elif action == "update":
                return self._update(**kwargs)
            elif action == "complete":
                return self._complete(**kwargs)
            elif action == "delete":
                return self._delete(**kwargs)
            else:
                return f"Error: Unknown action '{action}'"
        except Exception as e:
            return f"Error: {str(e)}"

    def _create(self, subject: str, description: str, metadata: dict | None = None, **kwargs: Any) -> str:
        """Create a new todo."""
        if not subject:
            return "Error: subject is required for create action"
        if not description:
            return "Error: description is required for create action"

        todo = self._store.create(subject, description, metadata)

        return f"""✅ Task created

ID: {todo['id']}
Subject: {todo['subject']}

Description:
{todo['description']}

Use 'todo' action='get' id='{todo['id']}' to view details.
Use 'todo' action='update' id='{todo['id']}' to make changes.
"""

    def _list(self) -> str:
        """List all todos."""
        todos = self._store.list()

        if not todos:
            return "No tasks found. Create one with todo action='create'..."

        # Group by status
        pending = [t for t in todos if t["status"] == "pending" and not t.get("blocked_by")]
        blocked = [t for t in todos if t["status"] == "pending" and t.get("blocked_by")]
        in_progress = [t for t in todos if t["status"] == "in_progress"]
        completed = [t for t in todos if t["status"] == "completed"]
        deleted = [t for t in todos if t["status"] == "deleted"]

        lines = []
        lines.append(f"📋 Tasks ({len(todos)} total)\n")

        if pending:
            lines.append("## Ready to Start")
            for todo in pending:
                lines.append(f"  [{todo['id']}] {todo['subject']}")
            lines.append("")

        if blocked:
            lines.append("## Blocked (waiting for dependencies)")
            for todo in blocked:
                blocks = ", ".join(todo.get("blocked_by", []))
                lines.append(f"  [{todo['id']}] {todo['subject']} (blocked by: {blocks})")
            lines.append("")

        if in_progress:
            lines.append("## In Progress")
            for todo in in_progress:
                lines.append(f"  [{todo['id']}] {todo['subject']}")
            lines.append("")

        if completed:
            lines.append("## Completed")
            for todo in completed:
                lines.append(f"  [{todo['id']}] {todo['subject']}")
            lines.append("")

        if deleted:
            lines.append("## Deleted (soft-deleted)")
            for todo in deleted:
                lines.append(f"  [{todo['id']}] {todo['subject']}")
            lines.append("")

        return "\n".join(lines)

    def _get(self, id: str, **kwargs: Any) -> str:
        """Get todo details."""
        if not id:
            return "Error: id is required for get action"

        todo = self._store.get(id)
        if not todo:
            return f"Error: Task '{id}' not found"

        lines = [
            f"📋 Task {todo['id']}: {todo['subject']}",
            f"Status: {todo['status']}",
            f"Created: {todo['created_at']}",
            f"Updated: {todo['updated_at']}",
            "",
            "Description:",
            todo['description'],
        ]

        if todo.get("blocks"):
            lines.append("")
            lines.append(f"Blocks (these tasks depend on this): {', '.join(todo['blocks'])}")

        if todo.get("blocked_by"):
            lines.append("")
            lines.append(f"Blocked by: {', '.join(todo['blocked_by'])}")

        if todo.get("metadata"):
            lines.append("")
            lines.append("Metadata:")
            for key, value in todo["metadata"].items():
                lines.append(f"  {key}: {value}")

        return "\n".join(lines)

    def _update(self, id: str, **kwargs: Any) -> str:
        """Update a todo."""
        if not id:
            return "Error: id is required for update action"

        # Extract arrays for dependencies
        add_blocks = kwargs.pop("add_blocks", None)
        add_blocked_by = kwargs.pop("add_blocked_by", None)
        metadata = kwargs.pop("metadata", None)

        todo = self._store.update(
            id,
            subject=kwargs.get("subject"),
            description=kwargs.get("description"),
            status=kwargs.get("status"),
            add_blocks=add_blocks,
            add_blocked_by=add_blocked_by,
            metadata=metadata,
        )

        if not todo:
            return f"Error: Task '{id}' not found"

        return f"""✅ Task updated

ID: {todo['id']}
Subject: {todo['subject']}
Status: {todo['status']}
"""

    def _complete(self, id: str, **kwargs: Any) -> str:
        """Mark a todo as completed."""
        if not id:
            return "Error: id is required for complete action"

        todo = self._store.update(id, status="completed")
        if not todo:
            return f"Error: Task '{id}' not found"

        return f"""✅ Task completed

ID: {todo['id']}
Subject: {todo['subject']}
"""

    def _delete(self, id: str, delete: bool = False, **kwargs: Any) -> str:
        """Delete a todo."""
        if not id:
            return "Error: id is required for delete action"

        todo = self._store.delete(id, delete=delete)
        if not todo:
            return f"Error: Task '{id}' not found"

        action = "permanently deleted" if delete else "marked as deleted"
        return f"✅ Task '{todo['subject']}' ({action})"
