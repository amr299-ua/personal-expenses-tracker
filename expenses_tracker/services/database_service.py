"""Infrastructure service for database concerns.

Wraps low-level database operations like backup, encryption checks and
automation config so that the GUI doesn't call self.database directly.
"""

from __future__ import annotations

from pathlib import Path  # noqa: TC003
from typing import Any

from expenses_tracker.db import ExpenseDatabase  # noqa: TC001


class DatabaseService:
    """Infrastructure operations: backup, encryption, db path, automation config."""

    def __init__(self, database: ExpenseDatabase) -> None:
        self._database = database

    @property
    def db_path(self) -> Path:
        """Return the filesystem path of the database."""
        return self._database.db_path

    def create_backup(self) -> Path:
        """Create a backup of the database."""
        return self._database.create_backup()

    def get_automation_config(self) -> dict[str, Any]:
        """Return the current automation configuration."""
        return self._database.get_automation_config()

    def save_automation_config(self, config: dict[str, Any]) -> None:
        """Persist the automation configuration."""
        self._database.save_automation_config(config)
