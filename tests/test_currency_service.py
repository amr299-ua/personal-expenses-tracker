"""Tests for CurrencyService."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from expenses_tracker.services.currency_service import CurrencyService


class TestCurrencyService:
    def test_base_currency_default(self) -> None:
        db = MagicMock()
        service = CurrencyService(db)
        assert service.base_currency == "USD"

    def test_set_base_currency(self) -> None:
        db = MagicMock()
        service = CurrencyService(db)
        service.set_base_currency("eur")
        assert service.base_currency == "EUR"

    def test_convert_same_currency(self) -> None:
        db = MagicMock()
        service = CurrencyService(db)
        assert service.convert(100.0, "USD", "USD") == 100.0

    def test_convert_uses_local_rate(self) -> None:
        db = MagicMock()
        db.get_exchange_rate.return_value = 0.85
        service = CurrencyService(db)
        result = service.convert(100.0, "USD", "EUR", date(2025, 1, 1))
        assert result == pytest.approx(85.0)

    def test_convert_no_rate_raises(self) -> None:
        db = MagicMock()
        db.get_exchange_rate.return_value = None
        db.fetch_exchange_rates.return_value = []
        service = CurrencyService(db)
        with pytest.raises(ValueError):
            service.convert(100.0, "USD", "EUR")

    def test_add_manual_rate(self) -> None:
        db = MagicMock()
        db.add_exchange_rate.return_value = 42
        service = CurrencyService(db)
        rid = service.add_manual_rate("USD", "EUR", 0.92, date(2025, 1, 1))
        assert rid == 42
        db.add_exchange_rate.assert_called_once()

    @patch("expenses_tracker.services.currency_service.urllib.request.urlopen")
    def test_fetch_rate_from_api_success(self, mock_urlopen: MagicMock) -> None:
        db = MagicMock()
        service = CurrencyService(db)
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"rates": {"EUR": 0.92}, "date": "2025-01-01"}'
        mock_urlopen.return_value.__enter__.return_value = mock_response

        rate = service.fetch_rate_from_api("USD", "EUR", date(2025, 1, 1))
        assert rate == pytest.approx(0.92)
        db.add_exchange_rate.assert_called_once()

    @patch("expenses_tracker.services.currency_service.urllib.request.urlopen")
    def test_fetch_rate_from_api_failure_returns_none(self, mock_urlopen: MagicMock) -> None:
        db = MagicMock()
        service = CurrencyService(db)
        from urllib.error import URLError
        mock_urlopen.side_effect = URLError("Network error")

        assert service.fetch_rate_from_api("USD", "EUR") is None
