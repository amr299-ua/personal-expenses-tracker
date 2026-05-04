from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

from expenses_tracker.automation import ReportScheduler
from expenses_tracker.db import ExpenseDatabase
from expenses_tracker.i18n import normalize_language, tr


class AutomationDialog(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Misc,
        database: ExpenseDatabase,
        scheduler: ReportScheduler,
        language: str,
    ) -> None:
        super().__init__(parent)
        self._language = normalize_language(language)
        self.title(tr(self._language, "automation_title"))
        self.geometry("520x580")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.database = database
        self.scheduler = scheduler

        self._build_ui()
        self._load_config()

        self.bind("<Escape>", lambda _event: self.destroy())

    def _build_ui(self) -> None:
        canvas = tk.Canvas(self, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        scroll_frame = ttk.Frame(canvas)

        scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw", width=500)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True, padx=8, pady=8)
        scrollbar.pack(side="right", fill="y")

        # --- Schedule section ---
        schedule_frame = ttk.LabelFrame(scroll_frame, text=tr(self._language, "automation_schedule"), padding=10)
        schedule_frame.pack(fill="x", pady=(0, 8))

        self.enabled_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            schedule_frame,
            text=tr(self._language, "automation_enabled"),
            variable=self.enabled_var,
        ).pack(anchor="w")

        self.backup_enabled_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            schedule_frame,
            text=tr(self._language, "automation_backup_enabled"),
            variable=self.backup_enabled_var,
        ).pack(anchor="w", pady=(6, 0))

        freq_row = ttk.Frame(schedule_frame)
        freq_row.pack(fill="x", pady=(6, 0))
        ttk.Label(freq_row, text=tr(self._language, "automation_frequency")).pack(side="left")
        self.freq_var = tk.StringVar(value="monthly")
        ttk.Combobox(
            freq_row,
            textvariable=self.freq_var,
            values=["daily", "weekly", "monthly"],
            state="readonly",
            width=12,
        ).pack(side="left", padx=(6, 0))

        day_row = ttk.Frame(schedule_frame)
        day_row.pack(fill="x", pady=(6, 0))
        ttk.Label(day_row, text=tr(self._language, "automation_day")).pack(side="left")
        self.day_var = tk.StringVar(value="1")
        ttk.Spinbox(day_row, from_=1, to=31, textvariable=self.day_var, width=6).pack(side="left", padx=(6, 0))

        time_row = ttk.Frame(schedule_frame)
        time_row.pack(fill="x", pady=(6, 0))
        ttk.Label(time_row, text=tr(self._language, "automation_time")).pack(side="left")
        self.time_var = tk.StringVar(value="08:00")
        ttk.Entry(time_row, textvariable=self.time_var, width=8).pack(side="left", padx=(6, 0))

        # --- Format section ---
        format_frame = ttk.LabelFrame(scroll_frame, text=tr(self._language, "automation_format"), padding=10)
        format_frame.pack(fill="x", pady=(0, 8))

        self.format_var = tk.StringVar(value="excel")
        ttk.Combobox(
            format_frame,
            textvariable=self.format_var,
            values=["excel", "csv", "pdf", "json", "yaml", "html", "all"],
            state="readonly",
            width=12,
        ).pack(anchor="w")

        # --- Email section ---
        email_frame = ttk.LabelFrame(scroll_frame, text=tr(self._language, "automation_email"), padding=10)
        email_frame.pack(fill="x", pady=(0, 8))

        self.email_enabled_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            email_frame,
            text=tr(self._language, "automation_enabled"),
            variable=self.email_enabled_var,
        ).pack(anchor="w")

        smtp_host_row = ttk.Frame(email_frame)
        smtp_host_row.pack(fill="x", pady=(6, 0))
        ttk.Label(smtp_host_row, text=tr(self._language, "automation_smtp_host"), width=16).pack(side="left")
        self.smtp_host_var = tk.StringVar()
        ttk.Entry(smtp_host_row, textvariable=self.smtp_host_var).pack(side="left", fill="x", expand=True)

        smtp_port_row = ttk.Frame(email_frame)
        smtp_port_row.pack(fill="x", pady=(6, 0))
        ttk.Label(smtp_port_row, text=tr(self._language, "automation_smtp_port"), width=16).pack(side="left")
        self.smtp_port_var = tk.StringVar()
        ttk.Entry(smtp_port_row, textvariable=self.smtp_port_var, width=8).pack(side="left")

        smtp_user_row = ttk.Frame(email_frame)
        smtp_user_row.pack(fill="x", pady=(6, 0))
        ttk.Label(smtp_user_row, text=tr(self._language, "automation_smtp_user"), width=16).pack(side="left")
        self.smtp_user_var = tk.StringVar()
        ttk.Entry(smtp_user_row, textvariable=self.smtp_user_var).pack(side="left", fill="x", expand=True)

        smtp_pass_row = ttk.Frame(email_frame)
        smtp_pass_row.pack(fill="x", pady=(6, 0))
        ttk.Label(smtp_pass_row, text=tr(self._language, "automation_smtp_password"), width=16).pack(side="left")
        self.smtp_password_var = tk.StringVar()
        ttk.Entry(smtp_pass_row, textvariable=self.smtp_password_var, show="*").pack(side="left", fill="x", expand=True)

        email_to_row = ttk.Frame(email_frame)
        email_to_row.pack(fill="x", pady=(6, 0))
        ttk.Label(email_to_row, text=tr(self._language, "automation_email_to"), width=16).pack(side="left")
        self.email_to_var = tk.StringVar()
        ttk.Entry(email_to_row, textvariable=self.email_to_var).pack(side="left", fill="x", expand=True)

        email_subj_row = ttk.Frame(email_frame)
        email_subj_row.pack(fill="x", pady=(6, 0))
        ttk.Label(email_subj_row, text=tr(self._language, "automation_email_subject"), width=16).pack(side="left")
        self.email_subject_var = tk.StringVar()
        ttk.Entry(email_subj_row, textvariable=self.email_subject_var).pack(side="left", fill="x", expand=True)

        # --- Buttons ---
        btn_row = ttk.Frame(scroll_frame)
        btn_row.pack(fill="x", pady=(8, 0))

        ttk.Button(
            btn_row,
            text=tr(self._language, "btn_cancel"),
            style="Ghost.TButton",
            command=self.destroy,
        ).pack(side="right", padx=(6, 0))
        ttk.Button(
            btn_row,
            text=tr(self._language, "btn_save"),
            style="Accent.TButton",
            command=self._save,
        ).pack(side="right")
        ttk.Button(
            btn_row,
            text=tr(self._language, "automation_test_email"),
            command=self._test_email,
        ).pack(side="left")
        ttk.Button(
            btn_row,
            text=tr(self._language, "automation_run_now"),
            command=self._run_now,
        ).pack(side="left", padx=(6, 0))

    def _load_config(self) -> None:
        config = self.database.get_automation_config()
        self.enabled_var.set(bool(config.get("enabled")))
        self.backup_enabled_var.set(bool(config.get("backup_enabled")))
        self.freq_var.set(config.get("schedule_type", "monthly"))
        day = config.get("schedule_day")
        self.day_var.set(str(day) if day is not None else "1")
        self.time_var.set(config.get("schedule_time", "08:00"))
        self.format_var.set(config.get("export_format", "excel"))
        self.email_enabled_var.set(bool(config.get("email_enabled")))
        self.smtp_host_var.set(config.get("smtp_host") or "")
        self.smtp_port_var.set(str(config.get("smtp_port") or ""))
        self.smtp_user_var.set(config.get("smtp_user") or "")
        self.smtp_password_var.set(config.get("smtp_password") or "")
        self.email_to_var.set(config.get("email_to") or "")
        self.email_subject_var.set(config.get("email_subject") or "")

    def _collect_config(self) -> dict[str, Any]:
        day_str = self.day_var.get().strip()
        try:
            day = int(day_str)
        except ValueError:
            day = 1
        port_str = self.smtp_port_var.get().strip()
        try:
            port = int(port_str) if port_str else None
        except ValueError:
            port = None
        return {
            "enabled": self.enabled_var.get(),
            "backup_enabled": self.backup_enabled_var.get(),
            "schedule_type": self.freq_var.get(),
            "schedule_day": day,
            "schedule_time": self.time_var.get().strip(),
            "export_format": self.format_var.get(),
            "email_enabled": self.email_enabled_var.get(),
            "smtp_host": self.smtp_host_var.get().strip() or None,
            "smtp_port": port,
            "smtp_user": self.smtp_user_var.get().strip() or None,
            "smtp_password": self.smtp_password_var.get().strip() or None,
            "email_to": self.email_to_var.get().strip() or None,
            "email_subject": self.email_subject_var.get().strip() or None,
        }

    def _save(self) -> None:
        config = self._collect_config()
        self.database.save_automation_config(config)
        self.scheduler.update_schedule(config)
        messagebox.showinfo(
            tr(self._language, "success"),
            tr(self._language, "automation_saved"),
            parent=self,
        )
        self.destroy()

    def _test_email(self) -> None:
        config = self._collect_config()
        if not config.get("email_enabled"):
            messagebox.showwarning(
                tr(self._language, "warning_no_data"),
                tr(self._language, "automation_email"),
                parent=self,
            )
            return
        success = self.scheduler.send_test_email(config)
        if success:
            messagebox.showinfo(
                tr(self._language, "success"),
                tr(self._language, "automation_test_sent"),
                parent=self,
            )
        else:
            messagebox.showerror(
                tr(self._language, "error_generic"),
                tr(self._language, "automation_test_failed"),
                parent=self,
            )

    def _run_now(self) -> None:
        try:
            self.scheduler._run_report()
            messagebox.showinfo(
                tr(self._language, "success"),
                tr(self._language, "automation_run_now"),
                parent=self,
            )
        except Exception as error:
            messagebox.showerror(
                tr(self._language, "error_generic"),
                tr(self._language, "error_email_send", error=error),
                parent=self,
            )
