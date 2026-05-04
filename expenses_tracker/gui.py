from __future__ import annotations

import argparse
import calendar
from datetime import date, timedelta
import json
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

import ttkbootstrap as ttkb
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure

from expenses_tracker.automation import ReportScheduler
from expenses_tracker.automation_dialog import AutomationDialog
from expenses_tracker.chart_viewer import ChartViewerDialog
from expenses_tracker.cloud_sync_dialog import CloudSyncDialog
from expenses_tracker.charts import generate_charts, generate_budget_chart, get_palette, PALETTES
from expenses_tracker.db import ExpenseDatabase, TransactionInput
from expenses_tracker.exporters import (
    export_reports,
    _compute_category_rows_from_transactions,
    _compute_month_rows_from_transactions,
)
from expenses_tracker.i18n import (
    format_date,
    format_number,
    is_rtl,
    language_label,
    list_languages,
    month_name,
    normalize_language,
    reload_translations,
    reshape_for_rtl,
    tr,
)
from expenses_tracker.security import (
    apply_private_permissions,
    AuditLog as FileAuditLog,
    BackupManager,
    LockManager,
    SQLCipherManager,
)


INCOME_CATEGORY_KEYS = [
    "salary",
    "business_income",
    "freelance",
    "interest",
    "dividends",
    "sale",
    "refund",
    "gift",
    "extra_income",
    "investment",
    "other",
]

EXPENSE_CATEGORY_KEYS = [
    "food",
    "electricity",
    "water",
    "gas",
    "transport",
    "rent",
    "internet",
    "phone",
    "health",
    "education",
    "leisure",
    "taxes",
    "home",
    "pets",
    "subscriptions",
    "investment",
    "other",
]


def category_options_for_type(language: str, type_key: str) -> list[str]:
    keys = INCOME_CATEGORY_KEYS if type_key == "income" else EXPENSE_CATEGORY_KEYS
    return [tr(language, f"category_{key}") for key in keys]


def filter_transaction_rows(
    rows: list[dict[str, object]],
    search: str,
    selected_type_db: str,
    selected_category: str,
    all_label: str,
    date_from: date | None,
    date_to: date | None,
    type_db_to_display: dict[str, str],
) -> list[dict[str, object]]:
    normalized_search = search.strip().lower()
    normalized_category = selected_category.strip().lower()
    normalized_all_label = all_label.strip().lower()

    filtered: list[dict[str, object]] = []
    for row in rows:
        row_type = str(row["transaction_type"]).lower()
        row_category = str(row["category"]).lower()
        row_date = safe_parse_date(str(row["transaction_date"]))

        if selected_type_db and row_type != selected_type_db:
            continue
        if normalized_category != normalized_all_label and row_category != normalized_category:
            continue
        if date_from and row_date and row_date < date_from:
            continue
        if date_to and row_date and row_date > date_to:
            continue

        if normalized_search:
            searchable = " ".join(
                [
                    str(row["id"]),
                    str(row["transaction_date"]),
                    type_db_to_display.get(str(row["transaction_type"]), str(row["transaction_type"])),
                    str(row["category"]),
                    str(row["amount"]),
                    str(row["description"]),
                ]
            ).lower()
            if normalized_search not in searchable:
                continue

        filtered.append(row)

    return filtered


def safe_parse_date(raw_value: str) -> date | None:
    value = raw_value.strip()
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


class CalendarDialog(tk.Toplevel):
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
        self.transient(parent)
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
                    command=lambda picked=day_number: self._select_day(picked),
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
    def __init__(self, parent: tk.Misc, language: str, options: list[tuple[str, str]]) -> None:
        super().__init__(parent)
        self._language = normalize_language(language)
        self.title(tr(self._language, "dialog_chart_title"))
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.selected_kind: str | None = None
        self._label_to_kind = {label: kind for label, kind in options}

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
        ttk.Button(button_row, text=tr(self._language, "btn_generate"), style="Accent.TButton", command=self._accept).pack(
            side="right"
        )

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
        self.transient(parent)
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
            ttk.Label(frame, text=tr(self._language, "lock_subtitle"), wraplength=280).pack(
                anchor="w", pady=(0, 12)
            )

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
        from expenses_tracker.security import verify_password, KeyDerivation

        pin = self.pin_var.get()
        if not pin:
            return

        if self._mode == "set":
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
            self.new_hash = KeyDerivation.hash_password(pin)
            self.success = True
            self.destroy()
        else:

            if self._current_hash and verify_password(pin, self._current_hash):
                self.success = True
                self.destroy()
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


class ExpensesApp(tk.Tk):
    def __init__(self, db_path: str = "data/expenses.db", initial_language: str | None = None, cipher_key: str | None = None) -> None:
        super().__init__()

        self.state_file = Path("data/ui_state.json")
        self._state = self._read_ui_state()
        self.language = normalize_language(initial_language or str(self._state.get("language", "en")))

        self.geometry("1100x720")
        self.minsize(960, 640)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        saved_mode = str(self._state.get("theme_mode", "light"))
        self.theme_mode = saved_mode if saved_mode in {"light", "dark"} else "light"
        self.palette = str(self._state.get("palette", "default"))
        if self.palette not in PALETTES:
            self.palette = "default"
        self._setup_theme()

        self.database = ExpenseDatabase(db_path, cipher_key=cipher_key)
        self.database.initialize()

        self.scheduler = ReportScheduler(
            database=self.database,
            config_getter=self.database.get_automation_config,
            language=self.language,
        )
        self.scheduler.start()
        self.scheduler.update_schedule()

        self.search_var = tk.StringVar(value=str(self._state.get("search", "")))
        self.filter_type_key = self._normalize_filter_type_key(str(self._state.get("filter_type_key", "all")))
        self.filter_category_var = tk.StringVar(value=str(self._state.get("filter_category", "")))
        self.filter_from_var = tk.StringVar(value=str(self._state.get("filter_from", "")))
        self.filter_to_var = tk.StringVar(value=str(self._state.get("filter_to", "")))
        self.filtered_count_var = tk.StringVar(value=tr(self.language, "showing_rows", filtered=0, total=0))

        self.sort_column = str(self._state.get("sort_column", "date"))
        self.sort_desc = bool(self._state.get("sort_desc", True))

        self.register_type_key = self._normalize_register_type_key(str(self._state.get("register_type_key", "expense")))
        self.type_var = tk.StringVar()
        self.amount_var = tk.StringVar()
        self.category_var = tk.StringVar()
        self.date_var = tk.StringVar(value=date.today().isoformat())
        self.editing_transaction_id: int | None = None
        self.save_button_var = tk.StringVar()

        # Pagination state
        self._page_size = 100
        self._current_page = 0
        self._total_pages = 1

        # Embedded chart canvases
        self._chart_canvas_category: FigureCanvasTkAgg | None = None
        self._chart_canvas_month: FigureCanvasTkAgg | None = None
        self._chart_toolbar_category: NavigationToolbar2Tk | None = None
        self._chart_toolbar_month: NavigationToolbar2Tk | None = None

        # Chart series visibility toggles
        self._show_income = tk.BooleanVar(value=True)
        self._show_expense = tk.BooleanVar(value=True)
        self._show_balance = tk.BooleanVar(value=True)

        # Validation indicator labels
        self._amount_indicator: ttk.Label | None = None
        self._date_indicator: ttk.Label | None = None
        self._category_indicator: ttk.Label | None = None

        self.balance_var = tk.StringVar(value=tr(self.language, "balance_label", amount=format_number(self.language, 0.0)))
        self.income_var = tk.StringVar(value=tr(self.language, "income_total_label", amount=format_number(self.language, 0.0)))
        self.expense_var = tk.StringVar(value=tr(self.language, "expense_total_label", amount=format_number(self.language, 0.0)))
        self.filter_type_var = tk.StringVar()
        self.language_var = tk.StringVar()
        self._last_totals = {"balance": 0.0, "income": 0.0, "expense": 0.0}

        self._container: ttk.Frame | None = None
        self._notebook: ttk.Notebook | None = None
        self._tab_register: ttk.Frame | None = None
        self._sync_language_maps()
        self._build_ui()
        self._setup_shortcuts()
        self._refresh_all()

    def _sync_language_maps(self) -> None:
        self._language_display_to_code = {language_label(code): code for code, _name in list_languages()}
        self._type_display_to_db = {
            tr(self.language, "type_income"): "income",
            tr(self.language, "type_expense"): "expense",
        }
        self._type_db_to_display = {value: key for key, value in self._type_display_to_db.items()}

        self._filter_display_to_key = {
            tr(self.language, "type_all"): "all",
            tr(self.language, "type_income_plural"): "income",
            tr(self.language, "type_expense_plural"): "expense",
        }
        self._filter_key_to_display = {value: key for key, value in self._filter_display_to_key.items()}
        self._all_label = tr(self.language, "type_all")

        self._column_titles = {
            "id": tr(self.language, "col_id"),
            "date": tr(self.language, "col_date"),
            "type": tr(self.language, "col_type"),
            "category": tr(self.language, "col_category"),
            "amount": tr(self.language, "col_amount"),
            "description": tr(self.language, "col_description"),
        }

        self.language_var.set(language_label(self.language))
        self.type_var.set(self._type_db_to_display.get(self.register_type_key, tr(self.language, "type_expense")))
        self.filter_type_var.set(self._filter_key_to_display.get(self.filter_type_key, self._all_label))
        self.balance_var.set(tr(self.language, "balance_label", amount=format_number(self.language, self._last_totals["balance"])))
        self.income_var.set(tr(self.language, "income_total_label", amount=format_number(self.language, self._last_totals["income"])))
        self.expense_var.set(tr(self.language, "expense_total_label", amount=format_number(self.language, self._last_totals["expense"])))
        self._update_save_button_text()

    def _chart_type_options(self) -> list[tuple[str, str]]:
        return [
            (tr(self.language, "chart_option_all"), "all"),
            (tr(self.language, "chart_option_bar"), "bar"),
            (tr(self.language, "chart_option_line"), "line"),
            (tr(self.language, "chart_option_pie"), "pie"),
            (tr(self.language, "chart_option_scatter"), "scatter"),
            (tr(self.language, "chart_option_bar3d"), "bar3d"),
            (tr(self.language, "chart_option_forecast"), "forecast"),
            (tr(self.language, "chart_option_sankey"), "sankey"),
            (tr(self.language, "chart_option_budget"), "budget"),
        ]

    def _build_ui(self) -> None:
        if self._container is not None:
            self._container.destroy()

        self.title(tr(self.language, "app_title"))
        self._container = ttk.Frame(self, padding=16, style="App.TFrame")
        self._container.pack(fill="both", expand=True)

        header = ttk.Frame(self._container, padding=14, style="Header.TFrame")
        header.pack(fill="x", pady=(0, 8))

        heading_side = "right" if is_rtl(self.language) else "left"
        buttons_side = "left" if is_rtl(self.language) else "right"
        heading_anchor = "e" if is_rtl(self.language) else "w"

        heading = ttk.Frame(header, style="Header.TFrame")
        heading.pack(side=heading_side, fill="x", expand=True)

        ttk.Label(heading, text=self._rtl_text(tr(self.language, "header_title")), style="HeaderTitle.TLabel").pack(anchor=heading_anchor)
        ttk.Label(
            heading,
            text=self._rtl_text(tr(self.language, "header_subtitle")),
            style="HeaderSubtitle.TLabel",
        ).pack(anchor=heading_anchor, pady=(2, 0))

        buttons = ttk.Frame(header, style="Header.TFrame")
        buttons.pack(side=buttons_side)

        ttk.Label(buttons, text=self._rtl_text(tr(self.language, "label_language")), style="HeaderSubtitle.TLabel").pack(
            side="left", padx=(0, 6)
        )
        language_box = ttk.Combobox(
            buttons,
            textvariable=self.language_var,
            values=list(self._language_display_to_code.keys()),
            state="readonly",
            width=16,
        )
        language_box.pack(side="left", padx=3)
        language_box.bind("<<ComboboxSelected>>", lambda _event: self._on_language_change())
        self._apply_rtl_to_widget(language_box)

        self.theme_button = ttk.Button(buttons, style="Ghost.TButton", command=self._toggle_theme)
        self.theme_button.pack(side="left", padx=3)
        self._update_theme_button_text()

        self.palette_var = tk.StringVar(value=self.palette)
        palette_box = ttk.Combobox(
            buttons,
            textvariable=self.palette_var,
            values=list(PALETTES.keys()),
            state="readonly",
            width=12,
        )
        palette_box.pack(side="left", padx=3)
        palette_box.bind("<<ComboboxSelected>>", lambda _event: self._on_palette_change())
        self._apply_rtl_to_widget(palette_box)

        btn_refresh = ttk.Button(buttons, text=tr(self.language, "btn_refresh"), style="Ghost.TButton", command=self._refresh_all)
        btn_refresh.pack(side="left", padx=3)
        self._apply_rtl_to_widget(btn_refresh)

        btn_charts = ttk.Button(
            buttons,
            text=tr(self.language, "btn_make_charts"),
            style="Ghost.TButton",
            command=self._generate_charts,
        )
        btn_charts.pack(side="left", padx=3)
        self._apply_rtl_to_widget(btn_charts)

        btn_automation = ttk.Button(
            buttons,
            text=tr(self.language, "btn_automation"),
            style="Ghost.TButton",
            command=self._open_automation_dialog,
        )
        btn_automation.pack(side="left", padx=3)
        self._apply_rtl_to_widget(btn_automation)

        lock_label = tr(self.language, "btn_set_lock") if not LockManager.is_lock_set() else tr(self.language, "btn_remove_lock")
        btn_lock = ttk.Button(buttons, text=lock_label, style="Ghost.TButton", command=self._toggle_lock)
        btn_lock.pack(side="left", padx=3)
        self._apply_rtl_to_widget(btn_lock)

        btn_backup = ttk.Button(buttons, text=tr(self.language, "btn_backup"), style="Ghost.TButton", command=self._create_backup)
        btn_backup.pack(side="left", padx=3)
        self._apply_rtl_to_widget(btn_backup)

        btn_cloud = ttk.Button(
            buttons,
            text=tr(self.language, "btn_cloud_sync"),
            style="Ghost.TButton",
            command=self._open_cloud_sync_dialog,
        )
        btn_cloud.pack(side="left", padx=3)
        self._apply_rtl_to_widget(btn_cloud)

        if not SQLCipherManager.is_encrypted_db(Path(self.database.db_path)):
            btn_encrypt = ttk.Button(
                buttons,
                text=tr(self.language, "btn_encrypt_db"),
                style="Ghost.TButton",
                command=self._encrypt_database,
            )
            btn_encrypt.pack(side="left", padx=3)
            self._apply_rtl_to_widget(btn_encrypt)

        self.export_format_var = tk.StringVar(value="excel")
        export_format_box = ttk.Combobox(
            buttons,
            textvariable=self.export_format_var,
            values=["excel", "csv", "pdf", "json", "yaml", "html", "monthly_pdf", "all"],
            state="readonly",
            width=12,
        )
        export_format_box.pack(side="left", padx=3)
        self._apply_rtl_to_widget(export_format_box)

        btn_export = ttk.Button(
            buttons,
            text=tr(self.language, "btn_export"),
            style="Ghost.TButton",
            command=lambda: self._export(self.export_format_var.get()),
        )
        btn_export.pack(side="left", padx=3)
        self._apply_rtl_to_widget(btn_export)

        btn_quick = ttk.Button(
            buttons,
            text=tr(self.language, "btn_quick_export"),
            style="Accent.TButton",
            command=self._quick_export,
        )
        btn_quick.pack(side="left", padx=3)
        self._apply_rtl_to_widget(btn_quick)

        metrics_row = ttk.Frame(self._container, style="App.TFrame")
        metrics_row.pack(fill="x", pady=(0, 8))
        self.balance_label = self._build_metric_card(metrics_row, self.balance_var, padx=(0, 6))
        self.income_label = self._build_metric_card(metrics_row, self.income_var, padx=(0, 6))
        self.expense_label = self._build_metric_card(metrics_row, self.expense_var, padx=(0, 0))

        notebook_shell = ttk.Frame(self._container, style="Card.TFrame", padding=6)
        notebook_shell.pack(fill="both", expand=True)

        notebook = ttk.Notebook(notebook_shell)
        notebook.pack(fill="both", expand=True)
        self._notebook = notebook

        tab_register = ttk.Frame(notebook, padding=12, style="App.TFrame")
        tab_transactions = ttk.Frame(notebook, padding=12, style="App.TFrame")
        tab_stats = ttk.Frame(notebook, padding=12, style="App.TFrame")

        notebook.add(tab_register, text=tr(self.language, "tab_register"))
        notebook.add(tab_transactions, text=tr(self.language, "tab_transactions"))
        notebook.add(tab_stats, text=tr(self.language, "tab_stats"))
        self._tab_register = tab_register

        self._build_register_tab(tab_register)
        self._build_transactions_tab(tab_transactions)
        self._build_stats_tab(tab_stats)

    def _rtl_text(self, text: str) -> str:
        if is_rtl(self.language):
            return reshape_for_rtl(text)
        return text

    def _apply_rtl_to_widget(self, widget: ttk.Widget, text: str | None = None) -> None:
        """Apply RTL reshaping and right alignment to supported widgets."""
        if not is_rtl(self.language):
            return
        if text is not None:
            reshaped = reshape_for_rtl(text)
            if isinstance(widget, (ttk.Label, ttk.Button)):
                widget.configure(text=reshaped)
        if isinstance(widget, (ttk.Entry, ttk.Combobox)):
            widget.configure(justify="right")
        if isinstance(widget, ttk.Label):
            widget.configure(anchor="e")
        if isinstance(widget, ttk.Button):
            widget.configure(width=len(text or widget.cget("text")) + 4)

    def _build_metric_card(
        self,
        parent: ttk.Frame,
        text_var: tk.StringVar,
        padx: tuple[int, int],
    ) -> ttk.Label:
        card = ttk.Frame(parent, style="Card.TFrame", padding=(14, 10))
        card.pack(side="left", fill="x", expand=True, padx=padx)
        anchor = "e" if is_rtl(self.language) else "w"
        label = ttk.Label(card, textvariable=text_var, style="Metric.TLabel", anchor=anchor)
        label.pack(anchor=anchor)
        return label

    def _build_register_tab(self, parent: ttk.Frame) -> None:
        form = ttk.Frame(parent, style="Card.TFrame", padding=12)
        form.pack(fill="x", padx=8, pady=6)

        label_sticky = "e" if is_rtl(self.language) else "w"

        lbl_type = ttk.Label(form, text=self._rtl_text(tr(self.language, "label_type")))
        lbl_type.grid(row=0, column=0, sticky=label_sticky, pady=4)
        lbl_amount = ttk.Label(form, text=self._rtl_text(tr(self.language, "label_amount")))
        lbl_amount.grid(row=0, column=1, sticky=label_sticky, pady=4)
        lbl_category = ttk.Label(form, text=self._rtl_text(tr(self.language, "label_category")))
        lbl_category.grid(row=0, column=2, sticky=label_sticky, pady=4)
        lbl_date = ttk.Label(form, text=self._rtl_text(tr(self.language, "label_date")))
        lbl_date.grid(row=0, column=3, sticky=label_sticky, pady=4)

        type_box = ttk.Combobox(
            form,
            textvariable=self.type_var,
            values=list(self._type_display_to_db.keys()),
            state="readonly",
            width=12,
        )
        type_box.grid(row=1, column=0, sticky="we", padx=(0, 10), pady=(0, 2))
        type_box.bind("<<ComboboxSelected>>", lambda _event: self._on_register_type_changed())
        self._apply_rtl_to_widget(type_box)

        amount_field = ttk.Frame(form)
        amount_field.grid(row=1, column=1, sticky="we", padx=(0, 10), pady=(0, 2))
        self.amount_entry = ttk.Entry(amount_field, textvariable=self.amount_var, width=16, justify="right" if is_rtl(self.language) else "left")
        self.amount_entry.pack(side="left", fill="x", expand=True)
        self._amount_indicator = ttk.Label(amount_field, text="", width=2)
        self._amount_indicator.pack(side="left", padx=(4, 0))

        cat_field = ttk.Frame(form)
        cat_field.grid(row=1, column=2, sticky="we", padx=(0, 10), pady=(0, 2))
        self.category_box = ttk.Combobox(
            cat_field,
            textvariable=self.category_var,
            values=[],
            state="normal",
            width=20,
        )
        self.category_box.pack(side="left", fill="x", expand=True)
        self._apply_rtl_to_widget(self.category_box)
        self._category_indicator = ttk.Label(cat_field, text="", width=2)
        self._category_indicator.pack(side="left", padx=(4, 0))

        date_field = ttk.Frame(form)
        date_field.grid(row=1, column=3, sticky="we", padx=(0, 10), pady=(0, 2))
        self.date_entry = ttk.Entry(date_field, textvariable=self.date_var, width=18, justify="right" if is_rtl(self.language) else "left")
        self.date_entry.pack(side="left", fill="x", expand=True)
        self._date_indicator = ttk.Label(date_field, text="", width=2)
        self._date_indicator.pack(side="left", padx=(4, 0))
        btn_calendar = ttk.Button(
            date_field,
            text="...",
            width=3,
            command=lambda: self._open_calendar_for_var(
                self.date_var,
                tr(self.language, "dialog_select_date"),
            ),
        )
        btn_calendar.pack(side="left", padx=(4, 0))

        lbl_description = ttk.Label(form, text=self._rtl_text(tr(self.language, "label_description")))
        lbl_description.grid(row=2, column=0, sticky=label_sticky, pady=4)
        self.description_text = tk.Text(
            form,
            width=80,
            height=4,
            relief="solid",
            borderwidth=1,
            background=self._colors["input_bg"],
            foreground=self._colors["text"],
            insertbackground=self._colors["text"],
            highlightthickness=0,
            padx=8,
            pady=6,
        )
        if is_rtl(self.language):
            self.description_text.tag_configure("rtl", justify="right")
            self.description_text.insert("1.0", "")
            self.description_text.tag_add("rtl", "1.0", "end")
        self.description_text.grid(row=3, column=0, columnspan=4, sticky="we", pady=(0, 8))

        actions = ttk.Frame(form, style="Card.TFrame")
        actions_sticky = "w" if is_rtl(self.language) else "e"
        actions.grid(row=4, column=0, columnspan=4, sticky=actions_sticky)

        btn_save = ttk.Button(
            actions,
            textvariable=self.save_button_var,
            style="Accent.TButton",
            command=self._save_transaction,
        )
        btn_save.pack(side="left", padx=4)
        self._apply_rtl_to_widget(btn_save)

        btn_clear = ttk.Button(
            actions,
            text=tr(self.language, "btn_clear"),
            style="Ghost.TButton",
            command=self._clear_form,
        )
        btn_clear.pack(side="left", padx=4)
        self._apply_rtl_to_widget(btn_clear)

        for column_index in range(4):
            form.columnconfigure(column_index, weight=1)

        self._on_register_type_changed()
        self._update_save_button_text()

        self.amount_var.trace_add("write", self._validate_amount)
        self.date_var.trace_add("write", self._validate_date)
        self.category_var.trace_add("write", self._validate_category)

    def _build_transactions_tab(self, parent: ttk.Frame) -> None:
        filters = ttk.LabelFrame(parent, text=self._rtl_text(tr(self.language, "filters_title")), padding=10, style="Card.TLabelframe")
        filters.pack(fill="x", padx=0, pady=(0, 8))

        label_sticky = "e" if is_rtl(self.language) else "w"

        ttk.Label(filters, text=self._rtl_text(tr(self.language, "label_search"))).grid(row=0, column=0, sticky=label_sticky)
        ttk.Label(filters, text=self._rtl_text(tr(self.language, "label_type"))).grid(row=0, column=1, sticky=label_sticky)
        ttk.Label(filters, text=self._rtl_text(tr(self.language, "label_category"))).grid(row=0, column=2, sticky=label_sticky)
        ttk.Label(filters, text=self._rtl_text(tr(self.language, "label_from"))).grid(row=0, column=3, sticky=label_sticky)
        ttk.Label(filters, text=self._rtl_text(tr(self.language, "label_to"))).grid(row=0, column=4, sticky=label_sticky)

        search_entry = ttk.Entry(filters, textvariable=self.search_var, justify="right" if is_rtl(self.language) else "left")
        search_entry.grid(row=1, column=0, sticky="we", padx=(0, 8), pady=(2, 0))

        type_box = ttk.Combobox(
            filters,
            textvariable=self.filter_type_var,
            values=list(self._filter_display_to_key.keys()),
            state="readonly",
            width=10,
        )
        type_box.grid(row=1, column=1, sticky="we", padx=(0, 8), pady=(2, 0))
        type_box.bind("<<ComboboxSelected>>", lambda _event: self._on_filter_change())
        self._apply_rtl_to_widget(type_box)

        self.category_filter_box = ttk.Combobox(
            filters,
            textvariable=self.filter_category_var,
            values=[self._all_label],
            state="readonly",
            width=18,
        )
        self.category_filter_box.grid(row=1, column=2, sticky="we", padx=(0, 8), pady=(2, 0))
        self.category_filter_box.bind("<<ComboboxSelected>>", lambda _event: self._on_filter_change())
        self._apply_rtl_to_widget(self.category_filter_box)

        from_field = ttk.Frame(filters)
        from_field.grid(row=1, column=3, sticky="we", padx=(0, 8), pady=(2, 0))
        from_entry = ttk.Entry(from_field, textvariable=self.filter_from_var, width=14, justify="right" if is_rtl(self.language) else "left")
        from_entry.pack(side="left", fill="x", expand=True)
        from_entry.bind("<KeyRelease>", lambda _event: self._on_filter_change())
        ttk.Button(
            from_field,
            text="...",
            width=3,
            command=lambda: self._open_calendar_for_var(
                self.filter_from_var,
                tr(self.language, "label_from"),
                on_change=self._on_filter_change,
            ),
        ).pack(side="left", padx=(4, 0))

        to_field = ttk.Frame(filters)
        to_field.grid(row=1, column=4, sticky="we", padx=(0, 8), pady=(2, 0))
        to_entry = ttk.Entry(to_field, textvariable=self.filter_to_var, width=14, justify="right" if is_rtl(self.language) else "left")
        to_entry.pack(side="left", fill="x", expand=True)
        to_entry.bind("<KeyRelease>", lambda _event: self._on_filter_change())
        ttk.Button(
            to_field,
            text="...",
            width=3,
            command=lambda: self._open_calendar_for_var(
                self.filter_to_var,
                tr(self.language, "label_to"),
                on_change=self._on_filter_change,
            ),
        ).pack(side="left", padx=(4, 0))

        filter_actions = ttk.Frame(filters, style="Card.TFrame")
        filter_actions.grid(row=1, column=5, sticky="e")
        btn_apply = ttk.Button(
            filter_actions,
            text=tr(self.language, "btn_apply"),
            style="Accent.TButton",
            command=self._load_transactions,
        )
        btn_apply.pack(side="left", padx=3)
        self._apply_rtl_to_widget(btn_apply)

        btn_clear_filters = ttk.Button(
            filter_actions,
            text=tr(self.language, "btn_clear"),
            style="Ghost.TButton",
            command=self._clear_filters,
        )
        btn_clear_filters.pack(side="left", padx=3)
        self._apply_rtl_to_widget(btn_clear_filters)

        quick_ranges = ttk.Frame(filters, style="Card.TFrame")
        quick_ranges.grid(row=2, column=0, columnspan=6, sticky=label_sticky, pady=(8, 0))
        ttk.Label(quick_ranges, text=self._rtl_text(tr(self.language, "label_quick_dates"))).pack(side="left", padx=(0, 6))
        for preset in ["btn_today", "btn_week", "btn_month", "btn_year", "btn_all"]:
            btn = ttk.Button(
                quick_ranges,
                text=tr(self.language, preset),
                style="Ghost.TButton",
                command=lambda p=preset: self._apply_date_preset(p.replace("btn_", "")),
            )
            btn.pack(side="left", padx=2)
            self._apply_rtl_to_widget(btn)

        for column_index in range(5):
            filters.columnconfigure(column_index, weight=1)

        self.search_var.trace_add("write", self._on_search_change)

        self.search_entry = search_entry

        actions_row = ttk.Frame(parent, style="App.TFrame")
        actions_row.pack(fill="x", pady=(0, 6))
        btn_load = ttk.Button(
            actions_row,
            text=tr(self.language, "btn_load_form"),
            style="Ghost.TButton",
            command=self._load_selected_into_form,
        )
        btn_load.pack(side="left", padx=(0, 6))
        self._apply_rtl_to_widget(btn_load)

        btn_delete = ttk.Button(
            actions_row,
            text=tr(self.language, "btn_delete"),
            style="Ghost.TButton",
            command=self._delete_selected_transaction,
        )
        btn_delete.pack(side="left")
        self._apply_rtl_to_widget(btn_delete)

        count_side = "left" if is_rtl(self.language) else "right"
        ttk.Label(actions_row, textvariable=self.filtered_count_var, style="Muted.TLabel").pack(side=count_side)

        tree_area = ttk.Frame(parent, style="Card.TFrame", padding=8)
        tree_area.pack(fill="both", expand=True)

        columns = ("id", "date", "type", "category", "amount", "description")
        self.transactions_tree = ttk.Treeview(tree_area, columns=columns, show="headings", height=20)
        self.transactions_tree.pack(fill="both", expand=True, side="left")

        text_anchor = "e" if is_rtl(self.language) else "w"
        for column_name, title in self._column_titles.items():
            self.transactions_tree.heading(
                column_name,
                text=self._rtl_text(title),
                command=lambda selected=column_name: self._on_sort_change(selected),
            )

        self.transactions_tree.column("id", width=60, anchor="center")
        self.transactions_tree.column("date", width=120, anchor="center")
        self.transactions_tree.column("type", width=100, anchor="center")
        self.transactions_tree.column("category", width=160, anchor=text_anchor)
        self.transactions_tree.column("amount", width=100, anchor="e")
        self.transactions_tree.column("description", width=420, anchor=text_anchor)

        self.transactions_tree.tag_configure("income", foreground=self._colors["positive"])
        self.transactions_tree.tag_configure("expense", foreground=self._colors["negative"])
        self.transactions_tree.bind("<Double-1>", lambda _event: self._load_selected_into_form())

        scrollbar = ttk.Scrollbar(tree_area, orient="vertical", command=self.transactions_tree.yview)
        scrollbar.pack(fill="y", side="right")
        self.transactions_tree.configure(yscrollcommand=scrollbar.set)
        self._refresh_sort_headers()

        pagination = ttk.Frame(parent, style="App.TFrame")
        pagination.pack(fill="x", pady=(6, 0))
        self._btn_prev = ttk.Button(
            pagination,
            text="<",
            width=3,
            command=lambda: self._go_to_page(-1),
        )
        self._btn_prev.pack(side="left", padx=(0, 6))
        self._page_label_var = tk.StringVar(value="1 / 1")
        ttk.Label(pagination, textvariable=self._page_label_var, style="Muted.TLabel").pack(side="left")
        self._btn_next = ttk.Button(
            pagination,
            text=">",
            width=3,
            command=lambda: self._go_to_page(1),
        )
        self._btn_next.pack(side="left", padx=(6, 0))

    def _build_stats_tab(self, parent: ttk.Frame) -> None:
        top = ttk.Frame(parent, style="App.TFrame")
        top.pack(fill="both", expand=True)

        left = ttk.Frame(top, style="App.TFrame")
        right = ttk.Frame(top, style="App.TFrame")
        left.pack(fill="both", expand=True, side="left", padx=(0, 5))
        right.pack(fill="both", expand=True, side="left", padx=(5, 0))

        left_tree = ttk.LabelFrame(left, text=self._rtl_text(tr(self.language, "group_by_category")), padding=8, style="Card.TLabelframe")
        left_tree.pack(fill="both", expand=False, side="top", pady=(0, 5))

        self.category_tree = ttk.Treeview(
            left_tree,
            columns=("category", "income", "expense", "balance"),
            show="headings",
            height=6,
        )
        self.category_tree.pack(fill="both", expand=True, side="left")

        text_anchor = "e" if is_rtl(self.language) else "w"

        self.category_tree.heading("category", text=self._rtl_text(tr(self.language, "col_category")))
        self.category_tree.heading("income", text=self._rtl_text(tr(self.language, "legend_income")))
        self.category_tree.heading("expense", text=self._rtl_text(tr(self.language, "legend_expense")))
        self.category_tree.heading("balance", text=self._rtl_text(tr(self.language, "legend_balance")))

        self.category_tree.column("category", width=160, anchor=text_anchor)
        self.category_tree.column("income", width=100, anchor="e")
        self.category_tree.column("expense", width=100, anchor="e")
        self.category_tree.column("balance", width=100, anchor="e")

        cat_scroll = ttk.Scrollbar(left_tree, orient="vertical", command=self.category_tree.yview)
        cat_scroll.pack(fill="y", side="right")
        self.category_tree.configure(yscrollcommand=cat_scroll.set)

        left_chart = ttk.LabelFrame(left, text=self._rtl_text(tr(self.language, "chart_title_category")), padding=8, style="Card.TLabelframe")
        left_chart.pack(fill="both", expand=True, side="top")
        self._chart_frame_category = ttk.Frame(left_chart, style="Card.TFrame")
        self._chart_frame_category.pack(fill="both", expand=True)

        right_tree = ttk.LabelFrame(right, text=self._rtl_text(tr(self.language, "group_by_month")), padding=8, style="Card.TLabelframe")
        right_tree.pack(fill="both", expand=False, side="top", pady=(0, 5))

        self.month_tree = ttk.Treeview(
            right_tree,
            columns=("month", "income", "expense", "balance"),
            show="headings",
            height=6,
        )
        self.month_tree.pack(fill="both", expand=True, side="left")

        self.month_tree.heading("month", text=self._rtl_text(tr(self.language, "chart_x_month")))
        self.month_tree.heading("income", text=self._rtl_text(tr(self.language, "legend_income")))
        self.month_tree.heading("expense", text=self._rtl_text(tr(self.language, "legend_expense")))
        self.month_tree.heading("balance", text=self._rtl_text(tr(self.language, "legend_balance")))

        self.month_tree.column("month", width=120, anchor="center")
        self.month_tree.column("income", width=100, anchor="e")
        self.month_tree.column("expense", width=100, anchor="e")
        self.month_tree.column("balance", width=100, anchor="e")

        month_scroll = ttk.Scrollbar(right_tree, orient="vertical", command=self.month_tree.yview)
        month_scroll.pack(fill="y", side="right")
        self.month_tree.configure(yscrollcommand=month_scroll.set)

        series_toggles = ttk.Frame(right, style="App.TFrame")
        series_toggles.pack(fill="x", pady=(4, 2))
        chk_income = ttk.Checkbutton(
            series_toggles, text=self._rtl_text(tr(self.language, "legend_income")),
            variable=self._show_income, command=self._update_charts,
        )
        chk_income.pack(side="left", padx=(0, 8))
        self._apply_rtl_to_widget(chk_income)

        chk_expense = ttk.Checkbutton(
            series_toggles, text=self._rtl_text(tr(self.language, "legend_expense")),
            variable=self._show_expense, command=self._update_charts,
        )
        chk_expense.pack(side="left", padx=(0, 8))
        self._apply_rtl_to_widget(chk_expense)

        chk_balance = ttk.Checkbutton(
            series_toggles, text=self._rtl_text(tr(self.language, "legend_balance")),
            variable=self._show_balance, command=self._update_charts,
        )
        chk_balance.pack(side="left", padx=(0, 8))
        self._apply_rtl_to_widget(chk_balance)

        right_chart = ttk.LabelFrame(right, text=self._rtl_text(tr(self.language, "chart_title_month")), padding=8, style="Card.TLabelframe")
        right_chart.pack(fill="both", expand=True, side="top")
        self._chart_frame_month = ttk.Frame(right_chart, style="Card.TFrame")
        self._chart_frame_month.pack(fill="both", expand=True)

    def _on_language_change(self) -> None:
        selected_display = self.language_var.get().strip()
        selected_code = self._language_display_to_code.get(selected_display, self.language)
        if selected_code == self.language:
            return

        current_category = self.filter_category_var.get().strip()
        current_was_all = current_category == self._all_label

        reload_translations()
        self.language = selected_code
        self._sync_language_maps()

        if current_was_all:
            self.filter_category_var.set(self._all_label)

        self._build_ui()
        self._refresh_all()
        self._save_ui_state()

    def _normalize_filter_type_key(self, value: str) -> str:
        value_clean = value.strip().lower()
        if value_clean in {"all", "income", "expense"}:
            return value_clean
        return "all"

    def _normalize_register_type_key(self, value: str) -> str:
        value_clean = value.strip().lower()
        if value_clean in {"income", "expense"}:
            return value_clean
        return "expense"

    def _category_options(self, type_key: str) -> list[str]:
        return category_options_for_type(self.language, type_key)

    def _on_register_type_changed(self) -> None:
        display_value = self.type_var.get().strip()
        self.register_type_key = self._type_display_to_db.get(display_value, "expense")
        options = self._category_options(self.register_type_key)
        self.category_box.configure(values=options)

        if self.category_var.get() not in options:
            self.category_var.set(options[0])

    def _save_transaction(self) -> None:
        try:
            transaction = self._transaction_from_form()
            if self.editing_transaction_id is None:
                transaction_id = self.database.add_transaction(transaction, language=self.language)
                success_message = tr(self.language, "success_saved", id=transaction_id)
            else:
                updated = self.database.update_transaction(
                    self.editing_transaction_id,
                    transaction,
                    language=self.language,
                )
                if not updated:
                    raise ValueError(tr(self.language, "update_not_found"))
                success_message = tr(self.language, "success_updated", id=self.editing_transaction_id)
        except ValueError as error:
            messagebox.showerror(tr(self.language, "error_invalid_data"), str(error), parent=self)
            return
        except Exception as error:
            messagebox.showerror(
                tr(self.language, "error_generic"),
                tr(self.language, "error_could_not_save", error=error),
                parent=self,
            )
            return

        messagebox.showinfo(tr(self.language, "success"), success_message, parent=self)
        self._clear_form(keep_date=True)
        self._refresh_all()

    def _transaction_from_form(self) -> TransactionInput:
        return TransactionInput(
            amount=float(self.amount_var.get().strip()),
            transaction_type=self.register_type_key,
            category=self.category_var.get().strip(),
            transaction_date=date.fromisoformat(self.date_var.get().strip()),
            description=self.description_text.get("1.0", "end").strip(),
        )

    def _clear_form(self, keep_date: bool = False) -> None:
        self.editing_transaction_id = None
        self.register_type_key = "expense"
        self.type_var.set(self._type_db_to_display.get(self.register_type_key, tr(self.language, "type_expense")))
        self.amount_var.set("")
        self._on_register_type_changed()
        if not keep_date:
            self.date_var.set(date.today().isoformat())
        self.description_text.delete("1.0", "end")
        self._update_save_button_text()

    def _update_save_button_text(self) -> None:
        if not hasattr(self, "save_button_var"):
            return
        if self.editing_transaction_id is None:
            self.save_button_var.set(tr(self.language, "btn_save_transaction"))
        else:
            self.save_button_var.set(tr(self.language, "btn_update_transaction"))

    def _refresh_all(self) -> None:
        self._load_transactions()
        self._load_stats()

    def _on_search_change(self, *_: object) -> None:
        self._on_filter_change()

    def _on_filter_change(self) -> None:
        self.filter_type_key = self._filter_display_to_key.get(self.filter_type_var.get().strip(), "all")
        self._current_page = 0
        self._load_transactions()
        self._save_ui_state()

    def _open_calendar_for_var(
        self,
        target_var: tk.StringVar,
        title: str,
        on_change: Callable[[], None] | None = None,
    ) -> None:
        initial = self._safe_parse_date(target_var.get()) or date.today()

        def _apply(selected: date) -> None:
            target_var.set(selected.isoformat())
            if on_change is not None:
                on_change()

        CalendarDialog(self, initial, _apply, language=self.language, title=title)

    def _clear_filters(self) -> None:
        self.search_var.set("")
        self.filter_type_key = "all"
        self.filter_type_var.set(self._filter_key_to_display[self.filter_type_key])
        self.filter_category_var.set(self._all_label)
        self.filter_from_var.set("")
        self.filter_to_var.set("")
        self._on_filter_change()

    def _apply_date_preset(self, preset: str) -> None:
        today = date.today()

        if preset == "all":
            self.filter_from_var.set("")
            self.filter_to_var.set("")
            self._on_filter_change()
            return

        if preset == "today":
            start_date = today
            end_date = today
        elif preset == "week":
            start_date = today - timedelta(days=today.weekday())
            end_date = today
        elif preset == "month":
            start_date = today.replace(day=1)
            end_date = today
        elif preset == "year":
            start_date = today.replace(month=1, day=1)
            end_date = today
        else:
            return

        self.filter_from_var.set(start_date.isoformat())
        self.filter_to_var.set(end_date.isoformat())
        self._on_filter_change()

    def _sync_category_filter(self, rows: list[dict[str, object]]) -> None:
        categories = sorted({str(row["category"]) for row in rows})
        values = [self._all_label, *categories]
        self.category_filter_box.configure(values=values)

        current = self.filter_category_var.get().strip()
        if not current or current not in values:
            self.filter_category_var.set(self._all_label)

    def _apply_transaction_filters(self, rows: list[dict[str, object]]) -> list[dict[str, object]]:
        selected_type_db = "" if self.filter_type_key == "all" else self.filter_type_key
        date_from = self._safe_parse_date(self.filter_from_var.get())
        date_to = self._safe_parse_date(self.filter_to_var.get())

        return filter_transaction_rows(
            rows=rows,
            search=self.search_var.get(),
            selected_type_db=selected_type_db,
            selected_category=self.filter_category_var.get(),
            all_label=self._all_label,
            date_from=date_from,
            date_to=date_to,
            type_db_to_display=self._type_db_to_display,
        )

    def _selected_transaction_data(self) -> dict[str, str] | None:
        selection = self.transactions_tree.selection()
        if not selection:
            return None

        values = self.transactions_tree.item(selection[0], "values")
        if len(values) < 6:
            return None

        return {
            "id": str(values[0]),
            "date": str(values[1]),
            "type": str(values[2]),
            "category": str(values[3]),
            "amount": str(values[4]),
            "description": str(values[5]),
        }

    def _load_selected_into_form(self) -> None:
        row = self._selected_transaction_data()
        if row is None:
            messagebox.showwarning(
                tr(self.language, "warning_select_title"),
                tr(self.language, "warning_select_transaction"),
                parent=self,
            )
            return

        self.editing_transaction_id = int(row["id"])
        display_type = row["type"]
        db_type = self._type_display_to_db.get(display_type, "expense")
        self.register_type_key = db_type
        self.type_var.set(self._type_db_to_display.get(db_type, display_type))
        self._on_register_type_changed()

        self.amount_var.set(row["amount"])
        self.date_var.set(row["date"])

        category_value = row["category"]
        options = list(self.category_box["values"])
        if category_value not in options:
            options.append(category_value)
            self.category_box.configure(values=options)
        self.category_var.set(category_value)

        self.description_text.delete("1.0", "end")
        self.description_text.insert("1.0", row["description"])
        self._update_save_button_text()

        if self._notebook is not None and self._tab_register is not None:
            self._notebook.select(self._tab_register)

    def _delete_selected_transaction(self) -> None:
        row = self._selected_transaction_data()
        if row is None:
            messagebox.showwarning(
                tr(self.language, "warning_select_title"),
                tr(self.language, "warning_select_transaction"),
                parent=self,
            )
            return

        confirm = messagebox.askyesno(
            tr(self.language, "confirm_delete_title"),
            tr(self.language, "confirm_delete_message", id=row["id"]),
            parent=self,
        )
        if not confirm:
            return

        try:
            deleted = self.database.delete_transaction(int(row["id"]))
        except Exception as error:
            messagebox.showerror(
                tr(self.language, "error_generic"),
                tr(self.language, "delete_failed", error=error),
                parent=self,
            )
            return

        if not deleted:
            messagebox.showerror(
                tr(self.language, "error_generic"),
                tr(self.language, "delete_failed", error=tr(self.language, "delete_not_found")),
                parent=self,
            )
            return

        messagebox.showinfo(
            tr(self.language, "success"),
            tr(self.language, "delete_success"),
            parent=self,
        )
        self._refresh_all()

    def _sort_transactions(self, rows: list[dict[str, object]]) -> list[dict[str, object]]:
        return sorted(rows, key=self._row_sort_key, reverse=self.sort_desc)

    def _row_sort_key(self, row: dict[str, object]) -> tuple[int, object]:
        if self.sort_column == "id":
            return (0, int(row["id"]))
        if self.sort_column == "amount":
            return (0, float(row["amount"]))
        if self.sort_column == "date":
            parsed = self._safe_parse_date(str(row["transaction_date"]))
            return (0, parsed or date.min)
        if self.sort_column == "type":
            return (0, str(row["transaction_type"]).lower())
        if self.sort_column == "category":
            return (0, str(row["category"]).lower())
        if self.sort_column == "description":
            return (0, str(row["description"]).lower())
        return (0, str(row))

    def _on_sort_change(self, column_name: str) -> None:
        if column_name == self.sort_column:
            self.sort_desc = not self.sort_desc
        else:
            self.sort_column = column_name
            self.sort_desc = False

        self._refresh_sort_headers()
        self._load_transactions()
        self._save_ui_state()

    def _refresh_sort_headers(self) -> None:
        arrow = "▼" if self.sort_desc else "▲"
        for column_name, title in self._column_titles.items():
            label = title if column_name != self.sort_column else f"{title} {arrow}"
            self.transactions_tree.heading(
                column_name,
                text=label,
                command=lambda selected=column_name: self._on_sort_change(selected),
            )

    @staticmethod
    def _safe_parse_date(raw_value: str) -> date | None:
        return safe_parse_date(raw_value)

    def _read_ui_state(self) -> dict[str, Any]:
        if not self.state_file.exists():
            return {}

        try:
            return json.loads(self.state_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def _save_ui_state(self) -> None:
        data = {
            "language": self.language,
            "theme_mode": self.theme_mode,
            "palette": self.palette,
            "search": self.search_var.get(),
            "register_type_key": self.register_type_key,
            "filter_type_key": self.filter_type_key,
            "filter_category": self.filter_category_var.get(),
            "filter_from": self.filter_from_var.get(),
            "filter_to": self.filter_to_var.get(),
            "sort_column": self.sort_column,
            "sort_desc": self.sort_desc,
        }

        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            if self.state_file.parent != Path("."):
                apply_private_permissions(self.state_file.parent, directory=True)

            temporary_file = self.state_file.with_suffix(self.state_file.suffix + ".tmp")
            temporary_file.write_text(json.dumps(data, ensure_ascii=True, indent=2), encoding="utf-8")
            apply_private_permissions(temporary_file)
            temporary_file.replace(self.state_file)
            apply_private_permissions(self.state_file)
        except OSError:
            return

    def _on_close(self) -> None:
        self.scheduler.stop()
        self._save_ui_state()
        self.destroy()

    def _toggle_lock(self) -> None:
        if LockManager.is_lock_set():
            stored_hash = LockManager.LOCK_FILE.read_text(encoding="utf-8").strip()
            dialog = LockScreenDialog(self, self.language, mode="unlock", current_hash=stored_hash)
            self.wait_window(dialog)
            if dialog.success:
                LockManager.remove_lock()
                LockManager.deactivate_lock()
                FileAuditLog.log(FileAuditLog.ACTION_LOCK_CHANGE, entity="lock", details="Lock removed")
                messagebox.showinfo(tr(self.language, "success"), tr(self.language, "lock_disabled"), parent=self)
                self._rebuild_header()
            return

        dialog = LockScreenDialog(self, self.language, mode="set")
        self.wait_window(dialog)
        if dialog.success and dialog.new_hash:
            LockManager.set_lock_from_hash(dialog.new_hash)
            LockManager.activate_lock()
            FileAuditLog.log(FileAuditLog.ACTION_LOCK_SET, entity="lock", details="PIN lock set")
            self._rebuild_header()

    def _rebuild_header(self) -> None:
        if self._container is not None:
            self._container.destroy()
        self._container = None
        self._build_ui()
        self._refresh_all()

    def _create_backup(self) -> None:
        try:
            backup_path = self.database.create_backup()
            FileAuditLog.log(FileAuditLog.ACTION_BACKUP, entity="database", details=str(backup_path))
            messagebox.showinfo(
                tr(self.language, "success"),
                tr(self.language, "backup_created", path=backup_path),
                parent=self,
            )
        except Exception as error:
            messagebox.showerror(
                tr(self.language, "error_generic"),
                tr(self.language, "backup_failed", error=error),
                parent=self,
            )

    def _encrypt_database(self) -> None:
        if SQLCipherManager.is_encrypted_db(Path(self.database.db_path)):
            messagebox.showinfo(tr(self.language, "info"), tr(self.language, "db_already_encrypted"), parent=self)
            return
        if not LockManager.is_lock_set():
            messagebox.showwarning(
                tr(self.language, "warning_no_lock"),
                tr(self.language, "lock_required_for_encryption"),
                parent=self,
            )
            return

        stored_hash = LockManager.LOCK_FILE.read_text(encoding="utf-8").strip()
        dialog = LockScreenDialog(self, self.language, mode="unlock", current_hash=stored_hash)
        self.wait_window(dialog)
        if not dialog.success:
            return
        pin = dialog.pin_var.get()

        try:
            key = SQLCipherManager.generate_key()
            SQLCipherManager.migrate_to_encrypted(Path(self.database.db_path), key)
            SQLCipherManager.store_key(key, pin)
            FileAuditLog.log(FileAuditLog.ACTION_LOCK_SET, entity="database", details="Database encrypted with SQLCipher")
            messagebox.showinfo(
                tr(self.language, "success"),
                tr(self.language, "db_encrypted_success"),
                parent=self,
            )
            self._rebuild_header()
        except Exception as error:
            messagebox.showerror(
                tr(self.language, "error_generic"),
                tr(self.language, "db_encryption_failed", error=error),
                parent=self,
            )

    def _toggle_theme(self) -> None:
        new_mode = "dark" if self.theme_mode == "light" else "light"
        self._set_theme(new_mode)
        self._save_ui_state()

    def _set_theme(self, mode: str) -> None:
        self.theme_mode = "dark" if mode == "dark" else "light"
        self._setup_theme()
        self._apply_runtime_theme()
        self._update_theme_button_text()

    def _apply_runtime_theme(self) -> None:
        if hasattr(self, "description_text"):
            self.description_text.configure(
                background=self._colors["input_bg"],
                foreground=self._colors["text"],
                insertbackground=self._colors["text"],
            )
        if hasattr(self, "transactions_tree"):
            self.transactions_tree.tag_configure("income", foreground=self._colors["positive"])
            self.transactions_tree.tag_configure("expense", foreground=self._colors["negative"])
        self._update_kpi_colors()

    def _update_theme_button_text(self) -> None:
        if hasattr(self, "theme_button"):
            if self.theme_mode == "light":
                self.theme_button.configure(text=tr(self.language, "btn_dark_mode"))
            else:
                self.theme_button.configure(text=tr(self.language, "btn_light_mode"))

    def _setup_theme(self) -> None:
        theme_name = "flatly" if self.theme_mode == "light" else "darkly"
        self._ttkb_style = ttkb.Style(theme_name)
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

        style = ttk.Style(self)
        self.configure(background=self._colors["bg"])
        self.option_add("*Font", "TkDefaultFont 10")

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

    def _setup_shortcuts(self) -> None:
        self.bind_all("<Control-n>", lambda _event: self._shortcut_new_transaction())
        self.bind_all("<Control-f>", lambda _event: self._shortcut_focus_search())
        self.bind_all("<Control-s>", lambda _event: self._shortcut_save())
        self.bind_all("<F5>", lambda _event: self._refresh_all())
        self.bind_all("<Control-g>", lambda _event: self._generate_charts())
        self.bind_all("<Control-e>", lambda _event: self._quick_export())
        self.bind_all("<Control-1>", lambda _event: self._select_tab(0))
        self.bind_all("<Control-2>", lambda _event: self._select_tab(1))
        self.bind_all("<Control-3>", lambda _event: self._select_tab(2))

    def _shortcut_new_transaction(self) -> None:
        focused = self.focus_get()
        if isinstance(focused, (tk.Entry, tk.Text)):
            return
        self._select_tab(0)
        self._clear_form(keep_date=True)
        if hasattr(self, "amount_entry"):
            self.amount_entry.focus_set()

    def _shortcut_focus_search(self) -> None:
        self._select_tab(1)
        if hasattr(self, "search_entry"):
            self.search_entry.focus_set()

    def _shortcut_save(self) -> None:
        focused = self.focus_get()
        if isinstance(focused, tk.Text):
            return
        self._save_transaction()

    def _select_tab(self, index: int) -> None:
        if self._notebook is not None:
            self._notebook.select(index)

    def _validate_amount(self, *_: object) -> None:
        value = self.amount_var.get().strip()
        if not value:
            self._set_indicator(self._amount_indicator, "")
            return
        try:
            amount = float(value)
            if amount > 0 and amount == amount and abs(amount) != float("inf"):
                self._set_indicator(self._amount_indicator, "✓", self._colors["positive"])
            else:
                self._set_indicator(self._amount_indicator, "✗", self._colors["negative"])
        except ValueError:
            self._set_indicator(self._amount_indicator, "✗", self._colors["negative"])

    def _validate_date(self, *_: object) -> None:
        value = self.date_var.get().strip()
        if not value:
            self._set_indicator(self._date_indicator, "")
            return
        try:
            date.fromisoformat(value)
            self._set_indicator(self._date_indicator, "✓", self._colors["positive"])
        except ValueError:
            self._set_indicator(self._date_indicator, "✗", self._colors["negative"])

    def _validate_category(self, *_: object) -> None:
        value = self.category_var.get().strip()
        if value:
            self._set_indicator(self._category_indicator, "✓", self._colors["positive"])
        else:
            self._set_indicator(self._category_indicator, "✗", self._colors["negative"])

    @staticmethod
    def _set_indicator(label: ttk.Label | None, text: str, color: str = "") -> None:
        if label is None:
            return
        label.configure(text=text, foreground=color if color else label.master["style"])

    def _go_to_page(self, delta: int) -> None:
        new_page = self._current_page + delta
        if 0 <= new_page < self._total_pages:
            self._current_page = new_page
            self._load_transactions()

    def _update_charts(self) -> None:
        category_rows = self.database.get_totals_by_category()
        month_rows = self.database.get_totals_by_month()

        self._destroy_chart(self._chart_canvas_category, self._chart_toolbar_category)
        self._destroy_chart(self._chart_canvas_month, self._chart_toolbar_month)

        if not category_rows and not month_rows:
            return

        self._chart_scroll_cids: list[int] = []

        if category_rows and hasattr(self, "_chart_frame_category"):
            figure = Figure(figsize=(5, 3), dpi=100)
            axis = figure.add_subplot(111)
            categories = [r["category"] for r in category_rows]
            expense_values = [float(r["expense"]) for r in category_rows]
            income_values = [float(r["income"]) for r in category_rows]
            x = range(len(categories))
            axis.bar(x, income_values, label=tr(self.language, "legend_income"), color=self._colors["positive"])
            axis.bar(x, expense_values, label=tr(self.language, "legend_expense"), color=self._colors["negative"], alpha=0.85)
            axis.set_xticks(list(x))
            axis.set_xticklabels(categories, rotation=30, ha="right", fontsize=8)
            axis.legend(fontsize=8)
            axis.set_title(tr(self.language, "chart_title_category"), fontsize=10)
            self._add_tooltip_to_bars(axis, categories, income_values, expense_values)
            figure.tight_layout()
            self._chart_canvas_category = FigureCanvasTkAgg(figure, master=self._chart_frame_category)
            self._chart_canvas_category.draw()
            self._chart_canvas_category.get_tk_widget().pack(fill="both", expand=True)
            self._chart_toolbar_category = NavigationToolbar2Tk(self._chart_canvas_category, self._chart_frame_category, pack_toolbar=False)
            self._chart_toolbar_category.update()
            self._chart_toolbar_category.pack(fill="x", side="bottom")
            cid = self._enable_scroll_zoom(figure, axis)
            if cid is not None:
                self._chart_scroll_cids.append(cid)

        if month_rows and hasattr(self, "_chart_frame_month"):
            figure = Figure(figsize=(5, 3), dpi=100)
            axis = figure.add_subplot(111)
            months = [r["month"] for r in month_rows]
            income_values = [float(r["income"]) for r in month_rows]
            expense_values = [float(r["expense"]) for r in month_rows]
            balance_values = [float(r["balance"]) for r in month_rows]
            if self._show_income.get():
                axis.plot(months, income_values, marker="o", label=tr(self.language, "legend_income"), color=self._colors["positive"])
            if self._show_expense.get():
                axis.plot(months, expense_values, marker="o", label=tr(self.language, "legend_expense"), color=self._colors["negative"])
            if self._show_balance.get():
                axis.plot(months, balance_values, marker="o", label=tr(self.language, "legend_balance"), color=self._colors["accent"])
            axis.set_xticklabels(months, rotation=30, ha="right", fontsize=8)
            if any([self._show_income.get(), self._show_expense.get(), self._show_balance.get()]):
                axis.legend(fontsize=8)
            axis.set_title(tr(self.language, "chart_title_month"), fontsize=10)
            axis.grid(alpha=0.3)
            self._add_tooltip_to_lines(axis, months, income_values, expense_values, balance_values)
            figure.tight_layout()
            self._chart_canvas_month = FigureCanvasTkAgg(figure, master=self._chart_frame_month)
            self._chart_canvas_month.draw()
            self._chart_canvas_month.get_tk_widget().pack(fill="both", expand=True)
            self._chart_toolbar_month = NavigationToolbar2Tk(self._chart_canvas_month, self._chart_frame_month, pack_toolbar=False)
            self._chart_toolbar_month.update()
            self._chart_toolbar_month.pack(fill="x", side="bottom")
            cid = self._enable_scroll_zoom(figure, axis)
            if cid is not None:
                self._chart_scroll_cids.append(cid)

    def _destroy_chart(self, canvas: FigureCanvasTkAgg | None, toolbar: NavigationToolbar2Tk | None) -> None:
        if canvas is not None:
            canvas.get_tk_widget().destroy()
        if toolbar is not None:
            toolbar.destroy()

    def _add_tooltip_to_bars(self, axis, categories, income_values, expense_values) -> None:
        tooltip = tk.Toplevel(self)
        tooltip.overrideredirect(True)
        tooltip.withdraw()
        label = ttk.Label(tooltip, text="", background="yellow", relief="solid", borderwidth=1, padding=(4, 2))
        label.pack()

        def on_motion(event):
            if event.inaxes != axis:
                tooltip.withdraw()
                return
            found = False
            for bar, cat, inc, exp in zip(axis.patches, categories, income_values, expense_values):
                if bar.contains_point((event.x, event.y), radius=5):
                    text = (
                        f"{cat}\n"
                        f"{tr(self.language, 'legend_income')}: {format_number(self.language, inc)}\n"
                        f"{tr(self.language, 'legend_expense')}: {format_number(self.language, exp)}"
                    )
                    label.configure(text=text)
                    tooltip.deiconify()
                    tooltip.geometry(f"+{self.winfo_pointerx() + 15}+{self.winfo_pointery() + 15}")
                    found = True
                    break
            if not found:
                tooltip.withdraw()

        axis.figure.canvas.mpl_connect("motion_notify_event", on_motion)

    def _add_tooltip_to_lines(self, axis, months, income_values, expense_values, balance_values) -> None:
        tooltip = tk.Toplevel(self)
        tooltip.overrideredirect(True)
        tooltip.withdraw()
        label = ttk.Label(tooltip, text="", background="yellow", relief="solid", borderwidth=1, padding=(4, 2))
        label.pack()

        def on_motion(event):
            if event.inaxes != axis:
                tooltip.withdraw()
                return
            found = False
            # Check proximity to each data point using data coordinates
            for i, month in enumerate(months):
                x_data = i
                for y_data, key, color in [
                    (income_values[i], "legend_income", self._colors["positive"]),
                    (expense_values[i], "legend_expense", self._colors["negative"]),
                    (balance_values[i], "legend_balance", self._colors["accent"]),
                ]:
                    # Convert data to display coordinates
                    x_display, y_display = axis.transData.transform((x_data, y_data))
                    dist = ((event.x - x_display) ** 2 + (event.y - y_display) ** 2) ** 0.5
                    if dist < 10:
                        text = (
                            f"{month}\n"
                            f"{tr(self.language, 'legend_income')}: {format_number(self.language, income_values[i])}\n"
                            f"{tr(self.language, 'legend_expense')}: {format_number(self.language, expense_values[i])}\n"
                            f"{tr(self.language, 'legend_balance')}: {format_number(self.language, balance_values[i])}"
                        )
                        label.configure(text=text)
                        tooltip.deiconify()
                        tooltip.geometry(f"+{self.winfo_pointerx() + 15}+{self.winfo_pointery() + 15}")
                        found = True
                        break
                if found:
                    break
            if not found:
                tooltip.withdraw()

        axis.figure.canvas.mpl_connect("motion_notify_event", on_motion)

    def _enable_scroll_zoom(self, figure, axis):
        def on_scroll(event):
            if event.inaxes != axis:
                return
            x_min, x_max = axis.get_xlim()
            y_min, y_max = axis.get_ylim()
            # Zoom factor: step > 0 zoom in, step < 0 zoom out
            factor = 0.9 if event.step > 0 else 1.1
            # Keep the point under the cursor fixed
            x_data, y_data = event.xdata, event.ydata
            if x_data is None or y_data is None:
                return
            new_x_min = x_data - (x_data - x_min) * factor
            new_x_max = x_data + (x_max - x_data) * factor
            new_y_min = y_data - (y_data - y_min) * factor
            new_y_max = y_data + (y_max - y_data) * factor
            axis.set_xlim(new_x_min, new_x_max)
            axis.set_ylim(new_y_min, new_y_max)
            figure.canvas.draw_idle()

        cid = figure.canvas.mpl_connect("scroll_event", on_scroll)
        return cid

    def _load_transactions(self) -> None:
        self._clear_tree(self.transactions_tree)
        rows = self.database.fetch_transactions(limit=None)
        self._sync_category_filter(rows)

        filtered_rows = self._apply_transaction_filters(rows)
        sorted_rows = self._sort_transactions(filtered_rows)

        total = len(sorted_rows)
        self._total_pages = max(1, (total + self._page_size - 1) // self._page_size)
        self._current_page = min(self._current_page, self._total_pages - 1)

        start = self._current_page * self._page_size
        end = start + self._page_size
        page_rows = sorted_rows[start:end]

        for row in page_rows:
            tag = "income" if row["transaction_type"] == "income" else "expense"
            tx_date = safe_parse_date(str(row["transaction_date"]))
            display_date = format_date(self.language, tx_date) if tx_date else str(row["transaction_date"])
            self.transactions_tree.insert(
                "",
                "end",
                values=(
                    row["id"],
                    display_date,
                    self._type_db_to_display.get(str(row["transaction_type"]), str(row["transaction_type"])),
                    row["category"],
                    format_number(self.language, float(row["amount"])),
                    row["description"],
                ),
                tags=(tag,),
            )

        self.filtered_count_var.set(
            tr(
                self.language,
                "showing_rows_paginated",
                filtered=len(page_rows),
                total=total,
                page=self._current_page + 1,
                pages=self._total_pages,
            )
        )

        if hasattr(self, "_page_label_var"):
            self._page_label_var.set(f"{self._current_page + 1} / {self._total_pages}")
        if hasattr(self, "_btn_prev"):
            self._btn_prev.configure(state="normal" if self._current_page > 0 else "disabled")
        if hasattr(self, "_btn_next"):
            self._btn_next.configure(state="normal" if self._current_page < self._total_pages - 1 else "disabled")

    def _load_stats(self) -> None:
        self._clear_tree(self.category_tree)
        self._clear_tree(self.month_tree)

        totals = self.database.get_totals_by_type()
        self._last_totals = totals
        self.balance_var.set(tr(self.language, "balance_label", amount=format_number(self.language, totals["balance"])))
        self.income_var.set(tr(self.language, "income_total_label", amount=format_number(self.language, totals["income"])))
        self.expense_var.set(tr(self.language, "expense_total_label", amount=format_number(self.language, totals["expense"])))
        self._update_kpi_colors()

        for row in self.database.get_totals_by_category():
            self.category_tree.insert(
                "",
                "end",
                values=(
                    row["category"],
                    format_number(self.language, float(row["income"])),
                    format_number(self.language, float(row["expense"])),
                    format_number(self.language, float(row["balance"])),
                ),
            )

        for row in self.database.get_totals_by_month():
            self.month_tree.insert(
                "",
                "end",
                values=(
                    row["month"],
                    format_number(self.language, float(row["income"])),
                    format_number(self.language, float(row["expense"])),
                    format_number(self.language, float(row["balance"])),
                ),
            )

        self._update_charts()

    def _update_kpi_colors(self) -> None:
        if not hasattr(self, "balance_label"):
            return

        balance = float(self._last_totals.get("balance", 0.0))
        self.balance_label.configure(
            foreground=self._colors["positive"] if balance >= 0 else self._colors["negative"]
        )

        if hasattr(self, "income_label"):
            self.income_label.configure(foreground=self._colors["positive"])
        if hasattr(self, "expense_label"):
            self.expense_label.configure(foreground=self._colors["negative"])

    def _generate_charts(self) -> None:
        dialog = ChartTypeDialog(self, self.language, self._chart_type_options())
        self.wait_window(dialog)

        if not dialog.selected_kind:
            return

        try:
            budget_rows: list[dict[str, object]] | None = None
            if dialog.selected_kind == "budget":
                today = date.today()
                month_str = today.strftime("%Y-%m")
                budget_rows = self.database.get_budget_vs_actual(month_str)

            ChartViewerDialog(
                parent=self,
                language=self.language,
                palette=self.palette,
                kind=dialog.selected_kind,
                category_rows=self.database.get_totals_by_category(),
                month_rows=self.database.get_totals_by_month(),
                budget_rows=budget_rows,
            )
        except Exception as error:
            messagebox.showerror(
                tr(self.language, "error_generic"),
                tr(self.language, "error_chart_failed", error=error),
                parent=self,
            )

    def _on_palette_change(self) -> None:
        new_palette = self.palette_var.get().strip()
        if new_palette == self.palette:
            return
        self.palette = new_palette
        self._update_charts()
        self._save_ui_state()

    def _open_automation_dialog(self) -> None:
        AutomationDialog(
            parent=self,
            database=self.database,
            scheduler=self.scheduler,
            language=self.language,
        )

    def _open_cloud_sync_dialog(self) -> None:
        from expenses_tracker.security import KeyDerivation

        encryption_key = None
        if LockManager.is_lock_set():
            stored_hash = LockManager.LOCK_FILE.read_text(encoding="utf-8").strip()
            dialog = LockScreenDialog(self, self.language, mode="unlock", current_hash=stored_hash)
            self.wait_window(dialog)
            if dialog.success:
                # Derive a deterministic key from the PIN for cloud encryption
                # We use a fixed salt for cloud sync so the same PIN always produces the same key
                salt = b"cloud_sync_salt_fixed_32bytes!"
                encryption_key, _ = KeyDerivation.derive_key(dialog.pin_var.get(), salt)

        CloudSyncDialog(
            parent=self,
            language=self.language,
            db_path=str(self.database.db_path),
            encryption_key=encryption_key,
        )

    def _export(self, fmt: str) -> None:
        all_transactions = self.database.fetch_transactions(limit=None)
        transactions = self._apply_transaction_filters(all_transactions)
        if not transactions:
            messagebox.showwarning(
                tr(self.language, "warning_no_data"),
                tr(self.language, "warning_no_transactions_export"),
                parent=self,
            )
            return

        category_rows = _compute_category_rows_from_transactions(transactions)
        month_rows = _compute_month_rows_from_transactions(transactions)

        try:
            generated = export_reports(
                transactions=transactions,
                category_rows=category_rows,
                month_rows=month_rows,
                output_dir="reports",
                fmt=fmt,
                language=self.language,
            )
        except Exception as error:
            messagebox.showerror(
                tr(self.language, "error_generic"),
                tr(self.language, "error_export_failed", error=error),
                parent=self,
            )
            return

        if not generated:
            messagebox.showwarning(
                tr(self.language, "warning_no_files"),
                tr(self.language, "warning_no_files_generated"),
                parent=self,
            )
            return

        files_text = "\n".join(path.as_posix() for path in generated)
        messagebox.showinfo(tr(self.language, "info_reports_generated"), files_text, parent=self)

    def _quick_export(self) -> None:
        """Export all formats for the last month with available data."""
        all_transactions = self.database.fetch_transactions(limit=None)
        if not all_transactions:
            messagebox.showwarning(
                tr(self.language, "warning_no_data"),
                tr(self.language, "warning_no_transactions_export"),
                parent=self,
            )
            return

        latest_month = max(str(row["transaction_date"])[:7] for row in all_transactions)
        month_transactions = [row for row in all_transactions if str(row["transaction_date"]).startswith(latest_month)]
        if not month_transactions:
            messagebox.showwarning(
                tr(self.language, "warning_no_data"),
                tr(self.language, "warning_no_transactions_export"),
                parent=self,
            )
            return

        category_rows = _compute_category_rows_from_transactions(month_transactions)
        month_rows = _compute_month_rows_from_transactions(month_transactions)

        try:
            generated = export_reports(
                transactions=month_transactions,
                category_rows=category_rows,
                month_rows=month_rows,
                output_dir="reports",
                fmt="all",
                language=self.language,
                year_month=latest_month,
            )
        except Exception as error:
            messagebox.showerror(
                tr(self.language, "error_generic"),
                tr(self.language, "error_export_failed", error=error),
                parent=self,
            )
            return

        files_text = "\n".join(path.as_posix() for path in generated)
        messagebox.showinfo(tr(self.language, "info_reports_generated"), files_text, parent=self)

    @staticmethod
    def _clear_tree(tree: ttk.Treeview) -> None:
        for item in tree.get_children():
            tree.delete(item)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--lang", default=None)
    parser.add_argument("--list-languages", action="store_true")

    args, _ = parser.parse_known_args(argv)
    language = normalize_language(args.lang)

    if args.list_languages:
        print(tr(language, "supported_languages"))
        for code, name in list_languages():
            print(f"- {code}: {name}")
        return 0

    if LockManager.is_lock_active():
        stored_hash = LockManager.LOCK_FILE.read_text(encoding="utf-8").strip()
        temp_root = tk.Tk()
        temp_root.withdraw()
        dialog = LockScreenDialog(temp_root, language, mode="unlock", current_hash=stored_hash)
        temp_root.wait_window(dialog)
        temp_root.destroy()

        if not dialog.success:
            return 1  # User cancelled or wrong PIN

    cipher_key = None
    db_path = Path("data/expenses.db")
    if SQLCipherManager.KEY_FILE.exists():
        # Encrypted database: need PIN to decrypt SQLCipher key
        if not LockManager.is_lock_set():
            messagebox.showerror(tr(language, "error_generic"), tr(language, "lock_no_pin_for_db_key"))
            return 1
        stored_hash = LockManager.LOCK_FILE.read_text(encoding="utf-8").strip()
        temp_root = tk.Tk()
        temp_root.withdraw()
        dialog = LockScreenDialog(temp_root, language, mode="unlock", current_hash=stored_hash)
        temp_root.wait_window(dialog)
        temp_root.destroy()
        if not dialog.success:
            return 1
        pin = dialog.pin_var.get()
        cipher_key = SQLCipherManager.retrieve_key(pin)
        if cipher_key is None:
            messagebox.showerror(tr(language, "error_generic"), tr(language, "db_key_retrieve_failed"))
            return 1

    try:
        app = ExpensesApp(db_path="data/expenses.db", initial_language=language, cipher_key=cipher_key)
    except tk.TclError as error:
        print(tr(language, "gui_start_error", error=error))
        return 1

    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
