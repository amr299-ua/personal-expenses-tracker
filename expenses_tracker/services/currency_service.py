"""Currency conversion and exchange-rate service.

Supports automatic rate fetching from a public API (frankfurter.app) and
manual rate entry. All conversions use the latest available rate for the
given date, falling back to the most recent stored rate.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import date
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from expenses_tracker.db import ExpenseDatabase

from expenses_tracker.schemas import ExchangeRateInput

DEFAULT_API_BASE = "https://api.frankfurter.app"


class CurrencyService:
    """High-level operations for multi-currency support."""

    def __init__(self, database: ExpenseDatabase, base_currency: str = "USD") -> None:
        self._database = database
        self._base_currency = base_currency.upper()

    @property
    def base_currency(self) -> str:
        """Return the configured base currency code."""
        return self._base_currency

    def set_base_currency(self, currency: str) -> None:
        """Update the base currency code."""
        self._base_currency = currency.strip().upper()

    def fetch_rate_from_api(
        self,
        from_currency: str,
        to_currency: str,
        rate_date: date | None = None,
    ) -> float | None:
        """Fetch a single rate from the public API and store it locally."""
        from_c = from_currency.strip().upper()
        to_c = to_currency.strip().upper()
        if from_c == to_c:
            return 1.0

        date_str = (rate_date or date.today()).isoformat()
        url = f"{DEFAULT_API_BASE}/{date_str}?from={from_c}&to={to_c}"
        try:
            with urllib.request.urlopen(url, timeout=15) as response:  # noqa: S310
                data = json.loads(response.read().decode("utf-8"))
            rate = float(data["rates"][to_c])
            self._database.add_exchange_rate(
                ExchangeRateInput(
                    from_currency=from_c,
                    to_currency=to_c,
                    rate=rate,
                    rate_date=date.fromisoformat(data["date"]),
                )
            )
            return rate
        except (urllib.error.URLError, KeyError, ValueError):
            return None

    def get_rate(
        self,
        from_currency: str,
        to_currency: str,
        rate_date: date | None = None,
    ) -> float | None:
        """Return the best available rate, trying local DB then API."""
        from_c = from_currency.strip().upper()
        to_c = to_currency.strip().upper()
        if from_c == to_c:
            return 1.0

        target_date = rate_date or date.today()
        # Try exact date first
        stored = self._database.get_exchange_rate(from_c, to_c, target_date.isoformat())
        if stored is not None:
            return stored

        # Try most recent stored rate
        rows = self._database.fetch_exchange_rates(from_currency=from_c, to_currency=to_c)
        if rows:
            # Already ordered by date desc
            return float(rows[0]["rate"])

        # Fallback to API
        return self.fetch_rate_from_api(from_c, to_c, target_date)

    def convert(
        self,
        amount: float,
        from_currency: str,
        to_currency: str | None = None,
        rate_date: date | None = None,
    ) -> float:
        """Convert an amount to the target currency (default base currency)."""
        to_c = (to_currency or self._base_currency).strip().upper()
        from_c = from_currency.strip().upper()
        if from_c == to_c:
            return amount
        rate = self.get_rate(from_c, to_c, rate_date)
        if rate is None:
            raise ValueError(f"No exchange rate available for {from_c} -> {to_c}")
        return amount * rate

    def add_manual_rate(
        self,
        from_currency: str,
        to_currency: str,
        rate: float,
        rate_date: date,
    ) -> int:
        """Manually insert or update an exchange rate."""
        return self._database.add_exchange_rate(
            ExchangeRateInput(
                from_currency=from_currency,
                to_currency=to_currency,
                rate=rate,
                rate_date=rate_date,
            )
        )

    def list_stored_rates(
        self,
        from_currency: str | None = None,
        to_currency: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return locally stored exchange rates."""
        return self._database.fetch_exchange_rates(
            from_currency=from_currency,
            to_currency=to_currency,
        )
