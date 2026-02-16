"""Multi-file edit tool for batch editing operations."""

from pathlib import Path
from typing import Any

from nanobot.agent.tools.base import Tool
from nanobot.agent.tools.filesystem import _resolve_path


class MultiEditTool(Tool):
    """Tool to edit multiple files in a single operation."""

    def __init__(self, allowed_dir: Path | None = None):
        self._allowed_dir = allowed_dir

    @property
    def name(self) -> str:
        return "multi_edit"

    @property
    def description(self) -> str:
        return (
            "Edit multiple files in a single operation. "
            "Each edit specifies a file path, old_text to find, and new_text to replace with. "
            "All edits are applied atomically - if any edit fails, no changes are made."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "edits": {
                    "type": "array",
                    "description": "Array of edit operations to apply",
                    "items": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "The file path to edit"
                            },
                            "old_text": {
                                "type": "string",
                                "description": "The exact text to find and replace"
                            },
                            "new_text": {
                                "type": "string",
                                "description": "The text to replace with"
                            }
                        },
                        "required": ["path", "old_text", "new_text"]
                    }
                },
                "dry_run": {
                    "type": "boolean",
                    "description": "If true, show what would change without actually editing files"
                }
            },
            "required": ["edits"]
        }

    async def execute(self, edits: list[dict], dry_run: bool = False, **kwargs: Any) -> str:
        """
        Execute multi-file edit operation.

        Args:
            edits: List of edit operations
            dry_run: If True, show changes without applying them

        Returns:
            Summary of the edit operation
        """
        if not edits:
            return "Error: edits array is empty"

        # First pass: validate all edits and read file contents
        file_states = {}
        errors = []

        for i, edit in enumerate(edits):
            # Validate edit structure
            if "path" not in edit:
                errors.append(f"Edit {i}: missing 'path'")
                continue
            if "old_text" not in edit:
                errors.append(f"Edit {i} ({edit['path']}): missing 'old_text'")
                continue
            if "new_text" not in edit:
                errors.append(f"Edit {i} ({edit['path']}): missing 'new_text'")
                continue

            path = edit["path"]
            old_text = edit["old_text"]
            new_text = edit["new_text"]

            try:
                file_path = _resolve_path(path, self._allowed_dir)

                if not file_path.exists():
                    errors.append(f"Edit {i} ({path}): file not found")
                    continue

                if not file_path.is_file():
                    errors.append(f"Edit {i} ({path}): not a file")
                    continue

                content = file_path.read_text(encoding="utf-8")

                if old_text not in content:
                    errors.append(f"Edit {i} ({path}): old_text not found in file")
                    continue

                # Check for multiple occurrences
                count = content.count(old_text)
                if count > 1:
                    errors.append(f"Edit {i} ({path}): old_text appears {count} times, must be unique")
                    continue

                # Store the state for this file
                if path not in file_states:
                    file_states[path] = {"original": content, "edits": [], "path": file_path}

                # Calculate what the content would look like after this edit
                current_content = file_states[path]["original"]
                for prev_edit in file_states[path]["edits"]:
                    # Apply previous edits to get current state
                    current_content = current_content.replace(prev_edit["old_text"], prev_edit["new_text"], 1)

                new_content = current_content.replace(old_text, new_text, 1)
                file_states[path]["edits"].append({"old_text": old_text, "new_text": new_text})
                file_states[path]["final"] = new_content

            except PermissionError as e:
                errors.append(f"Edit {i} ({path}): permission denied - {e}")
            except Exception as e:
                errors.append(f"Edit {i} ({path}): {str(e)}")

        if errors:
            return "Validation errors:\n" + "\n".join(f"  - {e}" for e in errors)

        if dry_run:
            # Show what would change
            lines = ["Dry run - showing planned changes:\n"]
            for path, state in file_states.items():
                lines.append(f"📄 {path}")
                lines.append(f"  Edits: {len(state['edits'])}")
                for j, edit in enumerate(state["edits"], 1):
                    preview_old = edit["old_text"][:50] + "..." if len(edit["old_text"]) > 50 else edit["old_text"]
                    preview_new = edit["new_text"][:50] + "..." if len(edit["new_text"]) > 50 else edit["new_text"]
                    lines.append(f"  {j}. '{preview_old}' → '{preview_new}'")
                lines.append("")
            return "\n".join(lines)

        # Apply all edits atomically
        applied = []
        try:
            for path, state in file_states.items():
                state["path"].write_text(state["final"], encoding="utf-8")
                applied.append(path)

            # Generate summary
            summary_parts = [
                f"✅ Successfully edited {len(applied)} file(s):\n",
            ]
            for path in applied:
                edit_count = file_states[path]["edits"]
                summary_parts.append(f"  • {path} ({len(edit_count)} edit{'s' if len(edit_count) > 1 else ''})")

            return "\n".join(summary_parts)

        except Exception as e:
            # Something went wrong during write
            return f"Error applying edits: {str(e)}"
