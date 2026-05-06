"""Budget tab — monthly budget management with progress bars and alerts.

Extracted from gui.py to keep components decoupled.
"""

from __future__ import annotations

import tkinter as tk
from datetime import date
from tkinter import messagebox, ttk
from typing import Any

from expenses_tracker.i18n import format_number, get_locale_config, is_rtl, tr
from expenses_tracker.schemas import BudgetInput


class BudgetTab:
    """Builds and manages the budget management tab."""

    def __init__(self, parent: ttk.Frame, app: Any) -> None:
        self.parent = parent
        self.app = app
        self._selected_budget_id: int | None = None
        self._build()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _build(self) -> None:
        controls = ttk.Frame(self.parent, style="Card.TFrame", padding=12)
        controls.pack(fill="x", padx=0, pady=(0, 8))

        label_sticky = "e" if is_rtl(self.app.language) else "w"

        lbl_month = ttk.Label(controls)
        self.app._set_i18n_text(lbl_month, "label_month")
        lbl_month.grid(row=0, column=0, sticky=label_sticky, padx=(0, 8))
        self.month_var = tk.StringVar(value=date.today().strftime("%Y-%m"))
        month_entry = ttk.Entry(controls, textvariable=self.month_var, width=12)
        month_entry.grid(row=0, column=1, sticky="we", padx=(0, 16))
        month_entry.bind("<KeyRelease>", lambda _event: self._load_budgets())
        self.month_entry = month_entry

        lbl_category = ttk.Label(controls)
        self.app._set_i18n_text(lbl_category, "label_category")
        lbl_category.grid(row=0, column=2, sticky=label_sticky, padx=(0, 8))
        self.budget_category_var = tk.StringVar()
        self.category_box = ttk.Combobox(
            controls,
            textvariable=self.budget_category_var,
            values=[],
            state="normal",
            width=18,
        )
        self.category_box.grid(row=0, column=3, sticky="we", padx=(0, 16))

        lbl_amount = ttk.Label(controls)
        self.app._set_i18n_text(lbl_amount, "label_amount")
        lbl_amount.grid(row=0, column=4, sticky=label_sticky, padx=(0, 8))
        self.planned_var = tk.StringVar()
        self.planned_entry = ttk.Entry(controls, textvariable=self.planned_var, width=14)
        self.planned_entry.grid(row=0, column=5, sticky="we", padx=(0, 16))

        btn_save = ttk.Button(
            controls,
            style="Accent.TButton",
            command=self._save_budget,
        )
        self.app._set_i18n_text(btn_save, "btn_save")
        btn_save.grid(row=0, column=6, padx=(0, 6))
        self.app._apply_rtl_to_widget(btn_save)

        btn_delete = ttk.Button(
            controls,
            style="Ghost.TButton",
            command=self._delete_budget,
        )
        self.app._set_i18n_text(btn_delete, "btn_delete")
        btn_delete.grid(row=0, column=7, padx=(0, 6))
        self.app._apply_rtl_to_widget(btn_delete)

        btn_clear = ttk.Button(
            controls,
            style="Ghost.TButton",
            command=self._clear_form,
        )
        self.app._set_i18n_text(btn_clear, "btn_clear")
        btn_clear.grid(row=0, column=8)
        self.app._apply_rtl_to_widget(btn_clear)

        for col in range(6):
            controls.columnconfigure(col, weight=1)

        tree_frame = ttk.Frame(self.parent, style="Card.TFrame", padding=8)
        tree_frame.pack(fill="both", expand=True)

        columns = ("category", "planned", "actual", "difference", "percent", "status")
        self.budget_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=16)
        self.budget_tree.pack(fill="both", expand=True, side="left")

        text_anchor = "e" if is_rtl(self.app.language) else "w"
        self.budget_tree.heading("category", text=self.app._rtl_text(tr(self.app.language, "col_category")))
        self.budget_tree.heading("planned", text=self.app._rtl_text(tr(self.app.language, "legend_planned")))
        self.budget_tree.heading("actual", text=self.app._rtl_text(tr(self.app.language, "legend_actual")))
        self.budget_tree.heading("difference", text=self.app._rtl_text(tr(self.app.language, "col_difference")))
        self.budget_tree.heading("percent", text=self.app._rtl_text(tr(self.app.language, "col_percent")))
        self.budget_tree.heading("status", text=self.app._rtl_text(tr(self.app.language, "col_status")))

        self.budget_tree.column("category", width=160, anchor=text_anchor)  # type: ignore[call-overload]
        self.budget_tree.column("planned", width=100, anchor="e")
        self.budget_tree.column("actual", width=100, anchor="e")
        self.budget_tree.column("difference", width=100, anchor="e")
        self.budget_tree.column("percent", width=120, anchor="center")
        self.budget_tree.column("status", width=100, anchor="center")

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.budget_tree.yview)
        scrollbar.pack(fill="y", side="right")
        self.budget_tree.configure(yscrollcommand=scrollbar.set)

        self.budget_tree.bind("<<TreeviewSelect>>", lambda _event: self._on_budget_select())

        self._load_budgets()

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def _load_budgets(self) -> None:
        self._clear_tree(self.budget_tree)
        month = self.month_var.get().strip()
        if len(month) != 7:
            return

        rows = self.app.transaction_service.get_budget_vs_actual(month)

        # Collect categories for combobox
        all_categories = sorted({r["category"] for r in rows})
        self.category_box.configure(values=all_categories)

        for row in rows:
            planned = float(row.get("planned", 0.0))
            actual = float(row.get("actual", 0.0))
            difference = float(row.get("difference", 0.0))
            percent = (actual / planned * 100) if planned > 0 else 0.0

            if planned > 0 and actual > planned:
                status = tr(self.app.language, "budget_over")
                tag = "over"
            elif planned > 0 and percent >= 80:
                status = tr(self.app.language, "budget_warning")
                tag = "warning"
            else:
                status = tr(self.app.language, "budget_ok")
                tag = "ok"

            self.budget_tree.insert(
                "",
                "end",
                values=(
                    row["category"],
                    format_number(self.app.language, planned),
                    format_number(self.app.language, actual),
                    format_number(self.app.language, difference),
                    f"{percent:.1f}%",
                    status,
                ),
                tags=(tag,),
            )

        self.budget_tree.tag_configure("over", foreground=self.app.theme_manager.colors["negative"])
        self.budget_tree.tag_configure("warning", foreground="#f9a825")
        self.budget_tree.tag_configure("ok", foreground=self.app.theme_manager.colors["positive"])

    def update_texts(self) -> None:
        """Refresh translated budget headings and field direction."""
        if not hasattr(self, "budget_tree") or not self.app._widget_exists(self.budget_tree):
            return
        self.budget_tree.heading("category", text=self.app._rtl_text(tr(self.app.language, "col_category")))
        self.budget_tree.heading("planned", text=self.app._rtl_text(tr(self.app.language, "legend_planned")))
        self.budget_tree.heading("actual", text=self.app._rtl_text(tr(self.app.language, "legend_actual")))
        self.budget_tree.heading("difference", text=self.app._rtl_text(tr(self.app.language, "col_difference")))
        self.budget_tree.heading("percent", text=self.app._rtl_text(tr(self.app.language, "col_percent")))
        self.budget_tree.heading("status", text=self.app._rtl_text(tr(self.app.language, "col_status")))
        self.app._apply_rtl_to_widget(self.category_box)
        self.app._apply_rtl_to_widget(self.month_entry)
        self.app._apply_rtl_to_widget(self.planned_entry)

    def apply_theme(self) -> None:
        """Apply runtime theme colors to budget status tags."""
        if not hasattr(self, "budget_tree") or not self.app._widget_exists(self.budget_tree):
            return
        self.budget_tree.tag_configure("over", foreground=self.app.theme_manager.colors["negative"])
        self.budget_tree.tag_configure("warning", foreground="#f9a825")
        self.budget_tree.tag_configure("ok", foreground=self.app.theme_manager.colors["positive"])

    # ------------------------------------------------------------------
    # Form logic
    # ------------------------------------------------------------------

    def _on_budget_select(self) -> None:
        selection = self.budget_tree.selection()
        if not selection:
            return
        values = self.budget_tree.item(selection[0], "values")
        if len(values) < 6:
            return
        self.budget_category_var.set(str(values[0]))
        # Parse planned amount back from formatted string (remove separators)
        locale_cfg = get_locale_config(self.app.language)
        thousands = locale_cfg.get("thousands_separator", ",")
        decimal = locale_cfg.get("decimal_separator", ".")
        planned_str = str(values[1]).replace(thousands, "").replace(decimal, ".")
        self.planned_var.set(planned_str)
        self._selected_budget_id = None

    def _save_budget(self) -> None:
        category = self.budget_category_var.get().strip()
        month = self.month_var.get().strip()
        planned_str = self.planned_var.get().strip()
        if not category or not month or not planned_str:
            messagebox.showwarning(
                tr(self.app.language, "warning_no_data"),
                tr(self.app.language, "budget_fill_all"),
                parent=self.app,
            )
            return
        try:
            planned = float(planned_str)
        except ValueError:
            messagebox.showerror(
                tr(self.app.language, "error_invalid_data"),
                tr(self.app.language, "amount_positive"),
                parent=self.app,
            )
            return

        try:
            budget_input = BudgetInput(category=category, month=month, planned_amount=planned)
            self.app.transaction_service.add_budget(budget_input)
        except ValueError as error:
            messagebox.showerror(
                tr(self.app.language, "error_invalid_data"),
                str(error),
                parent=self.app,
            )
            return

        self._clear_form()
        self._load_budgets()

    def _delete_budget(self) -> None:
        selection = self.budget_tree.selection()
        if not selection:
            messagebox.showwarning(
                tr(self.app.language, "warning_select_title"),
                tr(self.app.language, "warning_select_budget"),
                parent=self.app,
            )
            return

        values = self.budget_tree.item(selection[0], "values")
        category = str(values[0])
        month = self.month_var.get().strip()

        confirm = messagebox.askyesno(
            tr(self.app.language, "confirm_delete_title"),
            tr(self.app.language, "confirm_delete_budget", category=category, month=month),
            parent=self.app,
        )
        if not confirm:
            return

        # Find budget ID by category+month
        budgets = self.app.transaction_service.fetch_budgets(month=month)
        budget_id = None
        for b in budgets:
            if b["category"] == category:
                budget_id = b["id"]
                break

        if budget_id is None:
            messagebox.showerror(
                tr(self.app.language, "error_generic"),
                tr(self.app.language, "delete_not_found"),
                parent=self.app,
            )
            return

        try:
            deleted = self.app.transaction_service.delete_budget(budget_id)
        except Exception as error:
            messagebox.showerror(
                tr(self.app.language, "error_generic"),
                tr(self.app.language, "delete_failed", error=error),
                parent=self.app,
            )
            return

        if not deleted:
            messagebox.showerror(
                tr(self.app.language, "error_generic"),
                tr(self.app.language, "delete_not_found"),
                parent=self.app,
            )
            return

        messagebox.showinfo(
            tr(self.app.language, "success"),
            tr(self.app.language, "delete_success"),
            parent=self.app,
        )
        self._clear_form()
        self._load_budgets()

    def _clear_form(self) -> None:
        self.budget_category_var.set("")
        self.planned_var.set("")
        self._selected_budget_id = None
        for item in self.budget_tree.selection():
            self.budget_tree.selection_remove(item)

    @staticmethod
    def _clear_tree(tree: ttk.Treeview) -> None:
        for item in tree.get_children():
            tree.delete(item)
