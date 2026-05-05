from __future__ import annotations

import base64
import json
import os
import secrets
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE

SPREADSHEET_FORMULA_PREFIXES = ("=", "+", "-", "@")

DATA_DIR = Path("data")
LOCK_FILE = DATA_DIR / ".lock"
LOCK_ACTIVE_FILE = DATA_DIR / ".lock_active"
BACKUPS_DIR = DATA_DIR / "backups"
KEY_FILE = DATA_DIR / ".key"
MAX_BACKUPS = 10


def apply_private_permissions(path: str | Path, *, directory: bool = False) -> None:
    mode = 0o700 if directory else 0o600
    try:
        os.chmod(path, mode)
    except (AttributeError, NotImplementedError, OSError):
        return


def sanitize_spreadsheet_text(value: Any) -> str:
    text = cast(str, ILLEGAL_CHARACTERS_RE.sub("", str(value)))
    stripped = text.lstrip()
    if stripped.startswith(SPREADSHEET_FORMULA_PREFIXES):
        return "'" + text
    return text


class KeyDerivation:
    ITERATIONS = 600_000
    SALT_SIZE = 32

    @staticmethod
    def derive_key(password: str, salt: bytes | None = None) -> tuple[bytes, bytes]:
        if salt is None:
            salt = os.urandom(KeyDerivation.SALT_SIZE)
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=KeyDerivation.ITERATIONS,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8")))
        return key, salt

    @staticmethod
    def hash_password(password: str) -> str:
        salt = os.urandom(KeyDerivation.SALT_SIZE)
        key, _ = KeyDerivation.derive_key(password, salt)
        return base64.urlsafe_b64encode(salt).decode() + ":" + key.decode()


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt_b64, stored_key_b64 = stored_hash.split(":", 1)
        salt = base64.urlsafe_b64decode(salt_b64)
        derived_key, _ = KeyDerivation.derive_key(password, salt)
        stored_key = stored_key_b64.encode()
        return secrets.compare_digest(derived_key, stored_key)
    except (ValueError, Exception):
        return False


class LockManager:
    @staticmethod
    def is_lock_set() -> bool:
        return LOCK_FILE.exists()

    @staticmethod
    def set_lock(password: str) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        hash_value = KeyDerivation.hash_password(password)
        LOCK_FILE.write_text(hash_value, encoding="utf-8")
        apply_private_permissions(LOCK_FILE)

    @staticmethod
    def verify(password: str) -> bool:
        if not LOCK_FILE.exists():
            return False
        stored_hash = LOCK_FILE.read_text(encoding="utf-8").strip()
        return verify_password(password, stored_hash)

    @staticmethod
    def remove_lock() -> None:
        try:
            LOCK_FILE.unlink()
        except OSError:
            pass

    @staticmethod
    def set_lock_from_hash(hash_value: str) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        LOCK_FILE.write_text(hash_value, encoding="utf-8")
        apply_private_permissions(LOCK_FILE)

    @staticmethod
    def change_password(current_password: str, new_password: str) -> bool:
        if not LockManager.verify(current_password):
            return False
        LockManager.set_lock(new_password)
        return True

    @staticmethod
    def is_lock_active() -> bool:
        """Return True if the lock was explicitly activated (lock at startup)."""
        return LOCK_FILE.exists() and LOCK_ACTIVE_FILE.exists()

    @staticmethod
    def activate_lock() -> None:
        """Mark the lock as active (PIN will be requested at startup)."""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        LOCK_ACTIVE_FILE.write_text("active", encoding="utf-8")
        apply_private_permissions(LOCK_ACTIVE_FILE)

    @staticmethod
    def deactivate_lock() -> None:
        """Deactivate the startup lock (keeps PIN stored)."""
        try:
            LOCK_ACTIVE_FILE.unlink()
        except OSError:
            pass


class DatabaseEncryption:
    @staticmethod
    def encrypt_file(source_path: Path, key: bytes) -> Path:
        fernet = Fernet(key)
        data = source_path.read_bytes()
        encrypted = fernet.encrypt(data)
        enc_path = Path(str(source_path) + ".enc")
        enc_path.write_bytes(encrypted)
        apply_private_permissions(enc_path)
        return enc_path

    @staticmethod
    def decrypt_file(enc_path: Path, key: bytes, output_path: Path | None = None) -> Path:
        fernet = Fernet(key)
        encrypted = enc_path.read_bytes()
        decrypted = fernet.decrypt(encrypted)
        if output_path is None:
            output_path = Path(str(enc_path).rstrip(".enc"))
        output_path.write_bytes(decrypted)
        apply_private_permissions(output_path)
        return output_path

    @staticmethod
    def is_encrypted(db_path: Path) -> bool:
        return Path(str(db_path) + ".enc").exists() and not db_path.exists()


class BackupManager:
    @staticmethod
    def ensure_backup_dir() -> Path:
        BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
        apply_private_permissions(BACKUPS_DIR, directory=True)
        return BACKUPS_DIR

    @staticmethod
    def create_backup(db_path: str | Path = "data/expenses.db") -> Path:
        source = Path(db_path)
        if not source.exists():
            raise FileNotFoundError(f"Database not found: {source}")

        BackupManager.ensure_backup_dir()
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_name = f"expenses_{timestamp}.db"
        backup_path = BACKUPS_DIR / backup_name

        shutil.copy2(source, backup_path)
        apply_private_permissions(backup_path)

        BackupManager.rotate_backups()
        return backup_path

    @staticmethod
    def rotate_backups(max_backups: int = MAX_BACKUPS) -> list[Path]:
        if not BACKUPS_DIR.exists():
            return []
        backups = sorted(
            BACKUPS_DIR.glob("expenses_*.db"),
            key=lambda p: p.name,
            reverse=True,
        )
        removed = []
        for old_backup in backups[max_backups:]:
            try:
                old_backup.unlink()
                removed.append(old_backup)
            except OSError:
                pass
        return removed

    @staticmethod
    def list_backups() -> list[dict[str, Any]]:
        if not BACKUPS_DIR.exists():
            return []
        backups = []
        for path in sorted(BACKUPS_DIR.glob("expenses_*.db"), key=lambda p: p.name, reverse=True):
            stat = path.stat()
            backups.append({
                "path": str(path),
                "name": path.name,
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            })
        return backups

    @staticmethod
    def restore_backup(backup_name: str, db_path: str | Path = "data/expenses.db") -> Path:
        backup_file = BACKUPS_DIR / backup_name
        if not backup_file.exists():
            raise FileNotFoundError(f"Backup not found: {backup_file}")

        target = Path(db_path)
        shutil.copy2(backup_file, target)
        apply_private_permissions(target)
        return target


class AuditLog:
    LOG_FILE = DATA_DIR / "audit_log.jsonl"

    ACTION_CREATE = "create"
    ACTION_UPDATE = "update"
    ACTION_DELETE = "delete"
    ACTION_LOGIN = "login"
    ACTION_BACKUP = "backup"
    ACTION_RESTORE = "restore"
    ACTION_LOCK_SET = "lock_set"
    ACTION_LOCK_CHANGE = "lock_change"

    @staticmethod
    def log(action: str, entity: str = "", entity_id: int | None = None, details: str = "") -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "entity": entity,
            "entity_id": entity_id,
            "details": details,
        }
        with open(AuditLog.LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    @staticmethod
    def get_entries(limit: int = 100) -> list[dict[str, Any]]:
        if not AuditLog.LOG_FILE.exists():
            return []
        entries = []
        with open(AuditLog.LOG_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return entries[-limit:]

    @staticmethod
    def clear() -> None:
        try:
            AuditLog.LOG_FILE.unlink()
        except OSError:
            pass


class SQLCipherManager:
    KEY_FILE = DATA_DIR / ".dbkey"

    @staticmethod
    def is_encrypted_db(db_path: Path) -> bool:
        """Detect whether the database is already encrypted with SQLCipher."""
        if not db_path.exists():
            return False
        try:
            import sqlite3

            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' LIMIT 1")
            cursor.fetchone()
            conn.close()
            return False
        except Exception:
            return True

    @staticmethod
    def generate_key() -> str:
        """Generate a random 32-byte hex key for SQLCipher."""
        return secrets.token_hex(32)

    @staticmethod
    def store_key(key: str, master_password: str) -> None:
        """Encrypt the SQLCipher key with the user's PIN and save it."""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        derived_key, salt = KeyDerivation.derive_key(master_password)
        fernet = Fernet(derived_key)
        encrypted_key = fernet.encrypt(key.encode("utf-8"))
        payload = base64.urlsafe_b64encode(salt).decode() + ":" + base64.urlsafe_b64encode(encrypted_key).decode()
        SQLCipherManager.KEY_FILE.write_text(payload, encoding="utf-8")
        apply_private_permissions(SQLCipherManager.KEY_FILE)

    @staticmethod
    def retrieve_key(master_password: str) -> str | None:
        """Decrypt and return the SQLCipher key."""
        if not SQLCipherManager.KEY_FILE.exists():
            return None
        try:
            payload = SQLCipherManager.KEY_FILE.read_text(encoding="utf-8").strip()
            salt_b64, encrypted_b64 = payload.split(":", 1)
            salt = base64.urlsafe_b64decode(salt_b64)
            derived_key, _ = KeyDerivation.derive_key(master_password, salt)
            fernet = Fernet(derived_key)
            encrypted_key = base64.urlsafe_b64decode(encrypted_b64)
            key = fernet.decrypt(encrypted_key).decode("utf-8")
            return key
        except Exception:
            return None

    @staticmethod
    def migrate_to_encrypted(db_path: Path, key: str) -> None:
        """Migrate a plaintext database to an SQLCipher-encrypted database."""
        try:
            from pysqlcipher3 import dbapi2 as sqlite
        except ImportError as exc:
            raise ImportError("pysqlcipher3 is required for database encryption. Install it with: pip install pysqlcipher3") from exc

        if not db_path.exists():
            raise FileNotFoundError(f"Database not found: {db_path}")

        # Create a backup before migration
        BackupManager.create_backup(db_path)

        temp_encrypted = db_path.with_suffix(".db.encrypted")

        source_conn = sqlite.connect(str(db_path))
        source_conn.execute(f"PRAGMA key = '{key}'")
        source_conn.execute("ATTACH DATABASE ? AS encrypted KEY ?", (str(temp_encrypted), key))
        source_conn.execute("SELECT sqlcipher_export('encrypted')")
        source_conn.execute("DETACH DATABASE encrypted")
        source_conn.close()

        # Replace original with encrypted version
        db_path.unlink()
        shutil.move(str(temp_encrypted), str(db_path))
        apply_private_permissions(db_path)

    @staticmethod
    def remove_key_file() -> None:
        try:
            SQLCipherManager.KEY_FILE.unlink()
        except OSError:
            pass
