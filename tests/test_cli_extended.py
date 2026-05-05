"""Extended CLI tests for plot, export, and edge cases."""

from __future__ import annotations

import argparse
import sys
from datetime import date
from typing import Any

import pytest

from expenses_tracker import cli
from expenses_tracker.db import ExpenseDatabase, TransactionInput


def run_cli(args: list[str], monkeypatch: Any) -> tuple[int, str]:
    monkeypatch.setattr(sys, "argv", ["expenses"] + args)
    captured: list[str] = []
    import builtins
    monkeypatch.setattr(builtins, "print", lambda *a, **kw: captured.append(" ".join(str(x) for x in a)))
    exit_code = cli.main()
    return exit_code, "\n".join(captured)


class TestCliPlot:
    def test_plot_command_generates_files(self, tmp_path, monkeypatch):
        db_path = str(tmp_path / "test.db")
        db = ExpenseDatabase(db_path)
        db.initialize()
        db.add_transaction(TransactionInput(1000.0, "income", "Salary", date(2025, 1, 1)))
        db.add_transaction(TransactionInput(200.0, "expense", "Food", date(2025, 1, 10)))
        code, output = run_cli(
            ["--db-path", db_path, "plot", "--type", "bar", "--output-dir", str(tmp_path / "reports")],
            monkeypatch,
        )
        assert code == 0
        assert "chart" in output.lower() or "generated" in output.lower()

    def test_plot_no_data(self, tmp_path, monkeypatch):
        db_path = str(tmp_path / "test.db")
        db = ExpenseDatabase(db_path)
        db.initialize()
        code, output = run_cli(["--db-path", db_path, "plot"], monkeypatch)
        assert code == 0
        assert "no" in output.lower() or "data" in output.lower()


class TestCliExport:
    def test_export_command_generates_files(self, tmp_path, monkeypatch):
        db_path = str(tmp_path / "test.db")
        db = ExpenseDatabase(db_path)
        db.initialize()
        db.add_transaction(TransactionInput(1000.0, "income", "Salary", date(2025, 1, 1)))
        code, output = run_cli(
            ["--db-path", db_path, "export", "--format", "csv", "--output-dir", str(tmp_path / "reports")],
            monkeypatch,
        )
        assert code == 0
        assert "report" in output.lower() or "generated" in output.lower()

    def test_export_no_data(self, tmp_path, monkeypatch):
        db_path = str(tmp_path / "test.db")
        db = ExpenseDatabase(db_path)
        db.initialize()
        code, output = run_cli(["--db-path", db_path, "export"], monkeypatch)
        assert code == 0
        assert "no" in output.lower() or "data" in output.lower()


class TestCliParseDate:
    def test_invalid_date_raises(self, monkeypatch):
        with pytest.raises(ValueError):
            cli._parse_date("not-a-date", "en")


class TestCliPositiveInt:
    def test_positive_int_valid(self):
        assert cli._positive_int("5") == 5

    def test_positive_int_zero_raises(self):
        with pytest.raises(argparse.ArgumentTypeError, match="greater than 0"):
            cli._positive_int("0")

    def test_positive_int_negative_raises(self):
        with pytest.raises(argparse.ArgumentTypeError, match="greater than 0"):
            cli._positive_int("-1")

    def test_positive_int_non_int_raises(self):
        with pytest.raises(argparse.ArgumentTypeError, match="must be an integer"):
            cli._positive_int("abc")
