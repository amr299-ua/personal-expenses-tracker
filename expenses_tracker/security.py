from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE

SPREADSHEET_FORMULA_PREFIXES = ("=", "+", "-", "@")


def apply_private_permissions(path: str | Path, *, directory: bool = False) -> None:
    """Best-effort local privacy hardening for user-owned app files."""
    mode = 0o700 if directory else 0o600
    try:
        os.chmod(path, mode)
    except (AttributeError, NotImplementedError, OSError):
        return


def sanitize_spreadsheet_text(value: Any) -> str:
    text = ILLEGAL_CHARACTERS_RE.sub("", str(value))
    stripped = text.lstrip()
    if stripped.startswith(SPREADSHEET_FORMULA_PREFIXES):
        return "'" + text
    return text
