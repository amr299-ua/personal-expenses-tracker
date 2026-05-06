from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any, cast

LOCALES_DIR = Path(__file__).parent / "locales"

DEFAULT_LANGUAGE = "en"

_cache_meta: dict[str, dict[str, Any]] = {}
_cache_translations: dict[str, dict[str, str]] = {}
_cache_supported: dict[str, str] = {}


def _load_locale_file(language: str) -> dict[str, Any] | None:
    path = LOCALES_DIR / f"{language}.json"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return cast("dict[str, Any]", json.load(f))


def _ensure_loaded(language: str) -> None:
    if language in _cache_translations:
        return
    data = _load_locale_file(language)
    if data is not None:
        _cache_meta[language] = data.get("_meta", {})
        _cache_translations[language] = data.get("translations", {})
        name = data.get("_meta", {}).get("language_name", language)
        _cache_supported[language] = name


def _build_supported_languages() -> dict[str, str]:
    langs: dict[str, str] = {}
    for path in sorted(LOCALES_DIR.glob("*.json")):
        code = path.stem
        data = _load_locale_file(code)
        if data is not None:
            meta = data.get("_meta", {})
            translations = data.get("translations", {})
            langs[code] = meta.get("language_name", code)
            _cache_meta[code] = meta
            _cache_translations[code] = translations
            _cache_supported[code] = meta.get("language_name", code)
    return langs


SUPPORTED_LANGUAGES: dict[str, str] = _build_supported_languages()


def reload_translations() -> dict[str, str]:
    """Reload all locale files from disk and return supported languages."""
    global SUPPORTED_LANGUAGES
    _cache_meta.clear()
    _cache_translations.clear()
    _cache_supported.clear()
    SUPPORTED_LANGUAGES = _build_supported_languages()
    return SUPPORTED_LANGUAGES


def normalize_language(language: str | None) -> str:
    """Normalize a language code to a supported value or default."""
    if language is None:
        return DEFAULT_LANGUAGE

    normalized = language.strip().lower()
    if normalized in SUPPORTED_LANGUAGES:
        return normalized
    return DEFAULT_LANGUAGE


def list_languages() -> list[tuple[str, str]]:
    """Return sorted list of (code, name) tuples for supported languages."""
    return sorted(SUPPORTED_LANGUAGES.items(), key=lambda item: item[0])


def language_label(code: str) -> str:
    """Return a display label like 'English (en)' for a language code."""
    normalized = normalize_language(code)
    name = SUPPORTED_LANGUAGES.get(normalized, normalized)
    return f"{name} ({normalized})"


def tr(language: str | None, key: str, **kwargs: Any) -> str:
    """Translate a key for the given language, with optional format kwargs."""
    normalized = normalize_language(language)
    _ensure_loaded(normalized)

    values = _cache_translations.get(normalized)
    if values is None:
        values = _cache_translations.get(DEFAULT_LANGUAGE, {})

    template = values.get(key)
    if template is None:
        fallback = _cache_translations.get(DEFAULT_LANGUAGE, {})
        template = fallback.get(key, key)

    if kwargs:
        return template.format(**kwargs)
    return template


def month_name(language: str | None, month_number: int) -> str:
    """Return the localized name for a month number (1-12)."""
    key = f"calendar_m{month_number}"
    return tr(language, key)


def get_locale_config(language: str | None) -> dict[str, Any]:
    """Return locale formatting configuration for a language."""
    normalized = normalize_language(language)
    _ensure_loaded(normalized)
    meta = _cache_meta.get(normalized, {})
    return {
        "date_format": meta.get("date_format", "YYYY-MM-DD"),
        "decimal_separator": meta.get("decimal_separator", "."),
        "thousands_separator": meta.get("thousands_separator", ","),
        "rtl": meta.get("rtl", False),
    }


def is_rtl(language: str | None) -> bool:
    """Return True if the language uses right-to-left text direction."""
    config = get_locale_config(language)
    return bool(config.get("rtl", False))


def reshape_for_rtl(text: str) -> str:
    """Reshape Arabic text for proper display in Tkinter.

    Uses arabic_reshaper to fix character joining and python-bidi
    to apply the Unicode bidirectional algorithm.
    """
    if not text:
        return text
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display

        reshaped = arabic_reshaper.reshape(text)
        return cast("str", get_display(reshaped))
    except Exception:
        return text


def format_date(language: str | None, d: date | datetime) -> str:
    """Format a date according to the locale's date format pattern."""
    config = get_locale_config(language)

    if isinstance(d, datetime):
        d = d.date()

    year = f"{d.year:04d}"
    month = f"{d.month:02d}"
    day = f"{d.day:02d}"

    fmt = cast("str", config["date_format"])
    return fmt.replace("YYYY", year).replace("MM", month).replace("DD", day)


def format_number(
    language: str | None,
    value: float | int,
    decimals: int = 2,
) -> str:
    """Format a number with locale-specific separators."""
    config = get_locale_config(language)
    dec_sep = config["decimal_separator"]
    thou_sep = config["thousands_separator"]

    raw = f"{abs(value):.{decimals}f}"

    parts = raw.split(".")
    integer_part = parts[0]
    decimal_part = parts[1] if len(parts) > 1 else ""

    grouped = _group_integer(integer_part, thou_sep)
    result = grouped

    if decimal_part:
        result = result + dec_sep + decimal_part

    if value < 0:
        result = "-" + result

    return result


def _group_integer(integer_str: str, separator: str) -> str:
    if len(integer_str) <= 3:
        return integer_str
    groups: list[str] = []
    remaining = integer_str
    while remaining:
        groups.append(remaining[-3:])
        remaining = remaining[:-3]
    return separator.join(reversed(groups))
