"""Integration tests for the CLI entry point (cli.py)."""

from __future__ import annotations

import sys

import pytest

from expenses_tracker import cli
from expenses_tracker.db import ExpenseDatabase

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def run_cli(args: list[str], monkeypatch) -> tuple[int, str]:
    """Invoke cli.main() with patched argv; return (exit_code, stdout)."""
    monkeypatch.setattr(sys, "argv", ["expenses"] + args)
    captured = []

    import builtins
    monkeypatch.setattr(builtins, "print", lambda *a, **kw: captured.append(" ".join(str(x) for x in a)))

    exit_code = cli.main()
    return exit_code, "\n".join(captured)


# ---------------------------------------------------------------------------
# init-db
# ---------------------------------------------------------------------------


class TestInitDb:
    def test_returns_zero(self, tmp_path, monkeypatch):
        db_path = str(tmp_path / "test.db")
        code, _ = run_cli(["--db-path", db_path, "init-db"], monkeypatch)
        assert code == 0

    def test_prints_db_path(self, tmp_path, monkeypatch):
        db_path = str(tmp_path / "test.db")
        _, output = run_cli(["--db-path", db_path, "init-db"], monkeypatch)
        assert db_path in output

    def test_creates_database_file(self, tmp_path, monkeypatch):
        db_path = tmp_path / "test.db"
        run_cli(["--db-path", str(db_path), "init-db"], monkeypatch)
        assert db_path.exists()


# ---------------------------------------------------------------------------
# add
# ---------------------------------------------------------------------------


class TestAdd:
    def test_returns_zero_for_valid_transaction(self, tmp_path, monkeypatch):
        db_path = str(tmp_path / "test.db")
        code, _ = run_cli(
            ["--db-path", db_path, "add",
             "--type", "income", "--amount", "500",
             "--category", "Salario", "--date", "2025-01-15"],
            monkeypatch,
        )
        assert code == 0

    def test_prints_transaction_id(self, tmp_path, monkeypatch):
        db_path = str(tmp_path / "test.db")
        _, output = run_cli(
            ["--db-path", db_path, "add",
             "--type", "expense", "--amount", "80",
             "--category", "Transporte", "--date", "2025-01-20"],
            monkeypatch,
        )
        assert "1" in output  # first inserted row has id=1

    def test_transaction_is_persisted(self, tmp_path, monkeypatch):
        db_path = str(tmp_path / "test.db")
        run_cli(
            ["--db-path", db_path, "add",
             "--type", "income", "--amount", "1000",
             "--category", "Freelance", "--date", "2025-03-01"],
            monkeypatch,
        )
        db = ExpenseDatabase(db_path)
        rows = db.fetch_transactions(limit=None)
        assert len(rows) == 1
        assert rows[0]["category"] == "Freelance"
        assert rows[0]["amount"] == 1000.0

    def test_multiple_transactions_increment_id(self, tmp_path, monkeypatch):
        db_path = str(tmp_path / "test.db")
        for _ in range(3):
            run_cli(
                ["--db-path", db_path, "add",
                 "--type", "expense", "--amount", "10",
                 "--category", "Ocio", "--date", "2025-01-01"],
                monkeypatch,
            )
        db = ExpenseDatabase(db_path)
        rows = db.fetch_transactions(limit=None)
        assert len(rows) == 3


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


class TestList:
    def test_empty_db_prints_no_transactions(self, tmp_path, monkeypatch):
        db_path = str(tmp_path / "test.db")
        _, output = run_cli(["--db-path", db_path, "list"], monkeypatch)
        assert "No" in output or "no" in output or "recorded" in output.lower()

    def test_returns_zero_for_empty_db(self, tmp_path, monkeypatch):
        db_path = str(tmp_path / "test.db")
        code, _ = run_cli(["--db-path", db_path, "list"], monkeypatch)
        assert code == 0

    def test_shows_added_transactions(self, tmp_path, monkeypatch):
        db_path = str(tmp_path / "test.db")
        run_cli(
            ["--db-path", db_path, "add",
             "--type", "income", "--amount", "999",
             "--category", "TestCat", "--date", "2025-06-01"],
            monkeypatch,
        )
        _, output = run_cli(["--db-path", db_path, "list"], monkeypatch)
        assert "TestCat" in output

    def test_limit_flag(self, tmp_path, monkeypatch):
        db_path = str(tmp_path / "test.db")
        # Insert 5 transactions
        for i in range(1, 6):
            run_cli(
                ["--db-path", db_path, "add",
                 "--type", "expense", "--amount", str(i * 10),
                 "--category", "Cat", "--date", f"2025-0{i}-01"],
                monkeypatch,
            )
        # list --limit 2 should only show 2 lines with "[" (transaction rows)
        _, output = run_cli(["--db-path", db_path, "list", "--limit", "2"], monkeypatch)
        transaction_lines = [line for line in output.split("\n") if line.startswith("[")]
        assert len(transaction_lines) == 2

    def test_rejects_zero_limit(self, tmp_path, monkeypatch):
        db_path = str(tmp_path / "test.db")
        monkeypatch.setattr(sys, "argv", ["expenses", "--db-path", db_path, "list", "--limit", "0"])

        with pytest.raises(SystemExit) as error:
            cli.main()

        assert error.value.code == 2

    def test_rejects_negative_limit(self, tmp_path, monkeypatch):
        db_path = str(tmp_path / "test.db")
        monkeypatch.setattr(sys, "argv", ["expenses", "--db-path", db_path, "list", "--limit", "-1"])

        with pytest.raises(SystemExit) as error:
            cli.main()

        assert error.value.code == 2


# ---------------------------------------------------------------------------
# balance
# ---------------------------------------------------------------------------


class TestBalance:
    def test_returns_zero_exit_code(self, tmp_path, monkeypatch):
        db_path = str(tmp_path / "test.db")
        code, _ = run_cli(["--db-path", db_path, "balance"], monkeypatch)
        assert code == 0

    def test_shows_zero_balance_on_empty_db(self, tmp_path, monkeypatch):
        db_path = str(tmp_path / "test.db")
        _, output = run_cli(["--db-path", db_path, "balance"], monkeypatch)
        assert "0.00" in output

    def test_shows_correct_balance(self, tmp_path, monkeypatch):
        db_path = str(tmp_path / "test.db")
        run_cli(
            ["--db-path", db_path, "add",
             "--type", "income", "--amount", "1000",
             "--category", "Salario", "--date", "2025-01-01"],
            monkeypatch,
        )
        run_cli(
            ["--db-path", db_path, "add",
             "--type", "expense", "--amount", "300",
             "--category", "Alquiler", "--date", "2025-01-05"],
            monkeypatch,
        )
        _, output = run_cli(["--db-path", db_path, "balance"], monkeypatch)
        assert "700.00" in output


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------


class TestStats:
    def test_returns_zero(self, tmp_path, monkeypatch):
        db_path = str(tmp_path / "test.db")
        code, _ = run_cli(["--db-path", db_path, "stats"], monkeypatch)
        assert code == 0

    def test_shows_general_summary_header(self, tmp_path, monkeypatch):
        db_path = str(tmp_path / "test.db")
        _, output = run_cli(["--db-path", db_path, "stats"], monkeypatch)
        assert "SUMMARY" in output.upper() or "RESUMEN" in output.upper() or "===" in output

    def test_category_appears_in_stats(self, tmp_path, monkeypatch):
        db_path = str(tmp_path / "test.db")
        run_cli(
            ["--db-path", db_path, "add",
             "--type", "expense", "--amount", "50",
             "--category", "UniqueCategory", "--date", "2025-01-10"],
            monkeypatch,
        )
        _, output = run_cli(["--db-path", db_path, "stats"], monkeypatch)
        assert "UniqueCategory" in output


# ---------------------------------------------------------------------------
# --list-languages
# ---------------------------------------------------------------------------


class TestListLanguages:
    def test_returns_zero(self, tmp_path, monkeypatch):
        code, _ = run_cli(["--list-languages", "init-db"], monkeypatch)
        # --list-languages exits before requiring a subcommand in some implementations
        assert code == 0

    def test_output_contains_language_codes(self, tmp_path, monkeypatch):
        _, output = run_cli(["--list-languages", "init-db"], monkeypatch)
        assert "en" in output
        assert "es" in output


# ---------------------------------------------------------------------------
# --lang flag
# ---------------------------------------------------------------------------


class TestLangFlag:
    def test_spanish_balance_output(self, tmp_path, monkeypatch):
        db_path = str(tmp_path / "test.db")
        _, output = run_cli(["--db-path", db_path, "--lang", "es", "balance"], monkeypatch)
        # Spanish "current_balance" key contains different text from English
        en_code, en_output = run_cli(["--db-path", db_path, "--lang", "en", "balance"], monkeypatch)
        assert output != en_output
