from __future__ import annotations

import logging
import smtplib
import threading
import time
from datetime import date, datetime, timezone
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Callable

import schedule

from expenses_tracker.db import ExpenseDatabase
from expenses_tracker.exporters import export_reports
from expenses_tracker.i18n import tr

logger = logging.getLogger(__name__)


class ReportScheduler:
    def __init__(
        self,
        database: ExpenseDatabase,
        config_getter: Callable[[], dict[str, Any]],
        language: str = "en",
    ) -> None:
        self.database = database
        self.config_getter = config_getter
        self.language = language
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2)

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                with self._lock:
                    schedule.run_pending()
            except Exception:
                logger.exception("Scheduler run_pending error")
            self._stop_event.wait(timeout=60)

    def update_schedule(self, config: dict[str, Any] | None = None) -> None:
        if config is None:
            config = self.config_getter()
        with self._lock:
            schedule.clear()
            if not config.get("enabled"):
                return
            schedule_type = config.get("schedule_type", "monthly")
            schedule_time = config.get("schedule_time", "08:00")
            schedule_day = config.get("schedule_day")

            if schedule_type == "daily":
                schedule.every().day.at(schedule_time).do(self._run_report)
                if config.get("backup_enabled"):
                    schedule.every().day.at(schedule_time).do(self._run_backup)
            elif schedule_type == "weekly" and schedule_day is not None:
                days = [
                    schedule.every().sunday,
                    schedule.every().monday,
                    schedule.every().tuesday,
                    schedule.every().wednesday,
                    schedule.every().thursday,
                    schedule.every().friday,
                    schedule.every().saturday,
                ]
                if 0 <= schedule_day < len(days):
                    days[schedule_day].at(schedule_time).do(self._run_report)
                    if config.get("backup_enabled"):
                        days[schedule_day].at(schedule_time).do(self._run_backup)
            elif schedule_type == "monthly" and schedule_day is not None:
                # schedule library does not have monthly; use a daily check
                schedule.every().day.at(schedule_time).do(
                    self._run_monthly_report, day=schedule_day
                )
                if config.get("backup_enabled"):
                    schedule.every().day.at(schedule_time).do(
                        self._run_monthly_backup, day=schedule_day
                    )

    def _run_monthly_report(self, day: int) -> None:
        today = date.today()
        if today.day == day:
            self._run_report()

    def _run_backup(self) -> None:
        try:
            self.database.create_backup()
            logger.info("Automatic backup created")
        except Exception:
            logger.exception("Automatic backup failed")

    def _run_monthly_backup(self, day: int) -> None:
        if date.today().day == day:
            self._run_backup()

    def _run_report(self) -> None:
        config = self.config_getter()
        if not config.get("enabled"):
            return
        try:
            transactions = self.database.fetch_transactions(limit=None)
            if not transactions:
                return
            from expenses_tracker.exporters import (
                _compute_category_rows_from_transactions,
                _compute_month_rows_from_transactions,
            )
            category_rows = _compute_category_rows_from_transactions(transactions)
            month_rows = _compute_month_rows_from_transactions(transactions)
            fmt = config.get("export_format", "excel")
            generated = export_reports(
                transactions=transactions,
                category_rows=category_rows,
                month_rows=month_rows,
                output_dir="reports",
                fmt=fmt,
                language=self.language,
            )
            self._update_last_run()
            if config.get("email_enabled") and generated:
                for filepath in generated:
                    self._send_email(filepath, config)
        except Exception:
            logger.exception("Report generation failed")

    def _update_last_run(self) -> None:
        try:
            with self.database.Session() as session:
                from expenses_tracker.models import AutomationConfig
                row = session.query(AutomationConfig).first()
                if row is not None:
                    row.last_run = datetime.now(timezone.utc)
                    session.commit()
        except Exception:
            logger.exception("Failed to update last_run")

    def _send_email(self, filepath: Path, config: dict[str, Any]) -> None:
        host = config.get("smtp_host")
        port = config.get("smtp_port")
        user = config.get("smtp_user")
        password = config.get("smtp_password")
        to_addr = config.get("email_to")
        subject = config.get("email_subject") or tr(self.language, "app_title")

        if not all([host, port, user, password, to_addr]):
            return

        msg = MIMEMultipart()
        msg["Subject"] = subject
        msg["From"] = user
        msg["To"] = to_addr
        body = MIMEText(tr(self.language, "report_generated", path=filepath.name))
        msg.attach(body)

        with filepath.open("rb") as f:
            attachment = MIMEApplication(f.read(), Name=filepath.name)
        attachment["Content-Disposition"] = f'attachment; filename="{filepath.name}"'
        msg.attach(attachment)

        with smtplib.SMTP(host, int(port)) as server:
            server.starttls()
            server.login(user, password)
            server.send_message(msg)

    def send_test_email(self, config: dict[str, Any]) -> bool:
        try:
            host = config.get("smtp_host")
            port = config.get("smtp_port")
            user = config.get("smtp_user")
            password = config.get("smtp_password")
            to_addr = config.get("email_to")
            subject = (config.get("email_subject") or tr(self.language, "app_title")) + " [TEST]"

            if not all([host, port, user, password, to_addr]):
                return False

            msg = MIMEMultipart()
            msg["Subject"] = subject
            msg["From"] = user
            msg["To"] = to_addr
            body = MIMEText("This is a test email from Personal Expenses Tracker.")
            msg.attach(body)

            with smtplib.SMTP(host, int(port)) as server:
                server.starttls()
                server.login(user, password)
                server.send_message(msg)
            return True
        except Exception:
            logger.exception("Test email failed")
            return False
