"""Standalone dialog windows used by the main GUI.

Extracted from gui.py to reduce file size and improve modularity.
"""

from __future__ import annotations

import calendar
import tkinter as tk
from datetime import date
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

from expenses_tracker.i18n import (
    month_name,
    normalize_language,
    tr,
)


class CalendarDialog(tk.Toplevel):
    """Calendar picker dialog."""

    def __init__(
        self,
        parent: tk.Misc,
        initial_date: date,
        on_select: Callable[[date], None],
        language: str,
        title: str,
    ) -> None:
        super().__init__(parent)
        self._language = normalize_language(language)
        self.title(title)
        self.resizable(False, False)
        self.transient(parent)  # type: ignore[call-overload]
        self.grab_set()

        self._on_select = on_select
        self._shown_year = initial_date.year
        self._shown_month = initial_date.month

        calendar.setfirstweekday(calendar.MONDAY)

        shell = ttk.Frame(self, padding=10)
        shell.pack(fill="both", expand=True)

        controls = ttk.Frame(shell)
        controls.pack(fill="x", pady=(0, 8))

        ttk.Button(
            controls,
            text=tr(self._language, "btn_previous"),
            width=3,
            command=self._prev_month,
        ).pack(side="left")
        self.month_label = ttk.Label(controls, anchor="center", font=("TkDefaultFont", 10, "bold"))
        self.month_label.pack(side="left", fill="x", expand=True)
        ttk.Button(
            controls,
            text=tr(self._language, "btn_next"),
            width=3,
            command=self._next_month,
        ).pack(side="right")

        self.days_frame = ttk.Frame(shell)
        self.days_frame.pack(fill="both", expand=True)

        footer = ttk.Frame(shell)
        footer.pack(fill="x", pady=(8, 0))
        ttk.Button(footer, text=tr(self._language, "btn_today"), command=self._select_today).pack(side="left")
        ttk.Button(footer, text=tr(self._language, "btn_close"), command=self.destroy).pack(side="right")

        self._render()

    def _render(self) -> None:
        for widget in self.days_frame.winfo_children():
            widget.destroy()

        self.month_label.config(text=f"{month_name(self._language, self._shown_month)} {self._shown_year}")

        weekdays = [
            tr(self._language, "weekday_mon"),
            tr(self._language, "weekday_tue"),
            tr(self._language, "weekday_wed"),
            tr(self._language, "weekday_thu"),
            tr(self._language, "weekday_fri"),
            tr(self._language, "weekday_sat"),
            tr(self._language, "weekday_sun"),
        ]
        for column, short_name in enumerate(weekdays):
            ttk.Label(self.days_frame, text=short_name, anchor="center").grid(
                row=0,
                column=column,
                padx=2,
                pady=(0, 4),
            )

        month_rows = calendar.monthcalendar(self._shown_year, self._shown_month)
        for row_index, week in enumerate(month_rows, start=1):
            for col_index, day_number in enumerate(week):
                if day_number == 0:
                    ttk.Label(self.days_frame, text=" ").grid(row=row_index, column=col_index, padx=2, pady=2)
                    continue

                day_button = ttk.Button(
                    self.days_frame,
                    text=str(day_number),
                    width=3,
                    command=lambda picked=day_number: self._select_day(picked),  # type: ignore[misc]
                )
                day_button.grid(row=row_index, column=col_index, padx=2, pady=2)

    def _prev_month(self) -> None:
        if self._shown_month == 1:
            self._shown_month = 12
            self._shown_year -= 1
        else:
            self._shown_month -= 1
        self._render()

    def _next_month(self) -> None:
        if self._shown_month == 12:
            self._shown_month = 1
            self._shown_year += 1
        else:
            self._shown_month += 1
        self._render()

    def _select_day(self, day_number: int) -> None:
        self._on_select(date(self._shown_year, self._shown_month, day_number))
        self.destroy()

    def _select_today(self) -> None:
        self._on_select(date.today())
        self.destroy()


class ChartTypeDialog(tk.Toplevel):
    """Dialog for selecting a chart type."""

    def __init__(self, parent: tk.Misc, language: str, options: list[tuple[str, str]]) -> None:
        super().__init__(parent)
        self._language = normalize_language(language)
        self.title(tr(self._language, "dialog_chart_title"))
        self.resizable(False, False)
        self.transient(parent)  # type: ignore[call-overload]
        self.grab_set()

        self.selected_kind: str | None = None
        self._label_to_kind = dict(options)

        frame = ttk.Frame(self, padding=12)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text=tr(self._language, "dialog_chart_prompt")).pack(anchor="w", pady=(0, 6))

        default_label = options[0][0]
        self.chart_type_label_var = tk.StringVar(value=default_label)
        chart_box = ttk.Combobox(
            frame,
            textvariable=self.chart_type_label_var,
            values=[label for label, _kind in options],
            state="readonly",
            width=30,
        )
        chart_box.pack(fill="x")

        button_row = ttk.Frame(frame)
        button_row.pack(fill="x", pady=(10, 0))
        ttk.Button(button_row, text=tr(self._language, "btn_cancel"), style="Ghost.TButton", command=self._cancel).pack(
            side="right", padx=(6, 0)
        )
        ttk.Button(
            button_row,
            text=tr(self._language, "btn_generate"),
            style="Accent.TButton",
            command=self._accept,
        ).pack(side="right")

        self.bind("<Return>", lambda _event: self._accept())
        self.bind("<Escape>", lambda _event: self._cancel())

        chart_box.focus_set()

    def _accept(self) -> None:
        label = self.chart_type_label_var.get().strip()
        self.selected_kind = self._label_to_kind.get(label)
        self.destroy()

    def _cancel(self) -> None:
        self.selected_kind = None
        self.destroy()


class LockScreenDialog(tk.Toplevel):
    """PIN lock dialog for setting or verifying a PIN."""

    def __init__(
        self,
        parent: tk.Misc,
        language: str,
        mode: str = "unlock",
        current_hash: str | None = None,
    ) -> None:
        super().__init__(parent)
        self._language = normalize_language(language)
        self._mode = mode
        self._current_hash = current_hash
        self.success = False
        self.new_hash: str | None = None

        if mode == "set":
            self.title(tr(self._language, "lock_set_pin_title"))
        else:
            self.title(tr(self._language, "lock_title"))

        self.resizable(False, False)
        self.transient(parent)  # type: ignore[call-overload]
        self.grab_set()
        self.configure(width=360, height=220)

        frame = ttk.Frame(self, padding=24, style="App.TFrame")
        frame.pack(fill="both", expand=True)

        if mode == "set":
            ttk.Label(frame, text=tr(self._language, "lock_set_pin_subtitle"), wraplength=280).pack(
                anchor="w", pady=(0, 12)
            )
            ttk.Label(frame, text=tr(self._language, "lock_set_pin"), style="HeaderSubtitle.TLabel").pack(
                anchor="w", pady=(0, 4)
            )
        else:
            ttk.Label(frame, text=tr(self._language, "lock_subtitle"), wraplength=280).pack(anchor="w", pady=(0, 12))

        self.pin_var = tk.StringVar()
        pin_entry = ttk.Entry(frame, textvariable=self.pin_var, show="\u2022", width=24)
        pin_entry.pack(fill="x", pady=(0, 8))
        pin_entry.focus_set()

        self.confirm_var = tk.StringVar()
        if mode == "set":
            ttk.Label(frame, text=tr(self._language, "lock_confirm_pin")).pack(anchor="w", pady=(0, 4))
            confirm_entry = ttk.Entry(frame, textvariable=self.confirm_var, show="\u2022", width=24)
            confirm_entry.pack(fill="x", pady=(0, 12))
        else:
            ttk.Frame(frame, height=12).pack()

        button_row = ttk.Frame(frame)
        button_row.pack(fill="x")
        ttk.Button(button_row, text=tr(self._language, "btn_cancel"), style="Ghost.TButton", command=self._cancel).pack(
            side="right", padx=(6, 0)
        )
        btn_text = tr(self._language, "lock_set_pin") if mode == "set" else tr(self._language, "lock_unlock")
        ttk.Button(button_row, text=btn_text, style="Accent.TButton", command=self._accept).pack(side="right")

        self.bind("<Return>", lambda _e: self._accept())
        self.bind("<Escape>", lambda _e: self._cancel())

        self._center_on_parent(parent)

    def _center_on_parent(self, parent: tk.Misc) -> None:
        self.update_idletasks()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        px = parent.winfo_x()
        py = parent.winfo_y()
        w = self.winfo_width()
        h = self.winfo_height()
        x = px + (pw - w) // 2
        y = py + (ph - h) // 2
        self.geometry(f"+{x}+{y}")

    def _accept(self) -> None:
        from expenses_tracker.security import KeyDerivation, PinRateLimiter, PinValidator, verify_password

        pin = self.pin_var.get()

        if self._mode == "set":
            if not pin:
                return
            confirm = self.confirm_var.get()
            if pin != confirm:
                messagebox.showwarning(
                    tr(self._language, "error_generic"),
                    tr(self._language, "lock_pins_dont_match"),
                    parent=self,
                )
                self.pin_var.set("")
                self.confirm_var.set("")
                return
            is_valid, error_key = PinValidator.validate(pin)
            if not is_valid:
                messagebox.showwarning(
                    tr(self._language, "error_generic"),
                    tr(self._language, error_key),
                    parent=self,
                )
                self.pin_var.set("")
                self.confirm_var.set("")
                return
            self.new_hash = KeyDerivation.hash_password(pin)
            PinRateLimiter.reset()
            self.success = True
            self.destroy()
        else:
            remaining = PinRateLimiter.remaining_cooldown()
            if remaining > 0:
                messagebox.showwarning(
                    tr(self._language, "error_generic"),
                    tr(self._language, "pin_too_many_attempts", seconds=remaining),
                    parent=self,
                )
                return
            if PinRateLimiter.is_locked_out():
                messagebox.showwarning(
                    tr(self._language, "error_generic"),
                    tr(self._language, "pin_locked_out"),
                    parent=self,
                )
                self.pin_var.set("")
                return
            if not pin:
                return
            if self._current_hash and verify_password(pin, self._current_hash):
                PinRateLimiter.reset()
                self.success = True
                self.destroy()
            else:
                PinRateLimiter.record_failure()
                remaining = PinRateLimiter.remaining_cooldown()
                if PinRateLimiter.is_locked_out():
                    messagebox.showerror(
                        tr(self._language, "error_generic"),
                        tr(self._language, "pin_locked_out"),
                        parent=self,
                    )
                elif remaining > 0:
                    messagebox.showwarning(
                        tr(self._language, "error_generic"),
                        tr(self._language, "pin_too_many_attempts", seconds=remaining),
                        parent=self,
                    )
                else:
                    messagebox.showwarning(
                        tr(self._language, "error_generic"),
                        tr(self._language, "lock_wrong_pin"),
                        parent=self,
                    )
                self.pin_var.set("")
                self.focus_set()

    def _cancel(self) -> None:
        self.success = False
        self.destroy()
