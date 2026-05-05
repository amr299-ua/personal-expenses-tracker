"""Tests for the security module: encryption, lock, backups, audit logging."""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from expenses_tracker.security import (
    AuditLog,
    BackupManager,
    DatabaseEncryption,
    KeyDerivation,
    LockManager,
    SQLCipherManager,
    apply_private_permissions,
    sanitize_spreadsheet_text,
    verify_password,
)

# ---------------------------------------------------------------------------
# sanitize_spreadsheet_text / apply_private_permissions (existing)
# ---------------------------------------------------------------------------


class TestSanitizeSpreadsheetText:
    def test_prefixes_formula_triggers(self):
        assert sanitize_spreadsheet_text("=1+1") == "'=1+1"
        assert sanitize_spreadsheet_text("+SUM(1,1)") == "'+SUM(1,1)"
        assert sanitize_spreadsheet_text("-10+20") == "'-10+20"
        assert sanitize_spreadsheet_text("@cmd") == "'@cmd"

    def test_handles_leading_whitespace_before_formula(self):
        assert sanitize_spreadsheet_text("  =1+1") == "'  =1+1"

    def test_removes_illegal_xlsx_control_chars(self):
        assert sanitize_spreadsheet_text("safe\x01text") == "safetext"

    def test_normal_text_unchanged(self):
        assert sanitize_spreadsheet_text("hello world") == "hello world"


class TestApplyPrivatePermissions:
    def test_sets_file_mode_on_posix(self, tmp_path):
        if os.name == "nt":
            return
        file_path = tmp_path / "private.txt"
        file_path.write_text("secret", encoding="utf-8")
        apply_private_permissions(file_path)
        mode = stat.S_IMODE(file_path.stat().st_mode)
        assert mode == 0o600

    def test_sets_directory_mode_on_posix(self, tmp_path):
        if os.name == "nt":
            return
        dir_path = tmp_path / "private_dir"
        dir_path.mkdir()
        apply_private_permissions(dir_path, directory=True)
        mode = stat.S_IMODE(dir_path.stat().st_mode)
        assert mode == 0o700

    def test_nonexistent_path_does_not_raise(self):
        apply_private_permissions(Path("/nonexistent/path/12345"))


# ---------------------------------------------------------------------------
# KeyDerivation / verify_password
# ---------------------------------------------------------------------------


class TestKeyDerivation:
    def test_derive_key_returns_32_bytes_url_safe(self):
        key, salt = KeyDerivation.derive_key("mypassword")
        assert len(key) == 44  # base64 url-safe of 32 bytes
        assert len(salt) == KeyDerivation.SALT_SIZE

    def test_derive_key_deterministic_with_same_salt(self):
        _, salt = KeyDerivation.derive_key("test")
        key1, _ = KeyDerivation.derive_key("test", salt)
        key2, _ = KeyDerivation.derive_key("test", salt)
        assert key1 == key2

    def test_different_passwords_produce_different_keys(self):
        key1, _ = KeyDerivation.derive_key("password1")
        key2, _ = KeyDerivation.derive_key("password2")
        assert key1 != key2

    def test_same_password_different_salt_different_key(self):
        key1, _ = KeyDerivation.derive_key("test", os.urandom(32))
        key2, _ = KeyDerivation.derive_key("test", os.urandom(32))
        assert key1 != key2

    def test_hash_password_format(self):
        h = KeyDerivation.hash_password("test123")
        parts = h.split(":")
        assert len(parts) == 2
        salt_b64, key_b64 = parts
        assert len(base64.urlsafe_b64decode(salt_b64)) == KeyDerivation.SALT_SIZE


class TestVerifyPassword:
    def test_correct_password_verifies(self):
        h = KeyDerivation.hash_password("mypassword")
        assert verify_password("mypassword", h) is True

    def test_wrong_password_fails(self):
        h = KeyDerivation.hash_password("mypassword")
        assert verify_password("wrongpassword", h) is False

    def test_empty_password(self):
        h = KeyDerivation.hash_password("")
        assert verify_password("", h) is True

    def test_invalid_hash_returns_false(self):
        assert verify_password("test", "invalid_hash") is False

    def test_empty_hash_returns_false(self):
        assert verify_password("test", "") is False


import base64  # noqa: E402

# ---------------------------------------------------------------------------
# LockManager
# ---------------------------------------------------------------------------


class TestLockManager:
    def test_set_and_verify_lock(self, tmp_path, monkeypatch):
        monkeypatch.setattr("expenses_tracker.security.DATA_DIR", tmp_path)
        monkeypatch.setattr("expenses_tracker.security.LOCK_FILE", tmp_path / ".lock")

        LockManager.set_lock("1234")
        assert LockManager.is_lock_set() is True
        assert LockManager.verify("1234") is True
        assert LockManager.verify("wrong") is False

    def test_remove_lock(self, tmp_path, monkeypatch):
        monkeypatch.setattr("expenses_tracker.security.DATA_DIR", tmp_path)
        monkeypatch.setattr("expenses_tracker.security.LOCK_FILE", tmp_path / ".lock")

        LockManager.set_lock("1234")
        assert LockManager.is_lock_set() is True
        LockManager.remove_lock()
        assert LockManager.is_lock_set() is False

    def test_change_password(self, tmp_path, monkeypatch):
        monkeypatch.setattr("expenses_tracker.security.DATA_DIR", tmp_path)
        monkeypatch.setattr("expenses_tracker.security.LOCK_FILE", tmp_path / ".lock")

        LockManager.set_lock("old_pass")
        result = LockManager.change_password("old_pass", "new_pass")
        assert result is True
        assert LockManager.verify("new_pass") is True
        assert LockManager.verify("old_pass") is False

    def test_change_password_wrong_current(self, tmp_path, monkeypatch):
        monkeypatch.setattr("expenses_tracker.security.DATA_DIR", tmp_path)
        monkeypatch.setattr("expenses_tracker.security.LOCK_FILE", tmp_path / ".lock")

        LockManager.set_lock("1234")
        result = LockManager.change_password("wrong", "new_pass")
        assert result is False

    def test_set_lock_from_hash(self, tmp_path, monkeypatch):
        monkeypatch.setattr("expenses_tracker.security.DATA_DIR", tmp_path)
        monkeypatch.setattr("expenses_tracker.security.LOCK_FILE", tmp_path / ".lock")

        h = KeyDerivation.hash_password("test_pin")
        LockManager.set_lock_from_hash(h)
        assert LockManager.is_lock_set() is True
        assert LockManager.verify("test_pin") is True

    def test_no_lock_returns_false_for_verify(self, tmp_path, monkeypatch):
        monkeypatch.setattr("expenses_tracker.security.DATA_DIR", tmp_path)
        monkeypatch.setattr("expenses_tracker.security.LOCK_FILE", tmp_path / ".lock")
        assert LockManager.verify("anything") is False

    def test_is_lock_set_when_no_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr("expenses_tracker.security.DATA_DIR", tmp_path)
        monkeypatch.setattr("expenses_tracker.security.LOCK_FILE", tmp_path / ".lock")
        assert LockManager.is_lock_set() is False

    def test_activate_and_deactivate_lock(self, tmp_path, monkeypatch):
        monkeypatch.setattr("expenses_tracker.security.DATA_DIR", tmp_path)
        monkeypatch.setattr("expenses_tracker.security.LOCK_FILE", tmp_path / ".lock")
        monkeypatch.setattr("expenses_tracker.security.LOCK_ACTIVE_FILE", tmp_path / ".lock_active")

        LockManager.set_lock("1234")
        assert LockManager.is_lock_active() is False
        LockManager.activate_lock()
        assert LockManager.is_lock_active() is True
        LockManager.deactivate_lock()
        assert LockManager.is_lock_active() is False
        # lock file still exists
        assert LockManager.is_lock_set() is True

    def test_is_lock_active_requires_both_files(self, tmp_path, monkeypatch):
        monkeypatch.setattr("expenses_tracker.security.DATA_DIR", tmp_path)
        monkeypatch.setattr("expenses_tracker.security.LOCK_FILE", tmp_path / ".lock")
        monkeypatch.setattr("expenses_tracker.security.LOCK_ACTIVE_FILE", tmp_path / ".lock_active")

        assert LockManager.is_lock_active() is False
        LockManager.activate_lock()
        assert LockManager.is_lock_active() is False  # no lock file yet
        LockManager.set_lock("1234")
        assert LockManager.is_lock_active() is True


# ---------------------------------------------------------------------------
# DatabaseEncryption
# ---------------------------------------------------------------------------


class TestDatabaseEncryption:
    def test_encrypt_and_decrypt_file(self, tmp_path):
        original = tmp_path / "test.db"
        original.write_bytes(b"hello world database content")

        key = Fernet.generate_key()
        enc_path = DatabaseEncryption.encrypt_file(original, key)

        assert enc_path.exists()
        assert enc_path.name == "test.db.enc"
        assert enc_path.read_bytes() != original.read_bytes()

        dec_path = DatabaseEncryption.decrypt_file(enc_path, key)
        assert dec_path.read_bytes() == b"hello world database content"

    def test_decrypt_to_specific_path(self, tmp_path):
        original = tmp_path / "source.db"
        original.write_bytes(b"data")

        key = Fernet.generate_key()
        enc_path = DatabaseEncryption.encrypt_file(original, key)

        output = tmp_path / "restored.db"
        DatabaseEncryption.decrypt_file(enc_path, key, output_path=output)
        assert output.read_bytes() == b"data"

    def test_is_encrypted_detects_enc_file(self, tmp_path):
        db_path = tmp_path / "test.db"
        enc_path = tmp_path / "test.db.enc"

        db_path.write_bytes(b"plain")
        assert DatabaseEncryption.is_encrypted(db_path) is False

        db_path.unlink()
        enc_path.write_bytes(b"encrypted")
        assert DatabaseEncryption.is_encrypted(db_path) is True


from cryptography.fernet import Fernet  # noqa: E402

# ---------------------------------------------------------------------------
# BackupManager
# ---------------------------------------------------------------------------


class TestBackupManager:
    def test_create_backup(self, tmp_path, monkeypatch):
        monkeypatch.setattr("expenses_tracker.security.BACKUPS_DIR", tmp_path / "backups")
        monkeypatch.setattr("expenses_tracker.security.DATA_DIR", tmp_path)

        db_path = tmp_path / "expenses.db"
        db_path.write_bytes(b"database content")

        backup_path = BackupManager.create_backup(db_path)
        assert backup_path.exists()
        assert backup_path.read_bytes() == b"database content"
        assert backup_path.name.startswith("expenses_")

    def test_create_backup_raises_for_missing_db(self, tmp_path, monkeypatch):
        monkeypatch.setattr("expenses_tracker.security.BACKUPS_DIR", tmp_path / "backups")

        with pytest.raises(FileNotFoundError):
            BackupManager.create_backup(tmp_path / "nonexistent.db")

    def test_rotate_backups(self, tmp_path, monkeypatch):
        backups_dir = tmp_path / "backups"
        backups_dir.mkdir()
        monkeypatch.setattr("expenses_tracker.security.BACKUPS_DIR", backups_dir)

        for i in range(5):
            (backups_dir / f"expenses_2026010{i}_000000.db").write_bytes(b"data")

        removed = BackupManager.rotate_backups(max_backups=3)
        remaining = list(backups_dir.glob("expenses_*.db"))
        assert len(remaining) == 3
        assert len(removed) == 2

    def test_list_backups(self, tmp_path, monkeypatch):
        backups_dir = tmp_path / "backups"
        backups_dir.mkdir()
        monkeypatch.setattr("expenses_tracker.security.BACKUPS_DIR", backups_dir)

        db_path = tmp_path / "expenses.db"
        db_path.write_bytes(b"data")
        BackupManager.create_backup(db_path)

        backups = BackupManager.list_backups()
        assert len(backups) >= 1
        assert "name" in backups[0]
        assert "size" in backups[0]

    def test_restore_backup(self, tmp_path, monkeypatch):
        backups_dir = tmp_path / "backups"
        backups_dir.mkdir()
        monkeypatch.setattr("expenses_tracker.security.BACKUPS_DIR", backups_dir)

        original = tmp_path / "expenses.db"
        original.write_bytes(b"original content")

        backup_path = BackupManager.create_backup(original)

        original.write_bytes(b"modified content")

        restored = BackupManager.restore_backup(backup_path.name, original)
        assert restored.read_bytes() == b"original content"

    def test_restore_nonexistent_backup_raises(self, tmp_path, monkeypatch):
        monkeypatch.setattr("expenses_tracker.security.BACKUPS_DIR", tmp_path / "backups")

        with pytest.raises(FileNotFoundError):
            BackupManager.restore_backup("nonexistent.db")


# ---------------------------------------------------------------------------
# AuditLog
# ---------------------------------------------------------------------------


class TestAuditLog:
    def test_log_and_read_entries(self, tmp_path, monkeypatch):
        log_file = tmp_path / "audit_log.jsonl"
        monkeypatch.setattr("expenses_tracker.security.DATA_DIR", tmp_path)
        monkeypatch.setattr(AuditLog, "LOG_FILE", log_file)

        AuditLog.log("create", entity="transaction", entity_id=1, details="test")
        AuditLog.log("update", entity="transaction", entity_id=2, details="updated")

        entries = AuditLog.get_entries(limit=10)
        assert len(entries) == 2
        assert entries[0]["action"] == "create"
        assert entries[1]["action"] == "update"

    def test_get_entries_with_limit(self, tmp_path, monkeypatch):
        log_file = tmp_path / "audit_log.jsonl"
        monkeypatch.setattr("expenses_tracker.security.DATA_DIR", tmp_path)
        monkeypatch.setattr(AuditLog, "LOG_FILE", log_file)

        for i in range(5):
            AuditLog.log("create", entity="test", entity_id=i)

        entries = AuditLog.get_entries(limit=3)
        assert len(entries) == 3

    def test_clear_log(self, tmp_path, monkeypatch):
        log_file = tmp_path / "audit_log.jsonl"
        monkeypatch.setattr("expenses_tracker.security.DATA_DIR", tmp_path)
        monkeypatch.setattr(AuditLog, "LOG_FILE", log_file)

        AuditLog.log("test", entity="test")
        assert log_file.exists()
        AuditLog.clear()
        assert not log_file.exists()

    def test_get_entries_empty_log(self, tmp_path, monkeypatch):
        log_file = tmp_path / "audit_log.jsonl"
        monkeypatch.setattr("expenses_tracker.security.DATA_DIR", tmp_path)
        monkeypatch.setattr(AuditLog, "LOG_FILE", log_file)

        entries = AuditLog.get_entries()
        assert entries == []

    def test_log_entry_has_required_fields(self, tmp_path, monkeypatch):
        log_file = tmp_path / "audit_log.jsonl"
        monkeypatch.setattr("expenses_tracker.security.DATA_DIR", tmp_path)
        monkeypatch.setattr(AuditLog, "LOG_FILE", log_file)

        AuditLog.log("delete", entity="transaction", entity_id=5, details="deleted by user")
        entries = AuditLog.get_entries()
        entry = entries[0]

        assert "timestamp" in entry
        assert entry["action"] == "delete"
        assert entry["entity"] == "transaction"
        assert entry["entity_id"] == 5
        assert entry["details"] == "deleted by user"


# ---------------------------------------------------------------------------
# SQLCipherManager
# ---------------------------------------------------------------------------

_pysqlcipher3_available = True
try:
    import pysqlcipher3  # noqa: F401
except ImportError:
    _pysqlcipher3_available = False


class TestSQLCipherManager:
    def test_generate_key_is_hex_64_chars(self):
        key = SQLCipherManager.generate_key()
        assert len(key) == 64
        int(key, 16)  # valid hex

    def test_store_and_retrieve_key(self, tmp_path, monkeypatch):
        monkeypatch.setattr("expenses_tracker.security.DATA_DIR", tmp_path)
        monkeypatch.setattr(SQLCipherManager, "KEY_FILE", tmp_path / ".dbkey")

        key = SQLCipherManager.generate_key()
        SQLCipherManager.store_key(key, "mypin")
        retrieved = SQLCipherManager.retrieve_key("mypin")
        assert retrieved == key

    def test_retrieve_key_wrong_pin(self, tmp_path, monkeypatch):
        monkeypatch.setattr("expenses_tracker.security.DATA_DIR", tmp_path)
        monkeypatch.setattr(SQLCipherManager, "KEY_FILE", tmp_path / ".dbkey")

        key = SQLCipherManager.generate_key()
        SQLCipherManager.store_key(key, "mypin")
        assert SQLCipherManager.retrieve_key("wrongpin") is None

    def test_is_encrypted_db_detects_plaintext(self, tmp_path):
        db_path = tmp_path / "plain.db"
        import sqlite3

        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE t (id INTEGER)")
        conn.close()
        assert SQLCipherManager.is_encrypted_db(db_path) is False

    def test_remove_key_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr("expenses_tracker.security.DATA_DIR", tmp_path)
        monkeypatch.setattr(SQLCipherManager, "KEY_FILE", tmp_path / ".dbkey")

        SQLCipherManager.KEY_FILE.write_text("test")
        SQLCipherManager.remove_key_file()
        assert not SQLCipherManager.KEY_FILE.exists()

    @pytest.mark.skipif(not _pysqlcipher3_available, reason="pysqlcipher3 not installed")
    def test_migrate_to_encrypted_creates_encrypted_db(self, tmp_path, monkeypatch):
        monkeypatch.setattr("expenses_tracker.security.DATA_DIR", tmp_path)
        monkeypatch.setattr("expenses_tracker.security.BACKUPS_DIR", tmp_path / "backups")

        db_path = tmp_path / "expenses.db"
        import sqlite3

        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE t (id INTEGER)")
        conn.close()

        key = SQLCipherManager.generate_key()
        SQLCipherManager.migrate_to_encrypted(db_path, key)
        assert SQLCipherManager.is_encrypted_db(db_path) is True
