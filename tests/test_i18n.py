"""Tests for the i18n module: translations, language helpers."""

from __future__ import annotations

import pytest

from expenses_tracker.i18n import (
    DEFAULT_LANGUAGE,
    SUPPORTED_LANGUAGES,
    language_label,
    list_languages,
    month_name,
    normalize_language,
    tr,
)


# ---------------------------------------------------------------------------
# normalize_language()
# ---------------------------------------------------------------------------


class TestNormalizeLanguage:
    def test_valid_code_returned_unchanged(self):
        assert normalize_language("es") == "es"

    def test_uppercased_code_lowercased(self):
        assert normalize_language("ES") == "es"

    def test_mixed_case(self):
        assert normalize_language("Fr") == "fr"

    def test_none_returns_default(self):
        assert normalize_language(None) == DEFAULT_LANGUAGE

    def test_empty_string_returns_default(self):
        assert normalize_language("") == DEFAULT_LANGUAGE

    def test_unknown_code_returns_default(self):
        assert normalize_language("xx") == DEFAULT_LANGUAGE

    def test_all_supported_languages_accepted(self):
        for code in SUPPORTED_LANGUAGES:
            assert normalize_language(code) == code


# ---------------------------------------------------------------------------
# list_languages()
# ---------------------------------------------------------------------------


class TestListLanguages:
    def test_returns_list_of_tuples(self):
        result = list_languages()
        assert isinstance(result, list)
        assert all(isinstance(item, tuple) and len(item) == 2 for item in result)

    def test_contains_all_supported_languages(self):
        codes = {code for code, _ in list_languages()}
        assert codes == set(SUPPORTED_LANGUAGES.keys())

    def test_is_sorted_by_code(self):
        codes = [code for code, _ in list_languages()]
        assert codes == sorted(codes)

    def test_values_are_strings(self):
        for code, name in list_languages():
            assert isinstance(code, str)
            assert isinstance(name, str)


# ---------------------------------------------------------------------------
# language_label()
# ---------------------------------------------------------------------------


class TestLanguageLabel:
    def test_english_label(self):
        label = language_label("en")
        assert "English" in label
        assert "en" in label

    def test_spanish_label(self):
        label = language_label("es")
        assert "es" in label

    def test_invalid_code_falls_back_to_english(self):
        label = language_label("xx")
        assert "en" in label

    def test_format_is_name_parenthesis_code(self):
        label = language_label("en")
        assert label == "English (en)"


# ---------------------------------------------------------------------------
# tr()
# ---------------------------------------------------------------------------


class TestTr:
    def test_returns_english_translation(self):
        result = tr("en", "amount_positive")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_returns_spanish_translation_different_from_english(self):
        en = tr("en", "amount_positive")
        es = tr("es", "amount_positive")
        assert en != es

    def test_none_language_returns_english(self):
        assert tr(None, "amount_positive") == tr("en", "amount_positive")

    def test_unknown_language_returns_english(self):
        assert tr("xx", "amount_positive") == tr("en", "amount_positive")

    def test_unknown_key_returns_key_itself(self):
        result = tr("en", "this_key_does_not_exist_xyz")
        assert result == "this_key_does_not_exist_xyz"

    def test_kwargs_are_interpolated(self):
        result = tr("en", "current_balance", amount=42.5)
        assert "42.50" in result

    def test_invalid_type_message_includes_value(self):
        result = tr("en", "invalid_type", value="transfer")
        assert "transfer" in result

    def test_db_initialized_includes_path(self):
        result = tr("en", "db_initialized", path="/tmp/test.db")
        assert "/tmp/test.db" in result

    def test_all_supported_languages_have_amount_positive_key(self):
        for code in SUPPORTED_LANGUAGES:
            result = tr(code, "amount_positive")
            assert isinstance(result, str)
            assert result != "amount_positive"  # not falling through to key

    def test_all_supported_languages_have_kpi_labels(self):
        for code in SUPPORTED_LANGUAGES:
            income_label = tr(code, "income_total_label")
            expense_label = tr(code, "expense_total_label")
            assert income_label != "income_total_label"
            assert expense_label != "expense_total_label"

    def test_delete_not_found_message_present(self):
        for code in SUPPORTED_LANGUAGES:
            result = tr(code, "delete_not_found")
            assert result != "delete_not_found"

    def test_security_validation_messages_present(self):
        for code in SUPPORTED_LANGUAGES:
            assert tr(code, "category_too_long", limit=120) != "category_too_long"
            assert tr(code, "description_too_long", limit=1000) != "description_too_long"

    def test_ui_feature_messages_present(self):
        for code in SUPPORTED_LANGUAGES:
            assert tr(code, "btn_export_csv") != "btn_export_csv"
            assert tr(code, "btn_update_transaction") != "btn_update_transaction"
            assert tr(code, "success_updated", id=1) != "success_updated"
            assert tr(code, "update_not_found") != "update_not_found"

    def test_french_translation(self):
        result = tr("fr", "no_transactions")
        assert isinstance(result, str)
        assert result != tr("en", "no_transactions")


# ---------------------------------------------------------------------------
# month_name()
# ---------------------------------------------------------------------------


class TestMonthName:
    def test_january_english(self):
        assert month_name("en", 1) == "January"

    def test_december_english(self):
        assert month_name("en", 12) == "December"

    def test_january_spanish(self):
        assert month_name("es", 1) == "Enero"

    def test_all_12_months_english(self):
        expected = [
            "January", "February", "March", "April",
            "May", "June", "July", "August",
            "September", "October", "November", "December",
        ]
        for i, name in enumerate(expected, start=1):
            assert month_name("en", i) == name

    def test_none_language_falls_back_to_english(self):
        assert month_name(None, 1) == month_name("en", 1)

    def test_spanish_months_differ_from_english(self):
        for i in range(1, 13):
            en = month_name("en", i)
            es = month_name("es", i)
            assert en != es, f"Month {i} should differ between en and es"
