from __future__ import annotations

import logging
import smtplib
import threading
from datetime import date, datetime, timezone
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import TYPE_CHECKING, Any, cast

import schedule
from sqlalchemy import select

from expenses_tracker.exporters import export_reports
from expenses_tracker.i18n import tr

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from expenses_tracker.db import ExpenseDatabase

logger = logging.getLogger(__name__)


class ReportScheduler:
    """Background scheduler for automated report generation and email."""

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
        self._scheduler = schedule.Scheduler()

    def start(self) -> None:
        """Start the background scheduler thread."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the background scheduler thread."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2)

    def _run_loop(self) -> None:
        """Main scheduler loop running in a background thread."""
        while not self._stop_event.is_set():
            try:
                self._scheduler.run_pending()
            except Exception:
                logger.exception("Scheduler run_pending error")
            self._stop_event.wait(timeout=60)

    def update_schedule(self, config: dict[str, Any] | None = None) -> None:
        """Reconfigure the schedule based on current settings."""
        if config is None:
            config = self.config_getter()
        with self._lock:
            self._scheduler.clear()
            # Always check for recurring transactions daily
            self._scheduler.every().day.at("00:01").do(self._run_recurring)
            if not config.get("enabled"):
                return
            schedule_type = config.get("schedule_type", "monthly")
            schedule_time = config.get("schedule_time", "08:00")
            schedule_day = config.get("schedule_day")

            if schedule_type == "daily":
                self._scheduler.every().day.at(schedule_time).do(self._run_report)
                if config.get("backup_enabled"):
                    self._scheduler.every().day.at(schedule_time).do(self._run_backup)
            elif schedule_type == "weekly" and schedule_day is not None:
                days = [
                    self._scheduler.every().sunday,
                    self._scheduler.every().monday,
                    self._scheduler.every().tuesday,
                    self._scheduler.every().wednesday,
                    self._scheduler.every().thursday,
                    self._scheduler.every().friday,
                    self._scheduler.every().saturday,
                ]
                if 0 <= schedule_day < len(days):
                    days[schedule_day].at(schedule_time).do(self._run_report)
                    if config.get("backup_enabled"):
                        days[schedule_day].at(schedule_time).do(self._run_backup)
            elif schedule_type == "monthly" and schedule_day is not None:
                # schedule library does not have monthly; use a daily check
                self._scheduler.every().day.at(schedule_time).do(self._run_monthly_report, day=schedule_day)
                if config.get("backup_enabled"):
                    self._scheduler.every().day.at(schedule_time).do(self._run_monthly_backup, day=schedule_day)

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

    def _run_recurring(self) -> None:
        """Process recurring transactions due today."""
        try:
            created = self.database.process_recurring_transactions()
            if created > 0:
                logger.info("Created %d recurring transactions", created)
        except Exception:
            logger.exception("Recurring transaction processing failed")

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
                    try:
                        self._send_email(filepath, config)
                    except Exception:
                        logger.exception("Failed to send email for %s", filepath)
        except Exception:
            logger.exception("Report generation failed")

    def _update_last_run(self) -> None:
        try:
            with self.database.Session() as session:
                from expenses_tracker.models import AutomationConfig

                row = session.execute(select(AutomationConfig)).scalar_one_or_none()
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

        host_str = cast("str", host)
        port_int = int(cast("str", port))
        user_str = cast("str", user)
        password_str = cast("str", password)
        to_addr_str = cast("str", to_addr)

        msg = MIMEMultipart()
        msg["Subject"] = subject
        msg["From"] = user_str
        msg["To"] = to_addr_str
        body = MIMEText(tr(self.language, "report_generated", path=filepath.name))
        msg.attach(body)

        with filepath.open("rb") as f:
            attachment = MIMEApplication(f.read(), Name=filepath.name)
        attachment["Content-Disposition"] = f'attachment; filename="{filepath.name}"'
        msg.attach(attachment)

        if port_int == 465:
            with smtplib.SMTP_SSL(host_str, port_int) as server:
                server.login(user_str, password_str)
                server.send_message(msg)
        else:
            with smtplib.SMTP(host_str, port_int) as server:
                server.starttls()
                server.login(user_str, password_str)
                server.send_message(msg)

    def send_test_email(self, config: dict[str, Any]) -> bool:
        """Send a test email using the provided SMTP configuration."""
        try:
            host = config.get("smtp_host")
            port = config.get("smtp_port")
            user = config.get("smtp_user")
            password = config.get("smtp_password")
            to_addr = config.get("email_to")
            subject = (config.get("email_subject") or tr(self.language, "app_title")) + " [TEST]"

            if not all([host, port, user, password, to_addr]):
                return False

            host_str = cast("str", host)
            port_int = int(cast("str", port))
            user_str = cast("str", user)
            password_str = cast("str", password)
            to_addr_str = cast("str", to_addr)

            msg = MIMEMultipart()
            msg["Subject"] = subject
            msg["From"] = user_str
            msg["To"] = to_addr_str
            body = MIMEText("This is a test email from Personal Expenses Tracker.")
            msg.attach(body)

            if port_int == 465:
                with smtplib.SMTP_SSL(host_str, port_int) as server:
                    server.login(user_str, password_str)
                    server.send_message(msg)
            else:
                with smtplib.SMTP(host_str, port_int) as server:
                    server.starttls()
                    server.login(user_str, password_str)
                    server.send_message(msg)
            return True
        except Exception:
            logger.exception("Test email failed")
            return False
