"""Tests for architecture improvements: DI, services and logging."""

from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path

import pytest

from expenses_tracker.di import Container
from expenses_tracker.logging_config import configure_logging, get_logger
from expenses_tracker.services import ExportService, TransactionService, UIStateService
from expenses_tracker.utils import (
    category_options_for_type,
    filter_transaction_rows,
    safe_parse_date,
)


# ---------------------------------------------------------------------------
# DI Container
# ---------------------------------------------------------------------------


class FakeService:
    def __init__(self, value: int = 42) -> None:
        self.value = value


def test_container_registers_and_resolves_singleton():
    container = Container()
    container.register("fake", lambda: FakeService(1), singleton=True)

    a = container.resolve("fake")
    b = container.resolve("fake")

    assert a.value == 1
    assert a is b


def test_container_factory_returns_new_instances():
    container = Container()
    container.register("fake", lambda: FakeService(), singleton=False)

    a = container.resolve("fake")
    b = container.resolve("fake")

    assert a is not b
    assert a.value == b.value


def test_container_raises_on_missing_service():
    container = Container()
    with pytest.raises(KeyError, match="not registered"):
        container.resolve("missing")


def test_container_has_returns_correctly():
    container = Container()
    assert not container.has("x")
    container.register("x", lambda: None)
    assert container.has("x")


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------


def test_configure_logging_creates_handlers(tmp_path: Path) -> None:
    log_dir = tmp_path / "logs"
    root = logging.getLogger()
    root.handlers.clear()
    configure_logging(level="DEBUG", log_dir=str(log_dir), json_format=True, console=False)
    logger = get_logger("test_logger")
    logger.info("hello")
    for handler in root.handlers:
        handler.flush()

    log_file = log_dir / "app.log"
    assert log_file.exists()
    content = log_file.read_text()
    assert "hello" in content
    assert "test_logger" in content
    # reset root handlers to avoid polluting other tests
    root.handlers.clear()


def test_json_formatter_includes_level_and_message() -> None:
    from expenses_tracker.logging_config import JSONFormatter

    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=0, msg="msg", args=(), exc_info=None
    )
    output = formatter.format(record)
    data = json.loads(output)
    assert data["level"] == "INFO"
    assert data["message"] == "msg"
    assert "timestamp" in data


# ---------------------------------------------------------------------------
# UIStateService
# ---------------------------------------------------------------------------


def test_state_service_reads_missing_file_as_empty(tmp_path: Path) -> None:
    svc = UIStateService(tmp_path / "nonexistent.json")
    assert svc.read() == {}


def test_state_service_roundtrips_data(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    svc = UIStateService(path)
    svc.write({"language": "es", "theme_mode": "dark"})
    assert svc.read() == {"language": "es", "theme_mode": "dark"}


def test_state_service_handles_corrupt_file(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("not json")
    svc = UIStateService(path)
    assert svc.read() == {}


# ---------------------------------------------------------------------------
# ExportService helpers
# ---------------------------------------------------------------------------


def test_export_service_compute_category_rows() -> None:
    transactions = [
        {"category": "Food", "amount": 10.0, "transaction_type": "expense", "transaction_date": "2026-01-01"},
        {"category": "Food", "amount": 20.0, "transaction_type": "expense", "transaction_date": "2026-01-02"},
        {"category": "Salary", "amount": 100.0, "transaction_type": "income", "transaction_date": "2026-01-03"},
    ]
    rows = ExportService.compute_category_rows(transactions)
    assert len(rows) == 2
    food = next(r for r in rows if r["category"] == "Food")
    assert food["expense"] == 30.0
    assert food["income"] == 0.0


def test_export_service_compute_month_rows() -> None:
    transactions = [
        {"category": "Food", "amount": 10.0, "transaction_type": "expense", "transaction_date": "2026-01-01"},
        {"category": "Food", "amount": 20.0, "transaction_type": "income", "transaction_date": "2026-02-01"},
    ]
    rows = ExportService.compute_month_rows(transactions)
    assert len(rows) == 2
    jan = next(r for r in rows if r["month"] == "2026-01")
    assert jan["expense"] == 10.0


# ---------------------------------------------------------------------------
# Utils (moved from gui.py)
# ---------------------------------------------------------------------------


def test_category_options_for_type_income():
    options = category_options_for_type("en", "income")
    assert any("Salary" in opt for opt in options)


def test_filter_transaction_rows_by_search():
    rows = [
        {"id": 1, "transaction_date": "2026-01-01", "transaction_type": "income", "category": "X", "amount": 1, "description": "hello"},
    ]
    result = filter_transaction_rows(rows, "hello", "", "All", "All", None, None, {})
    assert len(result) == 1
    result = filter_transaction_rows(rows, "missing", "", "All", "All", None, None, {})
    assert len(result) == 0


def test_safe_parse_date_valid_and_invalid():
    assert safe_parse_date("2026-04-01") == date(2026, 4, 1)
    assert safe_parse_date("") is None
    assert safe_parse_date("bad") is None
