from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from expenses_tracker.cloud_sync import (
    CloudProvider,
    CloudSyncConfigManager,
    CloudSyncManager,
    DropboxProvider,
    GoogleDriveProvider,
    WebDAVProvider,
)
from expenses_tracker.i18n import is_rtl, normalize_language, reshape_for_rtl, tr


class CloudSyncDialog(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Misc,
        language: str,
        db_path: str = "data/expenses.db",
        encryption_key: bytes | None = None,
    ) -> None:
        super().__init__(parent)
        self._language = normalize_language(language)
        self._rtl = is_rtl(self._language)
        self.title(self._rtl_text(tr(self._language, "cloud_sync_title")))
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.db_path = Path(db_path)
        self.encryption_key = encryption_key

        frame = ttk.Frame(self, padding=16)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text=self._rtl_text(tr(self._language, "cloud_sync_config"))).pack(
            anchor="w" if not self._rtl else "e", pady=(0, 8)
        )

        provider_frame = ttk.Frame(frame)
        provider_frame.pack(fill="x", pady=(0, 8))

        ttk.Label(provider_frame, text=self._rtl_text(tr(self._language, "label_type"))).pack(side="left", padx=(0, 6))
        self.provider_var = tk.StringVar(value="webdav")
        ttk.Radiobutton(
            provider_frame, text=tr(self._language, "cloud_sync_webdav"), variable=self.provider_var, value="webdav"
        ).pack(side="left", padx=(0, 6))
        ttk.Radiobutton(
            provider_frame, text=tr(self._language, "cloud_sync_dropbox"), variable=self.provider_var, value="dropbox"
        ).pack(side="left", padx=(0, 6))
        ttk.Radiobutton(
            provider_frame, text=tr(self._language, "cloud_sync_gdrive"), variable=self.provider_var, value="gdrive"
        ).pack(side="left", padx=(0, 6))

        self._fields_frame = ttk.Frame(frame)
        self._fields_frame.pack(fill="x", pady=(0, 8))

        self.url_var = tk.StringVar()
        self.username_var = tk.StringVar()
        self.password_var = tk.StringVar()
        self.token_var = tk.StringVar()
        self.credentials_path_var = tk.StringVar()

        self._build_fields()

        self.provider_var.trace_add("write", lambda *_: self._build_fields())

        self._auto_sync_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            frame,
            text=self._rtl_text(tr(self._language, "cloud_sync_auto")),
            variable=self._auto_sync_var,
        ).pack(anchor="w" if not self._rtl else "e", pady=(0, 8))

        status_frame = ttk.Frame(frame)
        status_frame.pack(fill="x", pady=(0, 8))
        ttk.Label(status_frame, text=self._rtl_text(tr(self._language, "cloud_sync_last")) + ":").pack(side="left")
        self.last_sync_var = tk.StringVar(value="-")
        ttk.Label(status_frame, textvariable=self.last_sync_var).pack(side="left", padx=(4, 0))

        buttons = ttk.Frame(frame)
        buttons.pack(fill="x")

        ttk.Button(
            buttons, text=self._rtl_text(tr(self._language, "cloud_sync_testing")), command=self._test_connection
        ).pack(side="left", padx=(0, 6))
        ttk.Button(buttons, text=self._rtl_text(tr(self._language, "cloud_sync_now")), command=self._sync_now).pack(
            side="left", padx=(0, 6)
        )
        ttk.Button(buttons, text=self._rtl_text(tr(self._language, "btn_save")), command=self._save_config).pack(
            side="left", padx=(0, 6)
        )
        ttk.Button(buttons, text=self._rtl_text(tr(self._language, "btn_close")), command=self.destroy).pack(
            side="right"
        )

        self._load_saved_config()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _rtl_text(self, text: str) -> str:
        if self._rtl:
            return reshape_for_rtl(text)
        return text

    def _build_fields(self) -> None:
        for widget in self._fields_frame.winfo_children():
            widget.destroy()

        kind = self.provider_var.get()
        if kind == "webdav":
            self._add_field(self._fields_frame, tr(self._language, "cloud_sync_url"), self.url_var)
            self._add_field(self._fields_frame, tr(self._language, "cloud_sync_username"), self.username_var)
            self._add_field(self._fields_frame, tr(self._language, "cloud_sync_password"), self.password_var, show="*")
        elif kind == "dropbox":
            self._add_field(self._fields_frame, tr(self._language, "cloud_sync_token"), self.token_var)
        elif kind == "gdrive":
            self._add_field(self._fields_frame, tr(self._language, "cloud_sync_token"), self.credentials_path_var)

    def _add_field(self, parent: ttk.Frame, label: str, var: tk.StringVar, show: str = "") -> None:
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=(2, 2))
        ttk.Label(row, text=self._rtl_text(label), width=18, anchor="e" if self._rtl else "w").pack(side="left")
        entry = ttk.Entry(row, textvariable=var, show=show)
        entry.pack(side="left", fill="x", expand=True, padx=(6, 0))
        if self._rtl:
            entry.configure(justify="right")

    def _get_provider(self) -> CloudProvider | None:
        kind = self.provider_var.get()
        try:
            if kind == "webdav":
                return WebDAVProvider(self.url_var.get(), self.username_var.get(), self.password_var.get())
            elif kind == "dropbox":
                return DropboxProvider(self.token_var.get())
            elif kind == "gdrive":
                return GoogleDriveProvider(self.credentials_path_var.get())
        except Exception as error:
            messagebox.showerror(
                tr(self._language, "error_generic"),
                f"{tr(self._language, 'cloud_sync_error', error=error)}",
                parent=self,
            )
        return None

    def _collect_config(self) -> dict:
        kind = self.provider_var.get()
        config: dict = {
            "provider": kind,
            "auto_sync": self._auto_sync_var.get(),
        }
        if kind == "webdav":
            config["url"] = self.url_var.get()
            config["username"] = self.username_var.get()
            config["password"] = self.password_var.get()
        elif kind == "dropbox":
            config["token"] = self.token_var.get()
        elif kind == "gdrive":
            config["credentials_path"] = self.credentials_path_var.get()
        return config

    def _load_saved_config(self) -> None:
        saved = CloudSyncConfigManager.load()
        if saved is None:
            return
        kind = saved.get("provider", "webdav")
        self.provider_var.set(kind)
        if kind == "webdav":
            self.url_var.set(saved.get("url", ""))
            self.username_var.set(saved.get("username", ""))
            self.password_var.set(saved.get("password", ""))
        elif kind == "dropbox":
            self.token_var.set(saved.get("token", ""))
        elif kind == "gdrive":
            self.credentials_path_var.set(saved.get("credentials_path", ""))
        self._auto_sync_var.set(bool(saved.get("auto_sync", False)))
        self._build_fields()

    def _save_config(self) -> None:
        config = self._collect_config()
        try:
            CloudSyncConfigManager.save(config)
            messagebox.showinfo(
                tr(self._language, "success"),
                tr(self._language, "cloud_sync_config_saved"),
                parent=self,
            )
        except Exception as error:
            messagebox.showerror(
                tr(self._language, "error_generic"),
                tr(self._language, "cloud_sync_error", error=error),
                parent=self,
            )

    def _test_connection(self) -> None:
        provider = self._get_provider()
        if provider is None:
            return
        try:
            files = provider.list_files("/")
            messagebox.showinfo(tr(self._language, "success"), f"Connection OK. {len(files)} files found.", parent=self)
            self._save_config()
        except Exception as error:
            messagebox.showerror(
                tr(self._language, "error_generic"), tr(self._language, "cloud_sync_error", error=error), parent=self
            )

    def _sync_now(self) -> None:
        if self.encryption_key is None:
            messagebox.showwarning(tr(self._language, "warning_no_data"), "No encryption key configured.", parent=self)
            return
        provider = self._get_provider()
        if provider is None:
            return
        manager = CloudSyncManager(provider, self.encryption_key)
        try:
            manager.sync_up(self.db_path)
            from datetime import datetime

            self.last_sync_var.set(datetime.now().strftime("%Y-%m-%d %H:%M"))
            messagebox.showinfo(tr(self._language, "success"), tr(self._language, "cloud_sync_success"), parent=self)
            self._save_config()
        except Exception as error:
            messagebox.showerror(
                tr(self._language, "error_generic"), tr(self._language, "cloud_sync_error", error=error), parent=self
            )

    def _on_close(self) -> None:
        self._save_config()
        self.destroy()
