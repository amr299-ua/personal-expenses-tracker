"""Stats tab — category/month trees and embedded charts.

Extracted from gui.py to reduce monolith size.
"""

from __future__ import annotations

from tkinter import ttk
from typing import Any

from expenses_tracker.chart_panel import EmbeddedChartPanel
from expenses_tracker.i18n import format_number, is_rtl, tr


class StatsTab:
    """Builds and manages the statistics tab with trees and charts."""

    def __init__(self, parent: ttk.Frame, app: Any) -> None:
        self.parent = parent
        self.app = app
        self._build()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _build(self) -> None:
        top = ttk.Frame(self.parent, style="App.TFrame")
        top.pack(fill="both", expand=True)

        left = ttk.Frame(top, style="App.TFrame")
        right = ttk.Frame(top, style="App.TFrame")
        left.pack(fill="both", expand=True, side="left", padx=(0, 5))
        right.pack(fill="both", expand=True, side="left", padx=(5, 0))

        left_tree = ttk.LabelFrame(
            left,
            text=self.app._rtl_text(tr(self.app.language, "group_by_category")),
            padding=8,
            style="Card.TLabelframe",
        )
        left_tree.pack(fill="both", expand=False, side="top", pady=(0, 5))

        self.category_tree = ttk.Treeview(
            left_tree,
            columns=("category", "income", "expense", "balance"),
            show="headings",
            height=6,
        )
        self.category_tree.pack(fill="both", expand=True, side="left")

        text_anchor = "e" if is_rtl(self.app.language) else "w"

        self.category_tree.heading("category", text=self.app._rtl_text(tr(self.app.language, "col_category")))
        self.category_tree.heading("income", text=self.app._rtl_text(tr(self.app.language, "legend_income")))
        self.category_tree.heading("expense", text=self.app._rtl_text(tr(self.app.language, "legend_expense")))
        self.category_tree.heading("balance", text=self.app._rtl_text(tr(self.app.language, "legend_balance")))

        self.category_tree.column("category", width=160, anchor=text_anchor)  # type: ignore[call-overload]
        self.category_tree.column("income", width=100, anchor="e")
        self.category_tree.column("expense", width=100, anchor="e")
        self.category_tree.column("balance", width=100, anchor="e")

        cat_scroll = ttk.Scrollbar(left_tree, orient="vertical", command=self.category_tree.yview)
        cat_scroll.pack(fill="y", side="right")
        self.category_tree.configure(yscrollcommand=cat_scroll.set)

        left_chart = ttk.LabelFrame(
            left,
            text=self.app._rtl_text(tr(self.app.language, "chart_title_category")),
            padding=8,
            style="Card.TLabelframe",
        )
        left_chart.pack(fill="both", expand=True, side="top")
        chart_frame_category = ttk.Frame(left_chart, style="Card.TFrame")
        chart_frame_category.pack(fill="both", expand=True)

        right_tree = ttk.LabelFrame(
            right,
            text=self.app._rtl_text(tr(self.app.language, "group_by_month")),
            padding=8,
            style="Card.TLabelframe",
        )
        right_tree.pack(fill="both", expand=False, side="top", pady=(0, 5))

        self.month_tree = ttk.Treeview(
            right_tree,
            columns=("month", "income", "expense", "balance"),
            show="headings",
            height=6,
        )
        self.month_tree.pack(fill="both", expand=True, side="left")

        self.month_tree.heading("month", text=self.app._rtl_text(tr(self.app.language, "chart_x_month")))
        self.month_tree.heading("income", text=self.app._rtl_text(tr(self.app.language, "legend_income")))
        self.month_tree.heading("expense", text=self.app._rtl_text(tr(self.app.language, "legend_expense")))
        self.month_tree.heading("balance", text=self.app._rtl_text(tr(self.app.language, "legend_balance")))

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
            series_toggles,
            text=self.app._rtl_text(tr(self.app.language, "legend_income")),
            variable=self.app._show_income,
            command=self._refresh_chart_panel,
        )
        chk_income.pack(side="left", padx=(0, 8))
        self.app._apply_rtl_to_widget(chk_income)

        chk_expense = ttk.Checkbutton(
            series_toggles,
            text=self.app._rtl_text(tr(self.app.language, "legend_expense")),
            variable=self.app._show_expense,
            command=self._refresh_chart_panel,
        )
        chk_expense.pack(side="left", padx=(0, 8))
        self.app._apply_rtl_to_widget(chk_expense)

        chk_balance = ttk.Checkbutton(
            series_toggles,
            text=self.app._rtl_text(tr(self.app.language, "legend_balance")),
            variable=self.app._show_balance,
            command=self._refresh_chart_panel,
        )
        chk_balance.pack(side="left", padx=(0, 8))
        self.app._apply_rtl_to_widget(chk_balance)

        right_chart = ttk.LabelFrame(
            right,
            text=self.app._rtl_text(tr(self.app.language, "chart_title_month")),
            padding=8,
            style="Card.TLabelframe",
        )
        right_chart.pack(fill="both", expand=True, side="top")
        chart_frame_month = ttk.Frame(right_chart, style="Card.TFrame")
        chart_frame_month.pack(fill="both", expand=True)

        self._chart_panel = EmbeddedChartPanel(
            category_frame=chart_frame_category,
            month_frame=chart_frame_month,
            language=self.app.language,
            colors=self.app.theme_manager.colors,
            show_income=self.app._show_income,
            show_expense=self.app._show_expense,
            show_balance=self.app._show_balance,
            master=self.app,
        )

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def _load_stats(self) -> None:
        self.app._clear_tree(self.category_tree)
        self.app._clear_tree(self.month_tree)

        totals = self.app.transaction_service.get_totals_by_type()
        self.app._last_totals = totals
        self.app.balance_var.set(
            tr(self.app.language, "balance_label", amount=format_number(self.app.language, totals["balance"]))
        )
        self.app.income_var.set(
            tr(self.app.language, "income_total_label", amount=format_number(self.app.language, totals["income"]))
        )
        self.app.expense_var.set(
            tr(self.app.language, "expense_total_label", amount=format_number(self.app.language, totals["expense"]))
        )
        self.app._update_kpi_colors()

        for row in self.app.transaction_service.get_totals_by_category():
            self.category_tree.insert(
                "",
                "end",
                values=(
                    row["category"],
                    format_number(self.app.language, float(row["income"])),
                    format_number(self.app.language, float(row["expense"])),
                    format_number(self.app.language, float(row["balance"])),
                ),
            )

        for row in self.app.transaction_service.get_totals_by_month():
            self.month_tree.insert(
                "",
                "end",
                values=(
                    row["month"],
                    format_number(self.app.language, float(row["income"])),
                    format_number(self.app.language, float(row["expense"])),
                    format_number(self.app.language, float(row["balance"])),
                ),
            )

        self._refresh_chart_panel()

    # ------------------------------------------------------------------
    # Chart refresh
    # ------------------------------------------------------------------

    def _refresh_chart_panel(self) -> None:
        if hasattr(self, "_chart_panel"):
            self._chart_panel.update_charts(
                self.app.transaction_service.get_totals_by_category(),
                self.app.transaction_service.get_totals_by_month(),
            )
