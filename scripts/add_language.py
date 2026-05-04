#!/usr/bin/env python3
"""Helper script to add a new language to the expenses tracker.

Usage:
    python scripts/add_language.py <language_code> <language_name> [--date-format FMT]
                                    [--decimal-sep SEP] [--thousands-sep SEP] [--rtl]

Examples:
    python scripts/add_language.py ko 한국어 --date-format YYYY.MM.DD --decimal-sep . --thousands-sep ,
    python scripts/add_language.py hi हिन्दी --date-format DD-MM-YYYY --rtl

The script creates a new locale JSON file with English translations as placeholders.
Fill in the translations manually or use machine translation, then validate with
the --validate flag.

Validate an existing locale:
    python scripts/add_language.py --validate ja
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

LOCALES_DIR = Path(__file__).resolve().parent.parent / "expenses_tracker" / "locales"


def get_en_translations() -> dict[str, str]:
    en_path = LOCALES_DIR / "en.json"
    with open(en_path, encoding="utf-8") as f:
        data = json.load(f)
    return data["translations"]


def create_locale(
    code: str,
    name: str,
    date_format: str,
    decimal_sep: str,
    thousands_sep: str,
    rtl: bool,
) -> None:
    dest = LOCALES_DIR / f"{code}.json"
    if dest.exists():
        print(f"Error: {dest} already exists.", file=sys.stderr)
        sys.exit(1)

    en_translations = get_en_translations()

    meta = {
        "language_name": name,
        "code": code,
        "date_format": date_format,
        "decimal_separator": decimal_sep,
        "thousands_separator": thousands_sep,
        "rtl": rtl,
    }

    placeholder_translations = dict(en_translations)

    locale_data = {
        "_meta": meta,
        "translations": placeholder_translations,
    }

    with open(dest, "w", encoding="utf-8") as f:
        json.dump(locale_data, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"Created {dest}")
    print(f"  Language: {name} ({code})")
    print(f"  Date format: {date_format}")
    print(f"  Decimal separator: '{decimal_sep}'")
    print(f"  Thousands separator: '{thousands_sep}'")
    print(f"  RTL: {rtl}")
    print()
    print(f"Next steps:")
    print(f"  1. Edit {dest} and replace English placeholders with {name} translations")
    print(f"  2. Validate: python scripts/add_language.py --validate {code}")


def validate_locale(code: str) -> None:
    locale_path = LOCALES_DIR / f"{code}.json"
    if not locale_path.exists():
        print(f"Error: {locale_path} does not exist.", file=sys.stderr)
        sys.exit(1)

    en_translations = get_en_translations()
    en_keys = set(en_translations.keys())

    with open(locale_path, encoding="utf-8") as f:
        data = json.load(f)

    meta = data.get("_meta", {})
    translations = data.get("translations", {})
    locale_keys = set(translations.keys())

    missing = en_keys - locale_keys
    extra = locale_keys - en_keys
    same_as_en = [k for k in locale_keys & en_keys if translations[k] == en_translations[k]]

    errors = 0

    required_meta = ["language_name", "code", "date_format", "decimal_separator", "thousands_separator", "rtl"]
    for key in required_meta:
        if key not in meta:
            print(f"  ERROR: Missing _meta key: {key}")
            errors += 1

    if meta.get("code") != code:
        print(f"  ERROR: _meta.code is '{meta.get('code')}', expected '{code}'")
        errors += 1

    if missing:
        print(f"  WARNING: {len(missing)} missing translation keys: {sorted(missing)[:10]}{'...' if len(missing) > 10 else ''}")
        errors += 1

    if extra:
        print(f"  WARNING: {len(extra)} extra translation keys: {sorted(extra)[:10]}{'...' if len(extra) > 10 else ''}")

    if same_as_en:
        print(f"  INFO: {len(same_as_en)} translations still in English (need translation)")
        if len(same_as_en) <= 20:
            for k in same_as_en:
                print(f"    - {k}")

    if errors == 0 and not same_as_en:
        print(f"  OK: {code} locale is valid and fully translated ({len(locale_keys)} keys)")
    elif errors == 0:
        print(f"  OK: {code} locale structure is valid ({len(same_as_en)} keys still need translation)")

    return errors == 0


def list_locales() -> None:
    print("Available locales:")
    for path in sorted(LOCALES_DIR.glob("*.json")):
        code = path.stem
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        name = data.get("_meta", {}).get("language_name", code)
        rtl = data.get("_meta", {}).get("rtl", False)
        n_keys = len(data.get("translations", {}))
        rtl_marker = " (RTL)" if rtl else ""
        print(f"  {code}: {name} ({n_keys} keys){rtl_marker}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Add a new language or validate existing locales for the expenses tracker."
    )
    parser.add_argument("code", nargs="?", help="ISO 639-1 language code (e.g. ko, hi)")
    parser.add_argument("name", nargs="?", help="Native language name (e.g. 한국어, हिन्दी)")
    parser.add_argument("--date-format", default="YYYY-MM-DD", help="Date format (default: YYYY-MM-DD)")
    parser.add_argument("--decimal-sep", default=".", help="Decimal separator (default: .)")
    parser.add_argument("--thousands-sep", default=",", help="Thousands separator (default: ,)")
    parser.add_argument("--rtl", action="store_true", help="Mark as right-to-left language")
    parser.add_argument("--validate", metavar="CODE", help="Validate an existing locale file")
    parser.add_argument("--list", action="store_true", help="List all available locales")

    args = parser.parse_args()

    if args.list:
        list_locales()
        return

    if args.validate:
        validate_locale(args.validate)
        return

    if not args.code or not args.name:
        parser.print_help()
        sys.exit(1)

    create_locale(
        code=args.code,
        name=args.name,
        date_format=args.date_format,
        decimal_sep=args.decimal_sep,
        thousands_sep=args.thousands_sep,
        rtl=args.rtl,
    )


if __name__ == "__main__":
    main()