from __future__ import annotations

import argparse
import logging
import tkinter as tk
from collections.abc import Callable
from datetime import date
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Any

from expenses_tracker.automation import ReportScheduler
from expenses_tracker.automation_dialog import AutomationDialog
from expenses_tracker.chart_viewer import ChartViewerDialog
from expenses_tracker.charts import PALETTES
from expenses_tracker.cloud_sync_dialog import CloudSyncDialog
from expenses_tracker.db import ExpenseDatabase
from expenses_tracker.di import container as _di_container
from expenses_tracker.gui_dialogs import CalendarDialog, ChartTypeDialog, LockScreenDialog
from expenses_tracker.i18n import (
    format_date,
    format_number,
    is_rtl,
    language_label,
    list_languages,
    normalize_language,
    reload_translations,
    reshape_for_rtl,
    tr,
)
from expenses_tracker.theme import ThemeManager
from expenses_tracker.security import (
    AuditLog as FileAuditLog,
)
from expenses_tracker.security import (
    LockManager,
    SQLCipherManager,
)
from expenses_tracker.services import (
    CategorySuggestionService,
    CurrencyService,
    DatabaseService,
    ExportService,
    TransactionService,
    UIStateService,
)
from expenses_tracker.tabs import BudgetTab, RegisterTab, StatsTab, TransactionsTab

logger = logging.getLogger("expenses_tracker.gui")

# Re-export utilities for backward compatibility and test imports
from expenses_tracker.utils import (
    category_options_for_type,
    filter_transaction_rows,
    safe_parse_date,
)

__all__ = [
    "category_options_for_type",
    "filter_transaction_rows",
    "safe_parse_date",
]


def _resolve_or_create(name: str, factory: Callable[[], Any]) -> Any:
    """Helper to resolve from DI container or create a new instance."""
    return _di_container.resolve(name) if _di_container.has(name) else factory()

class ExpensesApp(tk.Tk):
    def __init__(
        self,
        db_path: str = "data/expenses.db",
        initial_language: str | None = None,
        cipher_key: str | None = None,
        *,
        database: ExpenseDatabase | None = None,
        transaction_service: TransactionService | None = None,
        export_service: ExportService | None = None,
        state_service: UIStateService | None = None,
    ) -> None:
        super().__init__()

        self.state_service = state_service or _resolve_or_create("state_service", lambda: UIStateService("data/ui_state.json"))
        self._state = self.state_service.read()
        self.language = normalize_language(initial_language or str(self._state.get("language", "en")))

        self.geometry("1100x720")
        self.minsize(960, 640)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        saved_mode = str(self._state.get("theme_mode", "light"))
        theme_mode = saved_mode if saved_mode in {"light", "dark"} else "light"
        palette = str(self._state.get("palette", "default"))
        if palette not in PALETTES:
            palette = "default"
        self.theme_manager = ThemeManager(theme_mode=theme_mode, palette=palette)
        self.theme_manager.setup(self)

        self.database = database or _resolve_or_create(
            "database", lambda: ExpenseDatabase(db_path, cipher_key=cipher_key)
        )
        if not getattr(self.database, "_initialized", False):
            self.database.initialize()
            self.database._initialized = True  # type: ignore[attr-defined]

        self.transaction_service = transaction_service or _resolve_or_create(
            "transaction_service", lambda: TransactionService(self.database)
        )
        self.export_service = export_service or _resolve_or_create("export_service", lambda: ExportService())
        self.database_service = _resolve_or_create(
            "database_service", lambda: DatabaseService(self.database)
        )
        self.currency_service = _resolve_or_create(
            "currency_service", lambda: CurrencyService(self.database)
        )
        self.category_suggestion_service = _resolve_or_create(
            "category_suggestion_service", lambda: CategorySuggestionService()
        )

        # Load base currency from state
        base_currency = str(self._state.get("base_currency", "USD"))
        self.currency_service.set_base_currency(base_currency)

        self.scheduler = ReportScheduler(
            database=self.database,
            config_getter=self.database_service.get_automation_config,
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
        self.currency_var = tk.StringVar(value=str(self._state.get("currency", "USD")))
        self.editing_transaction_id: int | None = None
        self.save_button_var = tk.StringVar()

        # Pagination state
        self._page_size = 100
        self._current_page = 0
        self._total_pages = 1

        # Embedded chart canvases

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

        self.palette_var = tk.StringVar(value=self.theme_manager.palette)
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

        if not SQLCipherManager.is_encrypted_db(Path(self.database_service.db_path)):
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
        tab_budget = ttk.Frame(notebook, padding=12, style="App.TFrame")

        notebook.add(tab_register, text=tr(self.language, "tab_register"))
        notebook.add(tab_transactions, text=tr(self.language, "tab_transactions"))
        notebook.add(tab_stats, text=tr(self.language, "tab_stats"))
        notebook.add(tab_budget, text=tr(self.language, "tab_budget"))
        self._tab_register = tab_register

        self._build_register_tab(tab_register)
        self._build_transactions_tab(tab_transactions)
        self._build_stats_tab(tab_stats)
        self._build_budget_tab(tab_budget)

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
        self._register_tab = RegisterTab(parent, self)
    def _build_transactions_tab(self, parent: ttk.Frame) -> None:
        self._transactions_tab = TransactionsTab(parent, self)
    def _build_stats_tab(self, parent: ttk.Frame) -> None:
        self._stats_tab = StatsTab(parent, self)
    def _build_budget_tab(self, parent: ttk.Frame) -> None:
        self._budget_tab = BudgetTab(parent, self)

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

    def _refresh_all(self) -> None:
        self._transactions_tab._load_transactions()
        self._stats_tab._load_stats()
        if hasattr(self, "_budget_tab"):
            self._budget_tab._load_budgets()

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

    def _load_selected_into_form(self) -> None:
        row = self._transactions_tab.selected_transaction_data()
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
        row = self._transactions_tab.selected_transaction_data()
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
            deleted = self.transaction_service.delete(int(row["id"]))
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

    @staticmethod
    def _safe_parse_date(raw_value: str) -> date | None:
        return safe_parse_date(raw_value)

    def _read_ui_state(self) -> dict[str, Any]:
        return self.state_service.read()

    def _save_ui_state(self) -> None:
        data = {
            "language": self.language,
            "theme_mode": self.theme_manager.theme_mode,
            "palette": self.theme_manager.palette,
            "search": self.search_var.get(),
            "register_type_key": self.register_type_key,
            "filter_type_key": self.filter_type_key,
            "filter_category": self.filter_category_var.get(),
            "filter_from": self.filter_from_var.get(),
            "filter_to": self.filter_to_var.get(),
            "sort_column": self.sort_column,
            "sort_desc": self.sort_desc,
            "base_currency": self.currency_service.base_currency,
            "currency": self.currency_var.get(),
        }
        self.state_service.write(data)

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
            backup_path = self.database_service.create_backup()
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
        if SQLCipherManager.is_encrypted_db(Path(self.database_service.db_path)):
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
            SQLCipherManager.migrate_to_encrypted(Path(self.database_service.db_path), key)
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
                background=self.theme_manager.colors["input_bg"],
                foreground=self.theme_manager.colors["text"],
                insertbackground=self.theme_manager.colors["text"],
            )
        if hasattr(self, "_transactions_tab"):
            self._transactions_tab.transactions_tree.tag_configure("income", foreground=self.theme_manager.colors["positive"])
            self._transactions_tab.transactions_tree.tag_configure("expense", foreground=self.theme_manager.colors["negative"])
        if hasattr(self, "_stats_tab"):
            self._stats_tab._chart_panel.set_colors(self.theme_manager.colors)
        self._update_kpi_colors()

    def _update_theme_button_text(self) -> None:
        if hasattr(self, "theme_button"):
            if self.theme_manager.theme_mode == "light":
                self.theme_button.configure(text=tr(self.language, "btn_dark_mode"))
            else:
                self.theme_button.configure(text=tr(self.language, "btn_light_mode"))

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
        self.bind_all("<Control-4>", lambda _event: self._select_tab(3))

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

    @staticmethod
    def _set_indicator(label: ttk.Label | None, text: str, color: str = "") -> None:
        if label is None:
            return
        label.configure(text=text, foreground=color if color else label.master["style"])

    def _update_kpi_colors(self) -> None:
        if not hasattr(self, "balance_label"):
            return

        balance = float(self._last_totals.get("balance", 0.0))
        self.balance_label.configure(
            foreground=self.theme_manager.colors["positive"] if balance >= 0 else self.theme_manager.colors["negative"]
        )

        if hasattr(self, "income_label"):
            self.income_label.configure(foreground=self.theme_manager.colors["positive"])
        if hasattr(self, "expense_label"):
            self.expense_label.configure(foreground=self.theme_manager.colors["negative"])

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
                budget_rows = self.transaction_service.get_budget_vs_actual(month_str)

            ChartViewerDialog(
                parent=self,
                language=self.language,
                palette=self.palette,
                kind=dialog.selected_kind,
                category_rows=self.transaction_service.get_totals_by_category(),
                month_rows=self.transaction_service.get_totals_by_month(),
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
        if new_palette == self.theme_manager.palette:
            return
        self.theme_manager.set_palette(new_palette)
        if hasattr(self, "_stats_tab"):
            self._stats_tab._refresh_chart_panel()
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
            db_path=str(self.database_service.db_path),
            encryption_key=encryption_key,
        )

    def _export(self, fmt: str) -> None:
        all_transactions = self.transaction_service.fetch_all()
        selected_type_db = "" if self.filter_type_key == "all" else self.filter_type_key
        date_from = self.transaction_service.parse_date(self.filter_from_var.get())
        date_to = self.transaction_service.parse_date(self.filter_to_var.get())
        transactions = self.transaction_service.filter_rows(
            all_transactions,
            search=self.search_var.get(),
            selected_type_db=selected_type_db,
            selected_category=self.filter_category_var.get(),
            all_label=self._all_label,
            date_from=date_from,
            date_to=date_to,
            type_db_to_display=self._type_db_to_display,
        )
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
        all_transactions = self.transaction_service.fetch_all()
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

    # Wire DI container with production services
    database = ExpenseDatabase(str(db_path), cipher_key=cipher_key)
    database.initialize()
    if not _di_container.has("database"):
        _di_container.register("database", lambda: database, singleton=True)
        _di_container.register("transaction_service", lambda: TransactionService(database), singleton=True)
        _di_container.register("export_service", lambda: ExportService(), singleton=True)
        _di_container.register("state_service", lambda: UIStateService("data/ui_state.json"), singleton=True)
        _di_container.register("database_service", lambda: DatabaseService(database), singleton=True)
        _di_container.register("currency_service", lambda: CurrencyService(database), singleton=True)
        _di_container.register("category_suggestion_service", lambda: CategorySuggestionService(), singleton=True)

    try:
        app = ExpensesApp(
            db_path="data/expenses.db",
            initial_language=language,
            cipher_key=cipher_key,
            database=_di_container.resolve("database"),
            transaction_service=_di_container.resolve("transaction_service"),
            export_service=_di_container.resolve("export_service"),
            state_service=_di_container.resolve("state_service"),
        )
    except tk.TclError as error:
        print(tr(language, "gui_start_error", error=error))
        return 1

    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
