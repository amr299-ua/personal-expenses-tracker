"""Tests for the cloud_sync module."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from expenses_tracker.cloud_sync import (
    CloudProvider,
    CloudSyncManager,
)
from expenses_tracker.security import DatabaseEncryption


class FakeProvider(CloudProvider):
    """In-memory fake cloud provider for testing."""

    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}

    def upload(self, local_path: Path, remote_path: str) -> None:
        self.files[remote_path] = local_path.read_bytes()

    def download(self, remote_path: str, local_path: Path) -> None:
        if remote_path not in self.files:
            raise FileNotFoundError(remote_path)
        local_path.write_bytes(self.files[remote_path])

    def list_files(self, remote_dir: str) -> list[dict[str, Any]]:
        return [{"name": k} for k in self.files if k.startswith(remote_dir)]

    def delete(self, remote_path: str) -> None:
        self.files.pop(remote_path, None)


@pytest.fixture
def fake_provider():
    return FakeProvider()


@pytest.fixture
def sync_manager(fake_provider):
    key = DatabaseEncryption.encrypt_file.__wrapped__ if hasattr(DatabaseEncryption.encrypt_file, "__wrapped__") else None
    # Use a fixed Fernet key for tests
    from cryptography.fernet import Fernet

    encryption_key = Fernet.generate_key()
    return CloudSyncManager(fake_provider, encryption_key)


class TestCloudSyncManager:
    def test_sync_up_creates_remote_files(self, tmp_path, sync_manager):
        db_path = tmp_path / "expenses.db"
        db_path.write_bytes(b"plain database content")
        sync_manager.sync_up(db_path)
        assert f"/{CloudSyncManager.REMOTE_DB_NAME}" in sync_manager.provider.files
        assert f"/{CloudSyncManager.REMOTE_META_NAME}" in sync_manager.provider.files

    def test_sync_down_restores_database(self, tmp_path, sync_manager):
        db_path = tmp_path / "expenses.db"
        db_path.write_bytes(b"original content")
        sync_manager.sync_up(db_path)

        db_path.write_bytes(b"modified content")
        sync_manager.sync_down(db_path)
        assert db_path.read_bytes() == b"original content"

    def test_auto_sync_calls_sync_up(self, tmp_path, sync_manager):
        db_path = tmp_path / "expenses.db"
        db_path.write_bytes(b"plain database content")
        sync_manager.auto_sync(db_path)
        assert f"/{CloudSyncManager.REMOTE_DB_NAME}" in sync_manager.provider.files

    def test_encrypted_upload_is_different_from_plaintext(self, tmp_path, sync_manager):
        db_path = tmp_path / "expenses.db"
        db_path.write_bytes(b"plain database content")
        sync_manager.sync_up(db_path)
        uploaded = sync_manager.provider.files[f"/{CloudSyncManager.REMOTE_DB_NAME}"]
        assert uploaded != b"plain database content"


class TestFakeProvider:
    def test_upload_and_download(self, tmp_path):
        provider = FakeProvider()
        local = tmp_path / "file.txt"
        local.write_text("hello")
        provider.upload(local, "/file.txt")
        assert "/file.txt" in provider.files

        dest = tmp_path / "downloaded.txt"
        provider.download("/file.txt", dest)
        assert dest.read_text() == "hello"

    def test_download_missing_raises(self, tmp_path):
        provider = FakeProvider()
        with pytest.raises(FileNotFoundError):
            provider.download("/missing", tmp_path / "x")

    def test_list_files(self):
        provider = FakeProvider()
        provider.files = {"/a.txt": b"a", "/b.txt": b"b", "/c.png": b"c"}
        result = provider.list_files("/")
        assert len(result) == 3

    def test_delete(self):
        provider = FakeProvider()
        provider.files = {"/a.txt": b"a"}
        provider.delete("/a.txt")
        assert "/a.txt" not in provider.files
