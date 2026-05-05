"""Tests for DatabaseService infrastructure wrapper."""

from __future__ import annotations

from pathlib import Path

import pytest

from expenses_tracker.services import DatabaseService


@pytest.fixture
def database_service(db):
    """Provide a DatabaseService backed by the test database."""
    return DatabaseService(db)


class TestDatabaseService:
    def test_db_path(self, database_service, db):
        assert database_service.db_path == db.db_path
        assert isinstance(database_service.db_path, Path)

    def test_create_backup(self, database_service, tmp_path):
        backup = database_service.create_backup()
        assert backup.exists()
        assert backup.suffix == ".db"

    def test_get_automation_config_default(self, database_service):
        config = database_service.get_automation_config()
        assert isinstance(config, dict)
        assert "enabled" in config
        assert "schedule_type" in config
        assert "schedule_day" in config
        assert "export_format" in config
