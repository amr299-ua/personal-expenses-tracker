"""Theme and style management for the Tkinter GUI.

Isolates ttkbootstrap setup, color palettes and ttk style configuration.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import ttkbootstrap as ttkb

from expenses_tracker.charts import PALETTES


class ThemeManager:
    """Manages application theme, color palette and ttk styles."""

    def __init__(self, theme_mode: str = "light", palette: str = "default") -> None:
        self.theme_mode = theme_mode if theme_mode in {"light", "dark"} else "light"
        self.palette = palette if palette in PALETTES else "default"
        self._colors: dict[str, str] = {}
        self._ttkb_style: ttkb.Style | None = None

    @property
    def colors(self) -> dict[str, str]:
        """Current color dictionary derived from the active theme."""
        return self._colors

    def setup(self, root: tk.Tk) -> None:
        """Configure ttkbootstrap theme and ttk styles."""
        theme_name = "flatly" if self.theme_mode == "light" else "darkly"
        self._ttkb_style = ttkb.Style(theme_name)  # type: ignore[no-untyped-call]
        c = self._ttkb_style.colors

        if self.theme_mode == "dark":
            self._colors = {
                "bg": c.bg,
                "card": "#2b2b2b",
                "header": c.dark,
                "text": c.fg,
                "muted": c.secondary,
                "accent": c.primary,
                "accent_hover": c.info,
                "line": c.border,
                "input_bg": c.inputbg,
                "notebook_bg": "#333333",
                "select_bg": c.selectbg,
                "select_fg": c.fg,
                "positive": c.success,
                "negative": c.danger,
            }
        else:
            self._colors = {
                "bg": c.bg,
                "card": "#ffffff",
                "header": c.dark,
                "text": c.fg,
                "muted": c.secondary,
                "accent": c.primary,
                "accent_hover": c.info,
                "line": c.border,
                "input_bg": c.inputbg,
                "notebook_bg": "#f0f0f0",
                "select_bg": c.selectbg,
                "select_fg": c.primary,
                "positive": c.success,
                "negative": c.danger,
            }

        style = ttk.Style(root)
        root.configure(background=self._colors["bg"])
        root.option_add("*Font", "TkDefaultFont 10")

        style.configure("TFrame", background=self._colors["bg"])
        style.configure("App.TFrame", background=self._colors["bg"])
        style.configure("Card.TFrame", background=self._colors["card"])
        style.configure("Header.TFrame", background=self._colors["header"])

        style.configure("TLabel", background=self._colors["bg"], foreground=self._colors["text"])
        style.configure(
            "HeaderTitle.TLabel",
            background=self._colors["header"],
            foreground="#f8fafc",
            font=("TkDefaultFont", 16, "bold"),
        )
        style.configure(
            "HeaderSubtitle.TLabel",
            background=self._colors["header"],
            foreground="#cbd5e1",
            font=("TkDefaultFont", 10),
        )
        style.configure(
            "Metric.TLabel",
            background=self._colors["card"],
            foreground=self._colors["text"],
            font=("TkDefaultFont", 12, "bold"),
        )
        style.configure(
            "Muted.TLabel",
            background=self._colors["bg"],
            foreground=self._colors["muted"],
            font=("TkDefaultFont", 9),
        )

        style.configure(
            "Accent.TButton",
            background=self._colors["accent"],
            foreground="#f8fafc",
            borderwidth=0,
            focusthickness=0,
            padding=(12, 7),
        )
        style.map(
            "Accent.TButton",
            background=[("active", self._colors["accent_hover"]), ("pressed", self._colors["accent_hover"])],
            foreground=[("disabled", "#d1d5db")],
        )

        style.configure(
            "Ghost.TButton",
            background=self._colors["card"],
            foreground=self._colors["text"],
            borderwidth=1,
            relief="solid",
            padding=(10, 7),
        )
        style.map(
            "Ghost.TButton",
            background=[("active", self._colors["notebook_bg"]), ("pressed", self._colors["notebook_bg"])],
        )

        style.configure(
            "Card.TLabelframe",
            background=self._colors["card"],
            bordercolor=self._colors["line"],
            relief="solid",
        )
        style.configure(
            "Card.TLabelframe.Label",
            background=self._colors["card"],
            foreground=self._colors["text"],
            font=("TkDefaultFont", 10, "bold"),
        )

    def toggle(self) -> str:
        """Switch between light and dark modes. Returns the new mode."""
        self.theme_mode = "dark" if self.theme_mode == "light" else "light"
        return self.theme_mode

    def set_mode(self, mode: str) -> None:
        """Explicitly set light or dark mode."""
        self.theme_mode = "dark" if mode == "dark" else "light"

    def set_palette(self, palette: str) -> None:
        """Update the chart color palette name."""
        if palette in PALETTES:
            self.palette = palette
