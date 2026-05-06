"""Tests for CategorySuggestionService."""

from __future__ import annotations

from expenses_tracker.services.category_suggestion_service import CategorySuggestionService


class TestCategorySuggestionService:
    def test_suggest_returns_none_when_empty(self) -> None:
        service = CategorySuggestionService()
        assert service.suggest("supermarket") is None

    def test_learn_and_suggest(self) -> None:
        service = CategorySuggestionService()
        transactions = [
            {"category": "Food", "description": "Weekly grocery shopping"},
            {"category": "Food", "description": "Supermarket run"},
            {"category": "Transport", "description": "Taxi to airport"},
        ]
        service.learn_from_transactions(transactions)
        assert service.suggest("grocery store") == "Food"
        assert service.suggest("taxi") == "Transport"

    def test_suggest_returns_none_for_unknown_words(self) -> None:
        service = CategorySuggestionService()
        service.learn_from_transactions([{"category": "Food", "description": "bread"}])
        assert service.suggest("xyz_unknown") is None

    def test_learn_ignores_empty_category_or_description(self) -> None:
        service = CategorySuggestionService()
        service.learn_from_transactions([
            {"category": "", "description": "something"},
            {"category": "Food", "description": ""},
            {"category": "Food", "description": "bread"},
        ])
        assert service.suggest("bread") == "Food"
