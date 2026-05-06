"""Category suggestion service based on historical transaction descriptions.

Uses a simple keyword-frequency algorithm: learns from past transactions
which words map to which categories, then suggests the most likely category
for a new description.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any


class CategorySuggestionService:
    """Provides auto-categorization suggestions from description text."""

    def __init__(self) -> None:
        self._word_to_category: dict[str, Counter[str]] = {}
        self._learned = False

    def learn_from_transactions(self, transactions: list[dict[str, Any]]) -> None:
        """Build internal word->category frequency map from existing transactions."""
        self._word_to_category.clear()
        for tx in transactions:
            category = str(tx.get("category", "")).strip()
            description = str(tx.get("description", "")).strip()
            if not category or not description:
                continue
            words = self._tokenize(description)
            for word in words:
                if word not in self._word_to_category:
                    self._word_to_category[word] = Counter()
                self._word_to_category[word][category] += 1
        self._learned = bool(self._word_to_category)

    def suggest(self, description: str) -> str | None:
        """Return the most likely category for a given description, or None."""
        if not self._learned or not description.strip():
            return None
        words = self._tokenize(description)
        category_scores: Counter[str] = Counter()
        for word in words:
            if word in self._word_to_category:
                category_scores.update(self._word_to_category[word])
        if not category_scores:
            return None
        return category_scores.most_common(1)[0][0]

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        """Extract lowercase alphabetic tokens from text."""
        return set(re.findall(r"[a-zA-Z\u00C0-\u024F\u0400-\u04FF]+", text.lower()))
