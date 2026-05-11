from __future__ import annotations

import json
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

from expenses_tracker.security import AppCrypto, DatabaseEncryption


class CloudProvider(ABC):
    """Abstract interface for cloud providers."""

    @abstractmethod
    def upload(self, local_path: Path, remote_path: str) -> None:
        """Upload a local file to the cloud."""

    @abstractmethod
    def download(self, remote_path: str, local_path: Path) -> None:
        """Download a file from the cloud to a local path."""

    @abstractmethod
    def list_files(self, remote_dir: str) -> list[dict[str, Any]]:
        """List files in a remote directory."""

    @abstractmethod
    def delete(self, remote_path: str) -> None:
        """Delete a remote file."""


class WebDAVProvider(CloudProvider):
    """WebDAV sync using webdavclient3."""

    def __init__(self, url: str, username: str, password: str) -> None:
        from webdav3.client import Client

        self.client = Client(
            {
                "webdav_hostname": url,
                "webdav_login": username,
                "webdav_password": password,
            }
        )

    def upload(self, local_path: Path, remote_path: str) -> None:
        """Upload a local file to WebDAV."""
        self.client.upload_sync(remote_path=remote_path, local_path=str(local_path))

    def download(self, remote_path: str, local_path: Path) -> None:
        """Download a file from WebDAV to a local path."""
        self.client.download_sync(remote_path=remote_path, local_path=str(local_path))

    def list_files(self, remote_dir: str) -> list[dict[str, Any]]:
        """List files in a remote WebDAV directory with metadata."""
        try:
            items = self.client.list(remote_dir, get_info=True)
        except TypeError:
            items = self.client.list(remote_dir)
        result: list[dict[str, Any]] = []
        for item in items:
            if isinstance(item, dict):
                result.append(
                    {
                        "name": item.get("name", str(item)),
                        "size": item.get("size", 0),
                        "modified": item.get("modified", ""),
                    }
                )
            else:
                result.append({"name": str(item), "size": 0, "modified": ""})
        return result

    def delete(self, remote_path: str) -> None:
        """Delete a file from WebDAV."""
        self.client.clean(remote_path)


class DropboxProvider(CloudProvider):
    """Dropbox sync using API v2."""

    def __init__(self, access_token: str) -> None:
        import dropbox as _dropbox

        self._dropbox = _dropbox
        self.dbx = _dropbox.Dropbox(access_token)

    def upload(self, local_path: Path, remote_path: str) -> None:
        """Upload a local file to Dropbox."""
        with open(local_path, "rb") as f:
            self.dbx.files_upload(f.read(), remote_path, mode=self._dropbox.files.WriteMode.overwrite)

    def download(self, remote_path: str, local_path: Path) -> None:
        """Download a file from Dropbox to a local path."""
        metadata, result = self.dbx.files_download(remote_path)
        local_path.write_bytes(result.content)

    def list_files(self, remote_dir: str) -> list[dict[str, Any]]:
        """List files in a remote Dropbox directory."""
        result = self.dbx.files_list_folder(remote_dir)
        return [{"name": entry.name, "path": entry.path_lower} for entry in result.entries]

    def delete(self, remote_path: str) -> None:
        """Delete a file from Dropbox."""
        self.dbx.files_delete_v2(remote_path)


class GoogleDriveProvider(CloudProvider):
    """Google Drive sync using Google API."""

    def __init__(self, credentials_path: str) -> None:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        creds = Credentials.from_authorized_user_file(  # type: ignore[no-untyped-call]
            credentials_path, ["https://www.googleapis.com/auth/drive"]
        )
        self.service = build("drive", "v3", credentials=creds)

    def upload(self, local_path: Path, remote_path: str) -> None:
        """Upload a local file to Google Drive."""
        file_metadata = {"name": remote_path}
        self.service.files().create(body=file_metadata, media_body=str(local_path), fields="id").execute()

    def download(self, remote_path: str, local_path: Path) -> None:
        """Download a file from Google Drive to a local path."""
        file_id = self._get_file_id(remote_path)
        request = self.service.files().get_media(fileId=file_id)
        local_path.write_bytes(request.execute())

    def list_files(self, remote_dir: str) -> list[dict[str, Any]]:
        """List files in a remote Google Drive directory."""
        results = self.service.files().list(q=f"name contains '{remote_dir}'", fields="files(id, name)").execute()
        return [{"name": f["name"], "id": f["id"]} for f in results.get("files", [])]

    def delete(self, remote_path: str) -> None:
        """Delete a file from Google Drive."""
        file_id = self._get_file_id(remote_path)
        self.service.files().delete(fileId=file_id).execute()

    def _get_file_id(self, name: str) -> str:
        results = self.service.files().list(q=f"name = '{name}'", fields="files(id, name)").execute()
        files = results.get("files", [])
        if not files:
            raise FileNotFoundError(f"Google Drive file not found: {name}")
        return cast("str", files[0]["id"])


class CloudSyncConfigManager:
    """Persists cloud sync provider configuration encrypted on disk."""

    @staticmethod
    def _config_path() -> Path:
        from expenses_tracker.utils import resolve_app_data_dir

        return resolve_app_data_dir() / "cloud_config.json"

    @staticmethod
    def save(config: dict[str, Any]) -> None:
        """Encrypt and persist the cloud sync configuration."""
        config_path = CloudSyncConfigManager._config_path()
        config_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(config, ensure_ascii=False)
        encrypted = AppCrypto.encrypt(payload)
        config_path.write_text(encrypted, encoding="utf-8")

    @staticmethod
    def load() -> dict[str, Any] | None:
        """Load and decrypt the cloud sync configuration, or None if not found."""
        config_path = CloudSyncConfigManager._config_path()
        if not config_path.exists():
            return None
        try:
            encrypted = config_path.read_text(encoding="utf-8").strip()
            raw = AppCrypto.decrypt(encrypted)
            if raw is None:
                return None
            return cast("dict[str, Any]", json.loads(raw))
        except (json.JSONDecodeError, OSError):
            return None

    @staticmethod
    def delete() -> None:
        """Remove the cloud sync configuration file."""
        import contextlib

        with contextlib.suppress(OSError):
            CloudSyncConfigManager._config_path().unlink()


class CloudSyncManager:
    """Manages encrypted synchronization with cloud providers."""

    REMOTE_DB_NAME = "expenses.db.enc"
    REMOTE_META_NAME = "sync_meta.json"

    def __init__(self, provider: CloudProvider, encryption_key: bytes, remote_dir: str = "/") -> None:
        self.provider = provider
        self.encryption_key = encryption_key
        self.remote_dir = remote_dir.rstrip("/")

    def _remote_path(self, name: str) -> str:
        return f"{self.remote_dir}/{name}"

    def sync_up(self, db_path: Path, *, force: bool = False) -> bool:
        """Upload encrypted database + metadata to cloud.

        If force is False, checks remote metadata timestamp first and
        returns False without uploading if the remote is newer.
        """
        if not force:
            remote_meta = self._get_remote_metadata()
            if remote_meta:
                local_mtime = db_path.stat().st_mtime
                remote_ts = remote_meta.get("timestamp", "")
                try:
                    remote_dt = datetime.fromisoformat(remote_ts)
                    if remote_dt.timestamp() > local_mtime:
                        return False
                except (ValueError, TypeError):
                    pass

        enc_path = DatabaseEncryption.encrypt_file(db_path, self.encryption_key)
        try:
            self.provider.upload(enc_path, self._remote_path(self.REMOTE_DB_NAME))
            meta = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "hash": self._file_hash(enc_path),
            }
            meta_path = db_path.with_suffix(".sync_meta.json")
            meta_path.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
            self.provider.upload(meta_path, self._remote_path(self.REMOTE_META_NAME))
            return True
        finally:
            enc_path.unlink(missing_ok=True)

    def _get_remote_metadata(self) -> dict[str, Any] | None:
        """Download and return remote sync metadata, or None if not found."""
        meta_path = Path("data/temp_remote_meta.json")
        try:
            self.provider.download(self._remote_path(self.REMOTE_META_NAME), meta_path)
            data = json.loads(meta_path.read_text(encoding="utf-8"))
            return cast("dict[str, Any]", data)
        except Exception:
            return None
        finally:
            meta_path.unlink(missing_ok=True)

    def sync_down(self, db_path: Path) -> None:
        """Download and decrypt database from cloud."""
        enc_path = db_path.with_suffix(".db.enc.download")
        try:
            self.provider.download(self._remote_path(self.REMOTE_DB_NAME), enc_path)
            DatabaseEncryption.decrypt_file(enc_path, self.encryption_key, output_path=db_path)
        finally:
            enc_path.unlink(missing_ok=True)

    def auto_sync(self, db_path: Path) -> None:
        """Auto-sync if there are pending changes (simplified: always sync up)."""
        self.sync_up(db_path)

    @staticmethod
    def _file_hash(path: Path) -> str:
        import hashlib

        return hashlib.sha256(path.read_bytes()).hexdigest()
