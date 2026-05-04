"""Security helper tests."""

from __future__ import annotations

import os
import stat

from expenses_tracker.security import apply_private_permissions, sanitize_spreadsheet_text


def test_sanitize_spreadsheet_text_prefixes_formula_triggers():
    assert sanitize_spreadsheet_text("=1+1") == "'=1+1"
    assert sanitize_spreadsheet_text("+SUM(1,1)") == "'+SUM(1,1)"
    assert sanitize_spreadsheet_text("-10+20") == "'-10+20"
    assert sanitize_spreadsheet_text("@cmd") == "'@cmd"


def test_sanitize_spreadsheet_text_handles_leading_whitespace_before_formula():
    assert sanitize_spreadsheet_text("  =1+1") == "'  =1+1"


def test_sanitize_spreadsheet_text_removes_illegal_xlsx_control_chars():
    assert sanitize_spreadsheet_text("safe\x01text") == "safetext"


def test_apply_private_permissions_sets_file_mode_on_posix(tmp_path):
    if os.name == "nt":
        return

    file_path = tmp_path / "private.txt"
    file_path.write_text("secret", encoding="utf-8")

    apply_private_permissions(file_path)

    mode = stat.S_IMODE(file_path.stat().st_mode)
    assert mode == 0o600
