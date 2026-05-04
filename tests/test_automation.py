"""Tests for automation scheduler and email functionality."""

from __future__ import annotations

from datetime import date
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from expenses_tracker.automation import ReportScheduler
from expenses_tracker.db import ExpenseDatabase, TransactionInput


@pytest.fixture
def scheduler(db: ExpenseDatabase):
    def config_getter():
        return db.get_automation_config()
    return ReportScheduler(database=db, config_getter=config_getter, language="en")


class TestAutomationConfigCRUD:
    def test_get_default_config(self, db: ExpenseDatabase):
        config = db.get_automation_config()
        assert config["enabled"] is False
        assert config["schedule_type"] == "monthly"
        assert config["schedule_day"] == 1
        assert config["schedule_time"] == "08:00"
        assert config["export_format"] == "excel"
        assert config["backup_enabled"] is False

    def test_save_and_retrieve_config(self, db: ExpenseDatabase):
        db.save_automation_config(
            {
                "enabled": True,
                "schedule_type": "weekly",
                "schedule_day": 3,
                "schedule_time": "09:30",
                "export_format": "pdf",
                "email_enabled": True,
                "smtp_host": "smtp.example.com",
                "smtp_port": 587,
                "smtp_user": "user@example.com",
                "smtp_password": "secret",
                "email_to": "to@example.com",
                "email_subject": "Report",
            }
        )
        config = db.get_automation_config()
        assert config["enabled"] is True
        assert config["schedule_type"] == "weekly"
        assert config["schedule_day"] == 3
        assert config["export_format"] == "pdf"
        assert config["smtp_host"] == "smtp.example.com"
        assert config["smtp_port"] == 587


class TestReportSchedulerLifecycle:
    def test_start_and_stop(self, scheduler: ReportScheduler):
        scheduler.start()
        assert scheduler._thread is not None
        scheduler.stop()
        assert not scheduler._thread.is_alive()

    def test_update_schedule_clears_previous_jobs(self, scheduler: ReportScheduler):
        with patch("expenses_tracker.automation.schedule") as mock_schedule:
            scheduler.update_schedule(
                {
                    "enabled": True,
                    "schedule_type": "daily",
                    "schedule_time": "08:00",
                }
            )
            mock_schedule.clear.assert_called_once()

    def test_update_schedule_disabled_does_not_add_jobs(self, scheduler: ReportScheduler):
        with patch("expenses_tracker.automation.schedule") as mock_schedule:
            scheduler.update_schedule({"enabled": False})
            mock_schedule.clear.assert_called_once()
            assert not mock_schedule.every.called


class TestEmailSending:
    def test_send_test_email_success(self, scheduler: ReportScheduler):
        with patch("expenses_tracker.automation.smtplib.SMTP") as mock_smtp:
            instance = MagicMock()
            mock_smtp.return_value.__enter__ = MagicMock(return_value=instance)
            mock_smtp.return_value.__exit__ = MagicMock(return_value=False)
            result = scheduler.send_test_email(
                {
                    "smtp_host": "smtp.example.com",
                    "smtp_port": 587,
                    "smtp_user": "user@example.com",
                    "smtp_password": "secret",
                    "email_to": "to@example.com",
                    "email_subject": "Test",
                }
            )
            assert result is True
            instance.starttls.assert_called_once()
            instance.login.assert_called_once_with("user@example.com", "secret")
            instance.send_message.assert_called_once()

    def test_send_test_email_missing_credentials(self, scheduler: ReportScheduler):
        result = scheduler.send_test_email({"smtp_host": None, "smtp_port": None})
        assert result is False


class TestSchedulerIntegration:
    def test_run_report_generates_files(self, db: ExpenseDatabase, scheduler: ReportScheduler):
        db.save_automation_config({"enabled": True, "export_format": "csv"})
        tx = TransactionInput(100.0, "income", "Salary", date(2025, 1, 1))
        db.add_transaction(tx)

        with patch("expenses_tracker.automation.export_reports") as mock_export:
            mock_export.return_value = []
            scheduler._run_report()
            mock_export.assert_called_once()

    def test_run_report_updates_last_run(self, db: ExpenseDatabase, scheduler: ReportScheduler):
        db.save_automation_config({"enabled": True, "export_format": "csv"})
        tx = TransactionInput(100.0, "income", "Salary", date(2025, 1, 1))
        db.add_transaction(tx)

        with patch("expenses_tracker.automation.export_reports", return_value=[]):
            scheduler._run_report()

        config = db.get_automation_config()
        assert config["last_run"] is not None

    def test_run_backup_creates_backup(self, db: ExpenseDatabase, scheduler: ReportScheduler):
        tx = TransactionInput(100.0, "income", "Salary", date(2025, 1, 1))
        db.add_transaction(tx)
        scheduler._run_backup()
        assert len(db.list_backups()) >= 1

    def test_update_schedule_adds_backup_job_when_backup_enabled(self, scheduler: ReportScheduler):
        with patch("expenses_tracker.automation.schedule") as mock_schedule:
            scheduler.update_schedule(
                {
                    "enabled": True,
                    "schedule_type": "daily",
                    "schedule_time": "08:00",
                    "backup_enabled": True,
                }
            )
            assert mock_schedule.every().day.at().do.call_count >= 2  # report + backup
