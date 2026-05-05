"""Extended automation tests for schedules, email and edge cases."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from expenses_tracker.automation import ReportScheduler
from expenses_tracker.db import TransactionInput


@pytest.fixture
def scheduler(db):
    def config_getter():
        return db.get_automation_config()
    return ReportScheduler(database=db, config_getter=config_getter, language="en")


class TestSchedulerSchedules:
    def test_update_schedule_weekly(self, scheduler):
        with patch("expenses_tracker.automation.schedule") as mock_schedule:
            scheduler.update_schedule({
                "enabled": True,
                "schedule_type": "weekly",
                "schedule_day": 1,
                "schedule_time": "09:00",
            })
            mock_schedule.clear.assert_called_once()
            assert mock_schedule.every().monday.at.called

    def test_update_schedule_monthly(self, scheduler):
        with patch("expenses_tracker.automation.schedule") as mock_schedule:
            scheduler.update_schedule({
                "enabled": True,
                "schedule_type": "monthly",
                "schedule_day": 15,
                "schedule_time": "10:00",
            })
            mock_schedule.clear.assert_called_once()
            assert mock_schedule.every().day.at.called

    def test_update_schedule_none_config(self, scheduler):
        with patch("expenses_tracker.automation.schedule") as mock_schedule:
            scheduler.update_schedule(None)
            mock_schedule.clear.assert_called_once()

    def test_run_monthly_report_on_wrong_day_does_nothing(self, scheduler, db):
        db.save_automation_config({"enabled": True, "export_format": "csv"})
        with patch.object(scheduler, "_run_report") as mock_report:
            scheduler._run_monthly_report(day=99)
            mock_report.assert_not_called()

    def test_run_monthly_backup_on_wrong_day_does_nothing(self, scheduler):
        with patch.object(scheduler, "_run_backup") as mock_backup:
            scheduler._run_monthly_backup(day=99)
            mock_backup.assert_not_called()

    def test_run_report_disabled(self, scheduler, db):
        db.save_automation_config({"enabled": False})
        with patch("expenses_tracker.automation.export_reports") as mock_export:
            scheduler._run_report()
            mock_export.assert_not_called()

    def test_run_report_no_transactions(self, scheduler, db):
        db.save_automation_config({"enabled": True, "export_format": "csv"})
        with patch("expenses_tracker.automation.export_reports") as mock_export:
            scheduler._run_report()
            mock_export.assert_not_called()

    def test_run_report_with_email(self, scheduler, db):
        db.save_automation_config({
            "enabled": True,
            "export_format": "csv",
            "email_enabled": True,
            "smtp_host": "smtp.example.com",
            "smtp_port": 587,
            "smtp_user": "user@example.com",
            "smtp_password": "secret",
            "email_to": "to@example.com",
            "email_subject": "Test",
        })
        db.add_transaction(TransactionInput(100.0, "income", "Salary", date(2025, 1, 1)))
        with patch("expenses_tracker.automation.export_reports") as mock_export:
            mock_export.return_value = [MagicMock()]
            with patch.object(scheduler, "_send_email") as mock_email:
                scheduler._run_report()
                mock_email.assert_called_once()

    def test_send_email_missing_config_returns_early(self, scheduler):
        with patch("expenses_tracker.automation.smtplib.SMTP") as mock_smtp:
            scheduler._send_email(MagicMock(), {})
            mock_smtp.assert_not_called()

    def test_send_test_email_exception_returns_false(self, scheduler):
        with patch("expenses_tracker.automation.smtplib.SMTP") as mock_smtp:
            mock_smtp.side_effect = Exception("SMTP error")
            result = scheduler.send_test_email({
                "smtp_host": "smtp.example.com",
                "smtp_port": 587,
                "smtp_user": "user@example.com",
                "smtp_password": "secret",
                "email_to": "to@example.com",
            })
            assert result is False

    def test_run_loop_exits_on_stop(self, scheduler):
        scheduler._stop_event.set()
        scheduler._run_loop()
        assert True  # should not hang

    def test_start_idempotent(self, scheduler):
        scheduler.start()
        thread = scheduler._thread
        scheduler.start()
        assert scheduler._thread is thread
        scheduler.stop()
