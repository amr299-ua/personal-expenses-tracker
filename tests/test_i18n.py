"""Tests for the i18n module: translations, language helpers, locale formatting."""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

import pytest

from expenses_tracker.i18n import (
    DEFAULT_LANGUAGE,
    LOCALES_DIR,
    SUPPORTED_LANGUAGES,
    format_date,
    format_number,
    get_locale_config,
    is_rtl,
    language_label,
    list_languages,
    month_name,
    normalize_language,
    reload_translations,
    reshape_for_rtl,
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


# ---------------------------------------------------------------------------
# New languages (Japanese, Arabic)
# ---------------------------------------------------------------------------


class TestNewLanguages:
    def test_japanese_is_supported(self):
        assert "ja" in SUPPORTED_LANGUAGES
        assert SUPPORTED_LANGUAGES["ja"] == "日本語"

    def test_arabic_is_supported(self):
        assert "ar" in SUPPORTED_LANGUAGES
        assert SUPPORTED_LANGUAGES["ar"] == "العربية"

    def test_japanese_translations_work(self):
        result = tr("ja", "app_title")
        assert result != "app_title"
        assert isinstance(result, str)

    def test_arabic_translations_work(self):
        result = tr("ar", "app_title")
        assert result != "app_title"
        assert isinstance(result, str)

    def test_japanese_key_coverage(self):
        en_keys = _get_locale_keys("en")
        ja_keys = _get_locale_keys("ja")
        assert en_keys == ja_keys, f"ja locale missing keys: {en_keys - ja_keys}"

    def test_arabic_key_coverage(self):
        en_keys = _get_locale_keys("en")
        ar_keys = _get_locale_keys("ar")
        assert en_keys == ar_keys, f"ar locale missing keys: {en_keys - ar_keys}"

    def test_arabic_rtl_flag(self):
        config = get_locale_config("ar")
        assert config["rtl"] is True

    def test_japanese_not_rtl(self):
        config = get_locale_config("ja")
        assert config["rtl"] is False


# ---------------------------------------------------------------------------
# is_rtl() / reshape_for_rtl()
# ---------------------------------------------------------------------------


class TestRtlHelpers:
    def test_is_rtl_true_for_arabic(self):
        assert is_rtl("ar") is True

    def test_is_rtl_false_for_english(self):
        assert is_rtl("en") is False

    def test_is_rtl_false_for_spanish(self):
        assert is_rtl("es") is False

    def test_reshape_for_rtl_returns_string(self):
        result = reshape_for_rtl("مرحبا")
        assert isinstance(result, str)

    def test_reshape_for_rtl_empty_string(self):
        assert reshape_for_rtl("") == ""

    def test_reshape_for_rtl_latin_unchanged(self):
        assert reshape_for_rtl("hello") == "hello"


# ---------------------------------------------------------------------------
# JSON locale files
# ---------------------------------------------------------------------------


class TestLocaleFiles:
    def test_all_locales_have_json_files(self):
        for code in SUPPORTED_LANGUAGES:
            path = LOCALES_DIR / f"{code}.json"
            assert path.exists(), f"Missing locale file for {code}"

    def test_all_locale_files_have_meta(self):
        for code in SUPPORTED_LANGUAGES:
            path = LOCALES_DIR / f"{code}.json"
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            assert "_meta" in data, f"{code} locale missing _meta section"
            meta = data["_meta"]
            assert "language_name" in meta
            assert "code" in meta
            assert "date_format" in meta
            assert "decimal_separator" in meta
            assert "thousands_separator" in meta
            assert "rtl" in meta

    def test_all_locale_files_have_translations(self):
        for code in SUPPORTED_LANGUAGES:
            path = LOCALES_DIR / f"{code}.json"
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            assert "translations" in data, f"{code} locale missing translations section"
            assert len(data["translations"]) > 0

    def test_all_locales_match_keys_with_english(self):
        en_keys = _get_locale_keys("en")
        for code in SUPPORTED_LANGUAGES:
            if code == "en":
                continue
            locale_keys = _get_locale_keys(code)
            missing = en_keys - locale_keys
            extra = locale_keys - en_keys
            assert not missing, f"{code} missing keys: {sorted(missing)[:5]}"
            assert not extra, f"{code} extra keys: {sorted(extra)[:5]}"

    def test_locale_meta_code_matches_filename(self):
        for code in SUPPORTED_LANGUAGES:
            path = LOCALES_DIR / f"{code}.json"
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            assert data["_meta"]["code"] == code


# ---------------------------------------------------------------------------
# Reload translations (hot-reload)
# ---------------------------------------------------------------------------


class TestReloadTranslations:
    def test_reload_returns_supported_languages(self):
        result = reload_translations()
        assert isinstance(result, dict)
        assert len(result) >= 6

    def test_reload_preserves_existing_languages(self):
        original_codes = set(SUPPORTED_LANGUAGES.keys())
        reload_translations()
        assert set(SUPPORTED_LANGUAGES.keys()) == original_codes

    def test_reload_translations_are_still_accessible(self):
        reload_translations()
        assert tr("en", "app_title") == "Personal Expenses Tracker"
        assert tr("es", "app_title") == "Control de gastos personal"

    def test_reload_reflects_new_locale_file(self, tmp_path):
        test_locale = {
            "_meta": {
                "language_name": "TestLang",
                "code": "zz",
                "date_format": "YYYY-MM-DD",
                "decimal_separator": ".",
                "thousands_separator": ",",
                "rtl": False,
            },
            "translations": {"app_title": "Test App", "language_name": "TestLang"},
        }
        temp_file = tmp_path / "zz.json"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(test_locale, f)

        original_dir = LOCALES_DIR
        try:
            import expenses_tracker.i18n as i18n_mod
            i18n_mod.LOCALES_DIR = tmp_path
            result = reload_translations()
            assert "zz" in result
            assert tr("zz", "app_title") == "Test App"
        finally:
            i18n_mod.LOCALES_DIR = original_dir
            reload_translations()


# ---------------------------------------------------------------------------
# format_date()
# ---------------------------------------------------------------------------


class TestFormatDate:
    def test_english_format(self):
        result = format_date("en", date(2026, 5, 4))
        assert result == "05/04/2026"

    def test_spanish_format(self):
        result = format_date("es", date(2026, 5, 4))
        assert result == "04/05/2026"

    def test_german_format(self):
        result = format_date("de", date(2026, 5, 4))
        assert result == "04.05.2026"

    def test_japanese_format(self):
        result = format_date("ja", date(2026, 5, 4))
        assert result == "2026/05/04"

    def test_with_datetime(self):
        result = format_date("en", datetime(2026, 5, 4, 10, 30))
        assert result == "05/04/2026"

    def test_unknown_language_falls_back(self):
        result = format_date("xx", date(2026, 5, 4))
        assert isinstance(result, str)
        assert "2026" in result


# ---------------------------------------------------------------------------
# format_number()
# ---------------------------------------------------------------------------


class TestFormatNumber:
    def test_english_number(self):
        assert format_number("en", 1234567.89) == "1,234,567.89"

    def test_spanish_number(self):
        assert format_number("es", 1234567.89) == "1.234.567,89"

    def test_german_number(self):
        assert format_number("de", 1234567.89) == "1.234.567,89"

    def test_french_number(self):
        assert format_number("fr", 1234567.89) == "1 234 567,89"

    def test_small_number(self):
        result = format_number("en", 42.5)
        assert "42.50" in result

    def test_integer_with_zero_decimals(self):
        result = format_number("en", 1000, decimals=0)
        assert "1,000" in result

    def test_negative_number(self):
        result = format_number("en", -1234.56)
        assert result.startswith("-")

    def test_unknown_language_falls_back(self):
        result = format_number("xx", 1234.56)
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# get_locale_config()
# ---------------------------------------------------------------------------


class TestGetLocaleConfig:
    def test_english_config(self):
        config = get_locale_config("en")
        assert config["date_format"] == "MM/DD/YYYY"
        assert config["decimal_separator"] == "."
        assert config["thousands_separator"] == ","
        assert config["rtl"] is False

    def test_spanish_config(self):
        config = get_locale_config("es")
        assert config["date_format"] == "DD/MM/YYYY"
        assert config["decimal_separator"] == ","
        assert config["thousands_separator"] == "."
        assert config["rtl"] is False

    def test_arabic_rtl(self):
        config = get_locale_config("ar")
        assert config["rtl"] is True

    def test_german_config(self):
        config = get_locale_config("de")
        assert config["date_format"] == "DD.MM.YYYY"

    def test_japanese_config(self):
        config = get_locale_config("ja")
        assert config["date_format"] == "YYYY/MM/DD"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_locale_keys(code: str) -> set[str]:
    path = LOCALES_DIR / f"{code}.json"
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return set(data["translations"].keys())
