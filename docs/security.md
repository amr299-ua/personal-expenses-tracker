# Security

Personal Expenses Tracker implements multiple layers of security to protect
your financial data.

## Database Encryption (SQLCipher)

The SQLite database can be encrypted at rest using **SQLCipher AES-256**.

### Enabling encryption

1. Go to **Tools > Encrypt Database**
2. Set your PIN first (if not already set)
3. The database will be migrated from plaintext to encrypted format
4. A backup is automatically created before migration

The encryption key is derived from your PIN using PBKDF2-HMAC-SHA256
with 600,000 iterations.

### Key validation

SQLCipher PRAGMA keys are validated as hex-only (64 characters) before use,
eliminating SQL injection vectors.

## PIN Lock

Protects the application at startup with a configurable PIN.

### Features

- **PBKDF2-HMAC-SHA256**: 600,000 iterations for key derivation
- **Weak PIN rejection**: Rejects common patterns (`0000`, `1234`, `password`, etc.)
- **Rate limiting**: Exponential backoff on failed attempts:
  - Attempt 3 → 5-second delay
  - Attempt 4 → 15-second delay
  - Attempt 5 → 30-second delay
  - Attempt 6 → 60-second delay
  - Attempt 7+ → Permanent lockout

### Managing the PIN

- **Set PIN**: Tools > Set PIN Lock (first time)
- **Change PIN**: Tools > Set PIN Lock (when already set)
- **Remove PIN**: Tools > Set PIN Lock > Leave empty

## File Encryption (Fernet)

Sensitive files and data are encrypted using **Fernet** (AES-128-CBC + HMAC):

- **Backups**: All database backups are encrypted
- **Cloud sync**: Database is encrypted before upload to any provider
- **SMTP password**: Stored encrypted at rest with `ENC:` prefix marker
- **Cloud credentials**: Encrypted and persisted across sessions

The Fernet key is stored in `data/.appkey` with restricted permissions (600).

## Key Derivation

- **Database encryption key**: Derived from PIN via PBKDF2-HMAC-SHA256
- **Cloud sync salt**: Random per-app salt stored in `data/.cloud_salt`
  (never hardcoded)
- **Fernet key**: Automatically generated on first use, stored in `data/.appkey`

## Audit Logging

All sensitive operations are logged to two locations:

1. **File**: `data/audit_log.jsonl` — JSON Lines format
2. **Database**: `audit_log` table — queryable via SQL

Tracked actions:
- `CREATE`, `UPDATE`, `DELETE` — Transaction changes
- `LOGIN` — PIN unlock events
- `BACKUP`, `RESTORE` — Backup operations
- `LOCK_SET`, `LOCK_CHANGE` — PIN management

## File Permissions (Unix)

Sensitive files are created with restricted permissions:
- Regular files: `600` (owner read/write only)
- Directories: `700` (owner access only)

Affected files:
- `data/.appkey` — Fernet encryption key
- `data/.cloud_salt` — Cloud sync key derivation salt
- `data/.lock` — PIN lock state
- `data/.key` — Database encryption key
