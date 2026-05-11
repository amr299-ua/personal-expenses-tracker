from __future__ import annotations

import base64
import contextlib
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

from expenses_tracker.utils import resolve_app_data_dir

SPREADSHEET_FORMULA_PREFIXES = ("=", "+", "-", "@")

DATA_DIR = resolve_app_data_dir()
LOCK_FILE = DATA_DIR / ".lock"
LOCK_ACTIVE_FILE = DATA_DIR / ".lock_active"
BACKUPS_DIR = DATA_DIR / "backups"
KEY_FILE = DATA_DIR / ".key"
MAX_BACKUPS = 10


def apply_private_permissions(path: str | Path, *, directory: bool = False) -> None:
    """Set restrictive file or directory permissions on Unix systems."""
    mode = 0o700 if directory else 0o600
    try:
        os.chmod(path, mode)
    except (AttributeError, NotImplementedError, OSError):
        return


def sanitize_spreadsheet_text(value: Any) -> str:
    """Remove illegal characters and prefix formula-starting values with apostrophe."""
    text = cast("str", ILLEGAL_CHARACTERS_RE.sub("", str(value)))
    stripped = text.lstrip()
    if stripped.startswith(SPREADSHEET_FORMULA_PREFIXES):
        return "'" + text
    return text


class KeyDerivation:
    """PBKDF2-HMAC-SHA256 key derivation utilities."""

    ITERATIONS = 600_000
    SALT_SIZE = 32

    @staticmethod
    def derive_key(password: str, salt: bytes | None = None) -> tuple[bytes, bytes]:
        """Derive a Fernet-compatible key from a password and optional salt."""
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
        """Hash a password with a random salt and return salt:key string."""
        salt = os.urandom(KeyDerivation.SALT_SIZE)
        key, _ = KeyDerivation.derive_key(password, salt)
        return base64.urlsafe_b64encode(salt).decode() + ":" + key.decode()


class CloudSyncSaltManager:
    """Manages a persistent random salt for cloud sync key derivation.

    Generates a random 32-byte salt on first use and stores it in a
    protected file so the same PIN always derives the same encryption
    key without relying on a hardcoded predictable salt.
    """

    SALT_FILE = DATA_DIR / ".cloud_salt"

    @staticmethod
    def get_or_create_salt() -> bytes:
        """Return the persistent cloud sync salt, creating it if needed."""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if CloudSyncSaltManager.SALT_FILE.exists():
            salt_b64 = CloudSyncSaltManager.SALT_FILE.read_text(encoding="utf-8").strip()
            return base64.urlsafe_b64decode(salt_b64)
        salt = os.urandom(KeyDerivation.SALT_SIZE)
        CloudSyncSaltManager.SALT_FILE.write_text(base64.urlsafe_b64encode(salt).decode(), encoding="utf-8")
        apply_private_permissions(CloudSyncSaltManager.SALT_FILE)
        return salt


class AppCrypto:
    """Application-level encryption for sensitive config fields (e.g. SMTP password).

    Generates a random Fernet key on first use and stores it in a protected
    file. This key is independent of the user PIN so background automation
    can still decrypt stored credentials.
    """

    KEY_FILE = DATA_DIR / ".appkey"
    _ENCRYPTED_PREFIX = "ENC:"

    @staticmethod
    def _get_or_create_key() -> bytes:
        """Return the application Fernet key, creating it if needed."""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if AppCrypto.KEY_FILE.exists():
            try:
                key_b64 = AppCrypto.KEY_FILE.read_text(encoding="utf-8").strip()
                key = base64.urlsafe_b64decode(key_b64)
                Fernet(key)  # validate the key is usable
                return key
            except Exception:
                AppCrypto.KEY_FILE.unlink(missing_ok=True)
        key = Fernet.generate_key()
        AppCrypto.KEY_FILE.write_text(key.decode(), encoding="utf-8")
        apply_private_permissions(AppCrypto.KEY_FILE)
        return key

    @staticmethod
    def encrypt(value: str) -> str:
        """Encrypt a plaintext string, returning a base64-encoded prefixed value."""
        if not value:
            return value
        key = AppCrypto._get_or_create_key()
        fernet = Fernet(key)
        encrypted = fernet.encrypt(value.encode("utf-8"))
        return AppCrypto._ENCRYPTED_PREFIX + base64.urlsafe_b64encode(encrypted).decode()

    @staticmethod
    def decrypt(value: str | None) -> str | None:
        """Decrypt a previously encrypted value, or return plaintext as-is."""
        if not value:
            return value
        if not value.startswith(AppCrypto._ENCRYPTED_PREFIX):
            return value
        try:
            key = AppCrypto._get_or_create_key()
            fernet = Fernet(key)
            encrypted = base64.urlsafe_b64decode(value[len(AppCrypto._ENCRYPTED_PREFIX) :])
            return fernet.decrypt(encrypted).decode("utf-8")
        except Exception:
            return None


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a password against a stored salt:key hash using constant-time comparison."""
    try:
        salt_b64, stored_key_b64 = stored_hash.split(":", 1)
        salt = base64.urlsafe_b64decode(salt_b64)
        derived_key, _ = KeyDerivation.derive_key(password, salt)
        stored_key = stored_key_b64.encode()
        return secrets.compare_digest(derived_key, stored_key)
    except Exception:
        return False


class PinValidator:
    """Validates PIN strength, rejecting empty or trivially weak PINs."""

    MIN_LENGTH = 4
    MAX_LENGTH = 64

    _WEAK_PINS: frozenset[str] = frozenset(
        {
            "0000",
            "1111",
            "2222",
            "3333",
            "4444",
            "5555",
            "6666",
            "7777",
            "8888",
            "9999",
            "1234",
            "4321",
            "1212",
            "1122",
            "123456",
            "password",
            "12345678",
            "qwerty",
            "abc123",
        }
    )

    @staticmethod
    def validate(pin: str) -> tuple[bool, str]:
        """Return (is_valid, error_message_i18n_key).

        Returns (True, "") if the PIN passes all checks.
        Returns (False, i18n_key) with a descriptive error key otherwise.
        """
        if not pin:
            return False, "pin_error_empty"
        if len(pin) < PinValidator.MIN_LENGTH:
            return False, "pin_error_too_short"
        if len(pin) > PinValidator.MAX_LENGTH:
            return False, "pin_error_too_long"
        if pin.lower() in PinValidator._WEAK_PINS:
            return False, "pin_error_weak"
        if len(set(pin)) == 1:
            return False, "pin_error_repeated"
        return True, ""


class PinRateLimiter:
    """Rate limiter for failed PIN unlock attempts.

    Tracks failed attempts globally (across dialog instances) and applies
    exponential backoff cooldowns. After MAX_ATTEMPTS the app requires a restart.
    """

    _failures: int = 0
    _first_failure_time: float = 0.0
    _lockout: bool = False

    MAX_ATTEMPTS = 7

    @staticmethod
    def _cooldown_seconds(attempts: int) -> int:
        """Return cooldown in seconds for a given number of failed attempts."""
        if attempts < 3:
            return 0
        if attempts == 3:
            return 5
        if attempts == 4:
            return 15
        if attempts == 5:
            return 30
        return 60

    @staticmethod
    def record_failure() -> None:
        """Record a failed PIN attempt."""
        import time

        if PinRateLimiter._failures == 0:
            PinRateLimiter._first_failure_time = time.monotonic()
        PinRateLimiter._failures += 1
        if PinRateLimiter._failures >= PinRateLimiter.MAX_ATTEMPTS:
            PinRateLimiter._lockout = True

    @staticmethod
    def remaining_cooldown() -> int:
        """Return remaining cooldown seconds (0 if no cooldown)."""
        if PinRateLimiter._failures == 0:
            return 0
        import time

        elapsed = time.monotonic() - PinRateLimiter._first_failure_time
        cooldown = PinRateLimiter._cooldown_seconds(PinRateLimiter._failures)
        remaining = max(0, int(cooldown - elapsed))
        return remaining

    @staticmethod
    def is_locked_out() -> bool:
        """Return True if the app is permanently locked (requires restart)."""
        return PinRateLimiter._lockout

    @staticmethod
    def reset() -> None:
        """Reset the failure counter after a successful unlock or PIN set."""
        PinRateLimiter._failures = 0
        PinRateLimiter._first_failure_time = 0.0
        PinRateLimiter._lockout = False


class LockManager:
    """PIN-based application lock management."""

    @staticmethod
    def is_lock_set() -> bool:
        """Return True if a lock file exists."""
        return LOCK_FILE.exists()

    @staticmethod
    def set_lock(password: str) -> None:
        """Create a lock file with the hashed password."""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        hash_value = KeyDerivation.hash_password(password)
        LOCK_FILE.write_text(hash_value, encoding="utf-8")
        apply_private_permissions(LOCK_FILE)

    @staticmethod
    def verify(password: str) -> bool:
        """Verify a password against the stored lock hash."""
        if not LOCK_FILE.exists():
            return False
        stored_hash = LOCK_FILE.read_text(encoding="utf-8").strip()
        return verify_password(password, stored_hash)

    @staticmethod
    def remove_lock() -> None:
        """Remove the lock file if it exists."""
        with contextlib.suppress(OSError):
            LOCK_FILE.unlink()

    @staticmethod
    def set_lock_from_hash(hash_value: str) -> None:
        """Create a lock file from a pre-computed hash."""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        LOCK_FILE.write_text(hash_value, encoding="utf-8")
        apply_private_permissions(LOCK_FILE)

    @staticmethod
    def change_password(current_password: str, new_password: str) -> bool:
        """Change the lock password if the current one is valid."""
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
        with contextlib.suppress(OSError):
            LOCK_ACTIVE_FILE.unlink()


class DatabaseEncryption:
    """Fernet-based file encryption for database files."""

    @staticmethod
    def encrypt_file(source_path: Path, key: bytes) -> Path:
        """Encrypt a file and write the .enc version alongside it."""
        fernet = Fernet(key)
        data = source_path.read_bytes()
        encrypted = fernet.encrypt(data)
        enc_path = Path(str(source_path) + ".enc")
        enc_path.write_bytes(encrypted)
        apply_private_permissions(enc_path)
        return enc_path

    @staticmethod
    def decrypt_file(enc_path: Path, key: bytes, output_path: Path | None = None) -> Path:
        """Decrypt an encrypted file and write the plaintext version."""
        fernet = Fernet(key)
        encrypted = enc_path.read_bytes()
        decrypted = fernet.decrypt(encrypted)
        if output_path is None:
            output_path = Path(str(enc_path).removesuffix(".enc"))
        output_path.write_bytes(decrypted)
        apply_private_permissions(output_path)
        return output_path

    @staticmethod
    def is_encrypted(db_path: Path) -> bool:
        """Return True if an encrypted version exists and plaintext does not."""
        return Path(str(db_path) + ".enc").exists() and not db_path.exists()


class BackupManager:
    """Database backup creation, rotation and restoration."""

    @staticmethod
    def ensure_backup_dir() -> Path:
        """Create the backups directory if it does not exist."""
        BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
        apply_private_permissions(BACKUPS_DIR, directory=True)
        return BACKUPS_DIR

    @staticmethod
    def create_backup(db_path: str | Path = "data/expenses.db") -> Path:
        """Create a timestamped backup and rotate old ones."""
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
        """Remove oldest backups exceeding the maximum count."""
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
        """Return metadata for all available backups."""
        if not BACKUPS_DIR.exists():
            return []
        backups = []
        for path in sorted(BACKUPS_DIR.glob("expenses_*.db"), key=lambda p: p.name, reverse=True):
            stat = path.stat()
            backups.append(
                {
                    "path": str(path),
                    "name": path.name,
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                }
            )
        return backups

    @staticmethod
    def restore_backup(backup_name: str, db_path: str | Path = "data/expenses.db") -> Path:
        """Restore the database from a named backup file."""
        backup_file = BACKUPS_DIR / backup_name
        if not backup_file.exists():
            raise FileNotFoundError(f"Backup not found: {backup_file}")

        target = Path(db_path)
        shutil.copy2(backup_file, target)
        apply_private_permissions(target)
        return target


class AuditLog:
    """JSONL-based file audit logging."""

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
        """Append an audit entry to the JSONL log file."""
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
        apply_private_permissions(AuditLog.LOG_FILE)

    @staticmethod
    def get_entries(limit: int = 100) -> list[dict[str, Any]]:
        """Return the most recent audit log entries."""
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
        """Delete the audit log file."""
        with contextlib.suppress(OSError):
            AuditLog.LOG_FILE.unlink()


class SQLCipherManager:
    """SQLCipher database encryption management."""

    KEY_FILE = DATA_DIR / ".dbkey"
    KEY_LENGTH_HEX = 64  # 32 bytes = 64 hex characters

    @staticmethod
    def validate_key(key: str) -> str:
        """Validate that a key is safe for use in a PRAGMA statement.

        Returns the key if valid. Raises ValueError on suspicious input.
        SQLCipher keys are hex strings from secrets.token_hex(32).
        """
        if not key or len(key) != SQLCipherManager.KEY_LENGTH_HEX:
            raise ValueError("Invalid SQLCipher key length")
        if not all(c in "0123456789abcdef" for c in key.lower()):
            raise ValueError("SQLCipher key must be a hex string")
        return key

    @staticmethod
    def is_encrypted_db(db_path: Path) -> bool:
        """Detect whether the database is already encrypted with SQLCipher."""
        if not db_path.exists():
            return False
        import sqlite3

        conn = sqlite3.connect(str(db_path))
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' LIMIT 1")
            cursor.fetchone()
            return False
        except Exception:
            return True
        finally:
            conn.close()

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
            raise ImportError(
                "pysqlcipher3 is required for database encryption. Install it with: pip install pysqlcipher3"
            ) from exc

        if not db_path.exists():
            raise FileNotFoundError(f"Database not found: {db_path}")

        # Create a backup before migration
        BackupManager.create_backup(db_path)

        temp_encrypted = db_path.with_suffix(".db.encrypted")

        safe_key = SQLCipherManager.validate_key(key)
        source_conn = sqlite.connect(str(db_path))
        source_conn.execute("ATTACH DATABASE ? AS encrypted KEY ?", (str(temp_encrypted), safe_key))
        source_conn.execute("SELECT sqlcipher_export('encrypted')")
        source_conn.execute("DETACH DATABASE encrypted")
        source_conn.close()

        # Replace original with encrypted version (atomic rename)
        backup_path = db_path.with_suffix(".db.bak")
        db_path.rename(backup_path)
        try:
            shutil.move(str(temp_encrypted), str(db_path))
            backup_path.unlink(missing_ok=True)
        except Exception:
            backup_path.rename(db_path)
            raise
        apply_private_permissions(db_path)

    @staticmethod
    def remove_key_file() -> None:
        """Remove the stored SQLCipher key file."""
        with contextlib.suppress(OSError):
            SQLCipherManager.KEY_FILE.unlink()
