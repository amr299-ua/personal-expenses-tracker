"""Extended cloud_sync tests with mocked providers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from expenses_tracker.cloud_sync import (
    CloudSyncManager,
    DropboxProvider,
    GoogleDriveProvider,
    WebDAVProvider,
)


def _skip_if_missing(module: str):
    try:
        __import__(module)
    except ImportError:
        pytest.skip(f"{module} not installed")


class TestWebDAVProvider:
    def test_init(self):
        _skip_if_missing("webdav3")
        with patch("webdav3.client.Client") as mock_client:
            WebDAVProvider("http://example.com", "user", "pass")
            mock_client.assert_called_once_with({
                "webdav_hostname": "http://example.com",
                "webdav_login": "user",
                "webdav_password": "pass",
            })

    def test_upload(self):
        _skip_if_missing("webdav3")
        with patch("webdav3.client.Client"):
            provider = WebDAVProvider("http://example.com", "user", "pass")
            path = MagicMock()
            provider.upload(path, "/remote")
            provider.client.upload_sync.assert_called_once_with(remote_path="/remote", local_path=str(path))


class TestDropboxProvider:
    def test_init(self):
        _skip_if_missing("dropbox")
        with patch("dropbox.Dropbox") as mock_dbx:
            DropboxProvider("token")
            mock_dbx.assert_called_once_with("token")

    def test_upload(self):
        _skip_if_missing("dropbox")
        with patch("dropbox.Dropbox"):
            provider = DropboxProvider("token")
            path = MagicMock()
            provider.upload(path, "/remote")
            provider.dbx.files_upload.assert_called_once()


class TestGoogleDriveProvider:
    def test_init(self):
        _skip_if_missing("google.oauth2.credentials")
        with (
            patch("google.oauth2.credentials.Credentials.from_authorized_user_file") as mock_creds,
            patch("googleapiclient.discovery.build") as mock_build,
        ):
            GoogleDriveProvider("/path/to/creds.json")
            mock_creds.assert_called_once()
            mock_build.assert_called_once_with("drive", "v3", credentials=mock_creds.return_value)

    def test_delete(self):
        _skip_if_missing("google.oauth2.credentials")

        mock_files_instance = MagicMock()
        mock_list_instance = MagicMock()
        mock_list_instance.execute.return_value = {"files": [{"id": "123", "name": "x"}]}
        mock_files_instance.list.return_value = mock_list_instance
        mock_delete_instance = MagicMock()
        mock_files_instance.delete.return_value = mock_delete_instance

        def mock_files():
            return mock_files_instance

        with (
            patch("google.oauth2.credentials.Credentials.from_authorized_user_file"),
            patch("googleapiclient.discovery.build", return_value=MagicMock(files=mock_files)),
        ):
            provider = GoogleDriveProvider("/path/to/creds.json")
            provider.delete("x")
            mock_delete_instance.execute.assert_called_once()


class TestCloudSyncManagerExtended:
    def test_sync_up_with_real_encryption(self, tmp_path):
        from cryptography.fernet import Fernet
        key = Fernet.generate_key()
        fake = MagicMock()
        manager = CloudSyncManager(fake, key)
        db_path = tmp_path / "expenses.db"
        db_path.write_bytes(b"data")
        manager.sync_up(db_path)
        assert fake.upload.call_count == 2

    def test_sync_down_with_real_encryption(self, tmp_path):
        from cryptography.fernet import Fernet
        key = Fernet.generate_key()
        fake = MagicMock()
        manager = CloudSyncManager(fake, key)
        db_path = tmp_path / "expenses.db"
        db_path.write_bytes(b"original")

        # intercept the encrypted file before sync_up deletes it
        captured_enc: bytes | None = None
        original_upload = fake.upload

        def capture_upload(local_path, remote_path):
            if local_path.suffix == ".enc":
                nonlocal captured_enc
                captured_enc = local_path.read_bytes()
            original_upload(local_path, remote_path)

        fake.upload = capture_upload
        manager.sync_up(db_path)
        assert captured_enc is not None

        enc_download = db_path.with_suffix(".db.enc.download")
        enc_download.write_bytes(captured_enc)

        db_path.write_bytes(b"modified")
        manager.sync_down(db_path)
        assert db_path.read_bytes() == b"original"

    def test_file_hash(self, tmp_path):
        path = tmp_path / "file.txt"
        path.write_bytes(b"hello")
        h = CloudSyncManager._file_hash(path)
        assert isinstance(h, str)
        assert len(h) == 64
