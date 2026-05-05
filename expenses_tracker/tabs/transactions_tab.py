"""Transactions tab — table, filters, sorting and pagination.

Extracted from gui.py to reduce monolith size.
"""

from __future__ import annotations

import tkinter as tk
from datetime import date, timedelta
from tkinter import ttk
from typing import Any

from expenses_tracker.i18n import format_date, format_number, is_rtl, tr
from expenses_tracker.utils import safe_parse_date


class TransactionsTab:
    """Builds and manages the transactions list with filters and pagination."""

    def __init__(self, parent: ttk.Frame, app: Any) -> None:
        self.parent = parent
        self.app = app
        self._build()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _build(self) -> None:
        filters = ttk.LabelFrame(
            self.parent,
            text=self.app._rtl_text(tr(self.app.language, "filters_title")),
            padding=10,
            style="Card.TLabelframe",
        )
        filters.pack(fill="x", padx=0, pady=(0, 8))

        label_sticky = "e" if is_rtl(self.app.language) else "w"

        ttk.Label(
            filters,
            text=self.app._rtl_text(tr(self.app.language, "label_search")),
        ).grid(row=0, column=0, sticky=label_sticky)
        ttk.Label(
            filters,
            text=self.app._rtl_text(tr(self.app.language, "label_type")),
        ).grid(row=0, column=1, sticky=label_sticky)
        ttk.Label(
            filters,
            text=self.app._rtl_text(tr(self.app.language, "label_category")),
        ).grid(row=0, column=2, sticky=label_sticky)
        ttk.Label(
            filters,
            text=self.app._rtl_text(tr(self.app.language, "label_from")),
        ).grid(row=0, column=3, sticky=label_sticky)
        ttk.Label(
            filters,
            text=self.app._rtl_text(tr(self.app.language, "label_to")),
        ).grid(row=0, column=4, sticky=label_sticky)

        search_entry = ttk.Entry(
            filters,
            textvariable=self.app.search_var,
            justify="right" if is_rtl(self.app.language) else "left",
        )
        search_entry.grid(row=1, column=0, sticky="we", padx=(0, 8), pady=(2, 0))

        type_box = ttk.Combobox(
            filters,
            textvariable=self.app.filter_type_var,
            values=list(self.app._filter_display_to_key.keys()),
            state="readonly",
            width=10,
        )
        type_box.grid(row=1, column=1, sticky="we", padx=(0, 8), pady=(2, 0))
        type_box.bind("<<ComboboxSelected>>", lambda _event: self._on_filter_change())
        self.app._apply_rtl_to_widget(type_box)

        self.app.category_filter_box = ttk.Combobox(
            filters,
            textvariable=self.app.filter_category_var,
            values=[self.app._all_label],
            state="readonly",
            width=18,
        )
        self.app.category_filter_box.grid(row=1, column=2, sticky="we", padx=(0, 8), pady=(2, 0))
        self.app.category_filter_box.bind("<<ComboboxSelected>>", lambda _event: self._on_filter_change())
        self.app._apply_rtl_to_widget(self.app.category_filter_box)

        from_field = ttk.Frame(filters)
        from_field.grid(row=1, column=3, sticky="we", padx=(0, 8), pady=(2, 0))
        from_entry = ttk.Entry(
            from_field,
            textvariable=self.app.filter_from_var,
            width=14,
            justify="right" if is_rtl(self.app.language) else "left",
        )
        from_entry.pack(side="left", fill="x", expand=True)
        from_entry.bind("<KeyRelease>", lambda _event: self._on_filter_change())
        ttk.Button(
            from_field,
            text="...",
            width=3,
            command=lambda: self.app._open_calendar_for_var(
                self.app.filter_from_var,
                tr(self.app.language, "label_from"),
                on_change=self._on_filter_change,
            ),
        ).pack(side="left", padx=(4, 0))

        to_field = ttk.Frame(filters)
        to_field.grid(row=1, column=4, sticky="we", padx=(0, 8), pady=(2, 0))
        to_entry = ttk.Entry(
            to_field,
            textvariable=self.app.filter_to_var,
            width=14,
            justify="right" if is_rtl(self.app.language) else "left",
        )
        to_entry.pack(side="left", fill="x", expand=True)
        to_entry.bind("<KeyRelease>", lambda _event: self._on_filter_change())
        ttk.Button(
            to_field,
            text="...",
            width=3,
            command=lambda: self.app._open_calendar_for_var(
                self.app.filter_to_var,
                tr(self.app.language, "label_to"),
                on_change=self._on_filter_change,
            ),
        ).pack(side="left", padx=(4, 0))

        filter_actions = ttk.Frame(filters, style="Card.TFrame")
        filter_actions.grid(row=1, column=5, sticky="e")
        btn_apply = ttk.Button(
            filter_actions,
            text=tr(self.app.language, "btn_apply"),
            style="Accent.TButton",
            command=self._load_transactions,
        )
        btn_apply.pack(side="left", padx=3)
        self.app._apply_rtl_to_widget(btn_apply)

        btn_clear_filters = ttk.Button(
            filter_actions,
            text=tr(self.app.language, "btn_clear"),
            style="Ghost.TButton",
            command=self._clear_filters,
        )
        btn_clear_filters.pack(side="left", padx=3)
        self.app._apply_rtl_to_widget(btn_clear_filters)

        quick_ranges = ttk.Frame(filters, style="Card.TFrame")
        quick_ranges.grid(row=2, column=0, columnspan=6, sticky=label_sticky, pady=(8, 0))
        ttk.Label(
            quick_ranges,
            text=self.app._rtl_text(tr(self.app.language, "label_quick_dates")),
        ).pack(side="left", padx=(0, 6))
        for preset in ["btn_today", "btn_week", "btn_month", "btn_year", "btn_all"]:
            btn = ttk.Button(
                quick_ranges,
                text=tr(self.app.language, preset),
                style="Ghost.TButton",
                command=lambda p=preset: self._apply_date_preset(p.replace("btn_", "")),  # type: ignore[misc]
            )
            btn.pack(side="left", padx=2)
            self.app._apply_rtl_to_widget(btn)

        for column_index in range(5):
            filters.columnconfigure(column_index, weight=1)

        self.app.search_var.trace_add("write", self._on_search_change)
        self.app.search_entry = search_entry

        actions_row = ttk.Frame(self.parent, style="App.TFrame")
        actions_row.pack(fill="x", pady=(0, 6))
        btn_load = ttk.Button(
            actions_row,
            text=tr(self.app.language, "btn_load_form"),
            style="Ghost.TButton",
            command=self.app._load_selected_into_form,
        )
        btn_load.pack(side="left", padx=(0, 6))
        self.app._apply_rtl_to_widget(btn_load)

        btn_delete = ttk.Button(
            actions_row,
            text=tr(self.app.language, "btn_delete"),
            style="Ghost.TButton",
            command=self.app._delete_selected_transaction,
        )
        btn_delete.pack(side="left")
        self.app._apply_rtl_to_widget(btn_delete)

        count_side = "left" if is_rtl(self.app.language) else "right"
        ttk.Label(actions_row, textvariable=self.app.filtered_count_var, style="Muted.TLabel").pack(side=count_side)  # type: ignore[arg-type]

        tree_area = ttk.Frame(self.parent, style="Card.TFrame", padding=8)
        tree_area.pack(fill="both", expand=True)

        columns = ("id", "date", "type", "category", "amount", "description")
        self.transactions_tree = ttk.Treeview(tree_area, columns=columns, show="headings", height=20)
        self.transactions_tree.pack(fill="both", expand=True, side="left")

        text_anchor = "e" if is_rtl(self.app.language) else "w"
        for column_name, title in self.app._column_titles.items():
            self.transactions_tree.heading(
                column_name,
                text=self.app._rtl_text(title),
                command=lambda selected=column_name: self._on_sort_change(selected),  # type: ignore[misc]
            )

        self.transactions_tree.column("id", width=60, anchor="center")
        self.transactions_tree.column("date", width=120, anchor="center")
        self.transactions_tree.column("type", width=100, anchor="center")
        self.transactions_tree.column("category", width=160, anchor=text_anchor)  # type: ignore[call-overload]
        self.transactions_tree.column("amount", width=100, anchor="e")
        self.transactions_tree.column("description", width=420, anchor=text_anchor)  # type: ignore[call-overload]

        self.transactions_tree.tag_configure("income", foreground=self.app.theme_manager.colors["positive"])
        self.transactions_tree.tag_configure("expense", foreground=self.app.theme_manager.colors["negative"])
        self.transactions_tree.bind("<Double-1>", lambda _event: self.app._load_selected_into_form())

        scrollbar = ttk.Scrollbar(tree_area, orient="vertical", command=self.transactions_tree.yview)
        scrollbar.pack(fill="y", side="right")
        self.transactions_tree.configure(yscrollcommand=scrollbar.set)
        self._refresh_sort_headers()

        pagination = ttk.Frame(self.parent, style="App.TFrame")
        pagination.pack(fill="x", pady=(6, 0))
        self.app._btn_prev = ttk.Button(
            pagination,
            text="<",
            width=3,
            command=lambda: self._go_to_page(-1),
        )
        self.app._btn_prev.pack(side="left", padx=(0, 6))
        self.app._page_label_var = tk.StringVar(value="1 / 1")
        ttk.Label(pagination, textvariable=self.app._page_label_var, style="Muted.TLabel").pack(side="left")
        self.app._btn_next = ttk.Button(
            pagination,
            text=">",
            width=3,
            command=lambda: self._go_to_page(1),
        )
        self.app._btn_next.pack(side="left", padx=(6, 0))

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def _load_transactions(self) -> None:
        self._clear_tree(self.transactions_tree)
        rows = self.app.transaction_service.fetch_all()
        self._sync_category_filter(rows)

        selected_type_db = "" if self.app.filter_type_key == "all" else self.app.filter_type_key
        date_from = self.app.transaction_service.parse_date(self.app.filter_from_var.get())
        date_to = self.app.transaction_service.parse_date(self.app.filter_to_var.get())

        filtered_rows = self.app.transaction_service.filter_rows(
            rows,
            search=self.app.search_var.get(),
            selected_type_db=selected_type_db,
            selected_category=self.app.filter_category_var.get(),
            all_label=self.app._all_label,
            date_from=date_from,
            date_to=date_to,
            type_db_to_display=self.app._type_db_to_display,
        )
        sorted_rows = self.app.transaction_service.sort_rows(filtered_rows, self.app.sort_column, self.app.sort_desc)

        page_rows, self.app._total_pages, self.app._current_page = self.app.transaction_service.paginate(
            sorted_rows, self.app._current_page, self.app._page_size
        )
        total = len(sorted_rows)

        for row in page_rows:
            tag = "income" if row["transaction_type"] == "income" else "expense"
            tx_date = safe_parse_date(str(row["transaction_date"]))
            display_date = format_date(self.app.language, tx_date) if tx_date else str(row["transaction_date"])
            self.transactions_tree.insert(
                "",
                "end",
                values=(
                    row["id"],
                    display_date,
                    self.app._type_db_to_display.get(str(row["transaction_type"]), str(row["transaction_type"])),
                    row["category"],
                    format_number(self.app.language, float(row["amount"])),
                    row["description"],
                ),
                tags=(tag,),
            )

        self.app.filtered_count_var.set(
            tr(
                self.app.language,
                "showing_rows_paginated",
                filtered=len(page_rows),
                total=total,
                page=self.app._current_page + 1,
                pages=self.app._total_pages,
            )
        )

        if hasattr(self.app, "_page_label_var"):
            self.app._page_label_var.set(f"{self.app._current_page + 1} / {self.app._total_pages}")
        if hasattr(self.app, "_btn_prev"):
            self.app._btn_prev.configure(state="normal" if self.app._current_page > 0 else "disabled")
        if hasattr(self.app, "_btn_next"):
            self.app._btn_next.configure(
                state="normal" if self.app._current_page < self.app._total_pages - 1 else "disabled",
            )

    # ------------------------------------------------------------------
    # Filtering
    # ------------------------------------------------------------------

    def _on_search_change(self, *_: object) -> None:
        self._on_filter_change()

    def _on_filter_change(self) -> None:
        self.app.filter_type_key = self.app._filter_display_to_key.get(self.app.filter_type_var.get().strip(), "all")
        self.app._current_page = 0
        self._load_transactions()
        self.app._save_ui_state()

    def _clear_filters(self) -> None:
        self.app.search_var.set("")
        self.app.filter_type_key = "all"
        self.app.filter_type_var.set(self.app._filter_key_to_display[self.app.filter_type_key])
        self.app.filter_category_var.set(self.app._all_label)
        self.app.filter_from_var.set("")
        self.app.filter_to_var.set("")
        self._on_filter_change()

    def _apply_date_preset(self, preset: str) -> None:
        today = date.today()

        if preset == "all":
            self.app.filter_from_var.set("")
            self.app.filter_to_var.set("")
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

        self.app.filter_from_var.set(start_date.isoformat())
        self.app.filter_to_var.set(end_date.isoformat())
        self._on_filter_change()

    def _sync_category_filter(self, rows: list[dict[str, object]]) -> None:
        categories = sorted({str(row["category"]) for row in rows})
        values = [self.app._all_label, *categories]
        self.app.category_filter_box.configure(values=values)

        current = self.app.filter_category_var.get().strip()
        if not current or current not in values:
            self.app.filter_category_var.set(self.app._all_label)

    # ------------------------------------------------------------------
    # Sorting
    # ------------------------------------------------------------------

    def _on_sort_change(self, column_name: str) -> None:
        if column_name == self.app.sort_column:
            self.app.sort_desc = not self.app.sort_desc
        else:
            self.app.sort_column = column_name
            self.app.sort_desc = False

        self._refresh_sort_headers()
        self._load_transactions()
        self.app._save_ui_state()

    def _refresh_sort_headers(self) -> None:
        arrow = "▼" if self.app.sort_desc else "▲"
        for column_name, title in self.app._column_titles.items():
            label = title if column_name != self.app.sort_column else f"{title} {arrow}"
            self.transactions_tree.heading(
                column_name,
                text=label,
                command=lambda selected=column_name: self._on_sort_change(selected),
            )

    # ------------------------------------------------------------------
    # Pagination
    # ------------------------------------------------------------------

    def _go_to_page(self, delta: int) -> None:
        new_page = self.app._current_page + delta
        if 0 <= new_page < self.app._total_pages:
            self.app._current_page = new_page
            self._load_transactions()

    # ------------------------------------------------------------------
    # Selection helpers (used by App)
    # ------------------------------------------------------------------

    def selected_transaction_data(self) -> dict[str, str] | None:
        """Return the currently selected transaction as a dict."""
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

    @staticmethod
    def _clear_tree(tree: ttk.Treeview) -> None:
        for item in tree.get_children():
            tree.delete(item)
