"""Service for persisting and restoring UI state across sessions.

Decouples GUI widgets from file I/O and JSON serialization details.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from expenses_tracker.security import apply_private_permissions


class UIStateService:
    """Read and write application UI state to a JSON file."""

    def __init__(self, state_file: Path | str = "data/ui_state.json") -> None:
        self._state_file = Path(state_file)

    def read(self) -> dict[str, Any]:
        """Load state from disk; return empty dict on missing or corrupt file."""
        if not self._state_file.exists():
            return {}
        try:
            return json.loads(self._state_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def write(self, data: dict[str, Any]) -> None:
        """Atomically persist state to disk with restrictive permissions."""
        try:
            self._state_file.parent.mkdir(parents=True, exist_ok=True)
            if self._state_file.parent != Path("."):
                apply_private_permissions(self._state_file.parent, directory=True)

            temporary_file = self._state_file.with_suffix(self._state_file.suffix + ".tmp")
            temporary_file.write_text(json.dumps(data, ensure_ascii=True, indent=2), encoding="utf-8")
            apply_private_permissions(temporary_file)
            temporary_file.replace(self._state_file)
            apply_private_permissions(self._state_file)
        except OSError:
            return
