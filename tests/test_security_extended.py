"""Extended security tests for edge cases."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from expenses_tracker.security import (
    AuditLog,
    BackupManager,
    DatabaseEncryption,
    KeyDerivation,
    LockManager,
    SQLCipherManager,
    apply_private_permissions,
    verify_password,
)

_pysqlcipher3_available = True
try:
    import pysqlcipher3  # noqa: F401
except ImportError:
    _pysqlcipher3_available = False


class TestApplyPrivatePermissions:
    def test_os_error_is_ignored(self, tmp_path):
        path = tmp_path / "file.txt"
        path.write_text("x")
        with patch("os.chmod", side_effect=OSError("mock")):
            apply_private_permissions(path)
        assert True  # no raise


class TestKeyDerivation:
    def test_hash_password_different_salts(self):
        h1 = KeyDerivation.hash_password("password")
        h2 = KeyDerivation.hash_password("password")
        assert h1 != h2  # different salts


class TestVerifyPassword:
    def test_malformed_hash_no_colon(self):
        assert verify_password("pass", "nocolon") is False

    def test_malformed_hash_invalid_base64(self):
        assert verify_password("pass", "!!!:@@@") is False


class TestLockManager:
    def test_set_lock_creates_data_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr("expenses_tracker.security.DATA_DIR", tmp_path)
        monkeypatch.setattr("expenses_tracker.security.LOCK_FILE", tmp_path / ".lock")
        LockManager.set_lock("1234")
        assert (tmp_path / ".lock").exists()

    def test_remove_lock_when_no_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr("expenses_tracker.security.DATA_DIR", tmp_path)
        monkeypatch.setattr("expenses_tracker.security.LOCK_FILE", tmp_path / ".lock")
        LockManager.remove_lock()
        assert LockManager.is_lock_set() is False


class TestDatabaseEncryption:
    def test_decrypt_file_default_output(self, tmp_path):
        from cryptography.fernet import Fernet
        key = Fernet.generate_key()
        source = tmp_path / "test.db"
        source.write_bytes(b"data")
        enc = DatabaseEncryption.encrypt_file(source, key)
        dec = DatabaseEncryption.decrypt_file(enc, key)
        assert dec.read_bytes() == b"data"
        assert dec.name == "test.db"


class TestBackupManager:
    def test_rotate_backups_no_dir(self, monkeypatch):
        monkeypatch.setattr("expenses_tracker.security.BACKUPS_DIR", Path("/nonexistent"))
        removed = BackupManager.rotate_backups()
        assert removed == []

    def test_list_backups_no_dir(self, monkeypatch):
        monkeypatch.setattr("expenses_tracker.security.BACKUPS_DIR", Path("/nonexistent"))
        assert BackupManager.list_backups() == []

    def test_create_backup_creates_dir(self, tmp_path, monkeypatch):
        backups_dir = tmp_path / "backups"
        monkeypatch.setattr("expenses_tracker.security.BACKUPS_DIR", backups_dir)
        monkeypatch.setattr("expenses_tracker.security.DATA_DIR", tmp_path)
        db_path = tmp_path / "expenses.db"
        db_path.write_bytes(b"data")
        path = BackupManager.create_backup(db_path)
        assert path.exists()
        assert backups_dir.exists()


class TestAuditLog:
    def test_clear_when_no_file(self, tmp_path, monkeypatch):
        log_file = tmp_path / "audit.jsonl"
        monkeypatch.setattr("expenses_tracker.security.DATA_DIR", tmp_path)
        monkeypatch.setattr(AuditLog, "LOG_FILE", log_file)
        AuditLog.clear()
        assert not log_file.exists()

    def test_get_entries_corrupted_line(self, tmp_path, monkeypatch):
        log_file = tmp_path / "audit.jsonl"
        monkeypatch.setattr("expenses_tracker.security.DATA_DIR", tmp_path)
        monkeypatch.setattr(AuditLog, "LOG_FILE", log_file)
        log_file.write_text('{"action":"create"}\nnot json\n{"action":"delete"}\n', encoding="utf-8")
        entries = AuditLog.get_entries(limit=10)
        assert len(entries) == 2


class TestSQLCipherManager:
    def test_is_encrypted_db_missing_file(self):
        assert SQLCipherManager.is_encrypted_db(Path("/nonexistent/db.db")) is False

    def test_retrieve_key_missing_file(self):
        assert SQLCipherManager.retrieve_key("pin") is None

    def test_remove_key_file_missing(self):
        SQLCipherManager.remove_key_file()
        assert True  # no raise

    @pytest.mark.skipif(not _pysqlcipher3_available, reason="pysqlcipher3 not installed")
    def test_migrate_to_encrypted_missing_db(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            SQLCipherManager.migrate_to_encrypted(tmp_path / "missing.db", "key")
