"""Register tab — transaction entry form and validation.

Extracted from gui.py to reduce monolith size.
"""

from __future__ import annotations

import tkinter as tk
from datetime import date
from tkinter import messagebox, ttk
from typing import Any

from expenses_tracker.db import TransactionInput
from expenses_tracker.i18n import is_rtl, tr


class RegisterTab:
    """Builds and manages the transaction registration form."""

    def __init__(self, parent: ttk.Frame, app: Any) -> None:
        self.parent = parent
        self.app = app
        self._build()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _build(self) -> None:
        form = ttk.Frame(self.parent, style="Card.TFrame", padding=12)
        form.pack(fill="x", padx=8, pady=6)

        label_sticky = "e" if is_rtl(self.app.language) else "w"

        lbl_type = ttk.Label(form, text=self.app._rtl_text(tr(self.app.language, "label_type")))
        lbl_type.grid(row=0, column=0, sticky=label_sticky, pady=4)
        lbl_amount = ttk.Label(form, text=self.app._rtl_text(tr(self.app.language, "label_amount")))
        lbl_amount.grid(row=0, column=1, sticky=label_sticky, pady=4)
        lbl_category = ttk.Label(form, text=self.app._rtl_text(tr(self.app.language, "label_category")))
        lbl_category.grid(row=0, column=2, sticky=label_sticky, pady=4)
        lbl_date = ttk.Label(form, text=self.app._rtl_text(tr(self.app.language, "label_date")))
        lbl_date.grid(row=0, column=3, sticky=label_sticky, pady=4)
        lbl_currency = ttk.Label(form, text=self.app._rtl_text(tr(self.app.language, "label_currency")))
        lbl_currency.grid(row=0, column=4, sticky=label_sticky, pady=4)

        type_box = ttk.Combobox(
            form,
            textvariable=self.app.type_var,
            values=list(self.app._type_display_to_db.keys()),
            state="readonly",
            width=12,
        )
        type_box.grid(row=1, column=0, sticky="we", padx=(0, 10), pady=(0, 2))
        type_box.bind("<<ComboboxSelected>>", lambda _event: self._on_register_type_changed())
        self.app._apply_rtl_to_widget(type_box)

        amount_field = ttk.Frame(form)
        amount_field.grid(row=1, column=1, sticky="we", padx=(0, 10), pady=(0, 2))
        amount_justify = "right" if is_rtl(self.app.language) else "left"
        self.app.amount_entry = ttk.Entry(
            amount_field, textvariable=self.app.amount_var, width=16, justify=amount_justify  # type: ignore[arg-type]
        )
        self.app.amount_entry.pack(side="left", fill="x", expand=True)
        self.app._amount_indicator = ttk.Label(amount_field, text="", width=2)
        self.app._amount_indicator.pack(side="left", padx=(4, 0))

        cat_field = ttk.Frame(form)
        cat_field.grid(row=1, column=2, sticky="we", padx=(0, 10), pady=(0, 2))
        self.app.category_box = ttk.Combobox(
            cat_field,
            textvariable=self.app.category_var,
            values=[],
            state="normal",
            width=20,
        )
        self.app.category_box.pack(side="left", fill="x", expand=True)
        self.app._apply_rtl_to_widget(self.app.category_box)
        self.app._category_indicator = ttk.Label(cat_field, text="", width=2)
        self.app._category_indicator.pack(side="left", padx=(4, 0))

        date_field = ttk.Frame(form)
        date_field.grid(row=1, column=3, sticky="we", padx=(0, 10), pady=(0, 2))
        date_justify = "right" if is_rtl(self.app.language) else "left"
        self.app.date_entry = ttk.Entry(
            date_field, textvariable=self.app.date_var, width=14, justify=date_justify  # type: ignore[arg-type]
        )
        self.app.date_entry.pack(side="left", fill="x", expand=True)
        self.app._date_indicator = ttk.Label(date_field, text="", width=2)
        self.app._date_indicator.pack(side="left", padx=(4, 0))
        btn_calendar = ttk.Button(
            date_field,
            text="...",
            width=3,
            command=lambda: self.app._open_calendar_for_var(
                self.app.date_var,
                tr(self.app.language, "dialog_select_date"),
            ),
        )
        btn_calendar.pack(side="left", padx=(4, 0))

        currency_field = ttk.Frame(form)
        currency_field.grid(row=1, column=4, sticky="we", padx=(0, 10), pady=(0, 2))
        self.app.currency_box = ttk.Combobox(
            currency_field,
            textvariable=self.app.currency_var,
            values=["USD", "EUR", "GBP", "JPY", "MXN", "CAD", "AUD", "CHF", "CNY", "ARS", "BRL"],
            state="readonly",
            width=10,
        )
        self.app.currency_box.pack(side="left", fill="x", expand=True)
        self.app._apply_rtl_to_widget(self.app.currency_box)

        lbl_description = ttk.Label(form, text=self.app._rtl_text(tr(self.app.language, "label_description")))
        lbl_description.grid(row=2, column=0, sticky=label_sticky, pady=4)
        self.app.description_text = tk.Text(
            form,
            width=80,
            height=4,
            relief="solid",
            borderwidth=1,
            background=self.app.theme_manager.colors["input_bg"],
            foreground=self.app.theme_manager.colors["text"],
            insertbackground=self.app.theme_manager.colors["text"],
            highlightthickness=0,
            padx=8,
            pady=6,
        )
        if is_rtl(self.app.language):
            self.app.description_text.tag_configure("rtl", justify="right")
            self.app.description_text.insert("1.0", "")
            self.app.description_text.tag_add("rtl", "1.0", "end")
        self.app.description_text.grid(row=3, column=0, columnspan=5, sticky="we", pady=(0, 8))

        actions = ttk.Frame(form, style="Card.TFrame")
        actions_sticky = "w" if is_rtl(self.app.language) else "e"
        actions.grid(row=4, column=0, columnspan=5, sticky=actions_sticky)

        btn_save = ttk.Button(
            actions,
            textvariable=self.app.save_button_var,
            style="Accent.TButton",
            command=self._save_transaction,
        )
        btn_save.pack(side="left", padx=4)
        self.app._apply_rtl_to_widget(btn_save)

        btn_clear = ttk.Button(
            actions,
            text=tr(self.app.language, "btn_clear"),
            style="Ghost.TButton",
            command=self._clear_form,
        )
        btn_clear.pack(side="left", padx=4)
        self.app._apply_rtl_to_widget(btn_clear)

        for column_index in range(5):
            form.columnconfigure(column_index, weight=1)

        self._on_register_type_changed()
        self._update_save_button_text()

        # Learn from existing transactions for auto-categorization
        try:
            transactions = self.app.transaction_service.fetch_all()
            self.app.category_suggestion_service.learn_from_transactions(transactions)
        except Exception:
            pass

        self.app.amount_var.trace_add("write", self._validate_amount)
        self.app.date_var.trace_add("write", self._validate_date)
        self.app.category_var.trace_add("write", self._validate_category)
        self.app.description_text.bind("<KeyRelease>", lambda _event: self._suggest_category())

    # ------------------------------------------------------------------
    # Form logic
    # ------------------------------------------------------------------

    def _on_register_type_changed(self) -> None:
        display_value = self.app.type_var.get().strip()
        self.app.register_type_key = self.app._type_display_to_db.get(display_value, "expense")
        options = self.app._category_options(self.app.register_type_key)
        self.app.category_box.configure(values=options)

        if self.app.category_var.get() not in options:
            self.app.category_var.set(options[0])

    def _save_transaction(self) -> None:
        try:
            transaction = self._transaction_from_form()
            if self.app.editing_transaction_id is None:
                transaction_id = self.app.transaction_service.add(transaction, language=self.app.language)
                success_message = tr(self.app.language, "success_saved", id=transaction_id)
            else:
                updated = self.app.transaction_service.update(
                    self.app.editing_transaction_id,
                    transaction,
                    language=self.app.language,
                )
                if not updated:
                    raise ValueError(tr(self.app.language, "update_not_found"))
                success_message = tr(self.app.language, "success_updated", id=self.app.editing_transaction_id)
        except ValueError as error:
            messagebox.showerror(tr(self.app.language, "error_invalid_data"), str(error), parent=self.app)
            return
        except Exception as error:
            messagebox.showerror(
                tr(self.app.language, "error_generic"),
                tr(self.app.language, "error_could_not_save", error=error),
                parent=self.app,
            )
            return

        messagebox.showinfo(tr(self.app.language, "success"), success_message, parent=self.app)
        self._clear_form(keep_date=True)
        self.app._refresh_all()

    def _suggest_category(self) -> None:
        description = self.app.description_text.get("1.0", "end").strip()
        if not description or len(description) < 3:
            return
        suggestion = self.app.category_suggestion_service.suggest(description)
        if suggestion is None:
            return
        options = list(self.app.category_box["values"] or [])
        if suggestion in options:
            current = self.app.category_var.get().strip()
            if not current or current == options[0]:
                self.app.category_var.set(suggestion)

    def _transaction_from_form(self) -> TransactionInput:
        return TransactionInput(
            amount=float(self.app.amount_var.get().strip()),
            transaction_type=self.app.register_type_key,
            category=self.app.category_var.get().strip(),
            transaction_date=date.fromisoformat(self.app.date_var.get().strip()),
            description=self.app.description_text.get("1.0", "end").strip(),
            currency=self.app.currency_var.get().strip().upper() or "USD",
        )

    def _clear_form(self, keep_date: bool = False) -> None:
        self.app.editing_transaction_id = None
        self.app.register_type_key = "expense"
        display_type = self.app._type_db_to_display.get(
            self.app.register_type_key, tr(self.app.language, "type_expense")
        )
        self.app.type_var.set(display_type)
        self.app.amount_var.set("")
        self._on_register_type_changed()
        if not keep_date:
            self.app.date_var.set(date.today().isoformat())
        self.app.description_text.delete("1.0", "end")
        self._update_save_button_text()

    def _update_save_button_text(self) -> None:
        if not hasattr(self.app, "save_button_var"):
            return
        if self.app.editing_transaction_id is None:
            self.app.save_button_var.set(tr(self.app.language, "btn_save_transaction"))
        else:
            self.app.save_button_var.set(tr(self.app.language, "btn_update_transaction"))

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate_amount(self, *_: object) -> None:
        value = self.app.amount_var.get().strip()
        if not value:
            self._set_indicator(self.app._amount_indicator, "")
            return
        try:
            amount = float(value)
            if amount > 0 and amount == amount and abs(amount) != float("inf"):
                self._set_indicator(self.app._amount_indicator, "✓", self.app.theme_manager.colors["positive"])
            else:
                self._set_indicator(self.app._amount_indicator, "✗", self.app.theme_manager.colors["negative"])
        except ValueError:
            self._set_indicator(self.app._amount_indicator, "✗", self.app.theme_manager.colors["negative"])

    def _validate_date(self, *_: object) -> None:
        value = self.app.date_var.get().strip()
        if not value:
            self._set_indicator(self.app._date_indicator, "")
            return
        try:
            date.fromisoformat(value)
            self._set_indicator(self.app._date_indicator, "✓", self.app.theme_manager.colors["positive"])
        except ValueError:
            self._set_indicator(self.app._date_indicator, "✗", self.app.theme_manager.colors["negative"])

    def _validate_category(self, *_: object) -> None:
        value = self.app.category_var.get().strip()
        if value:
            self._set_indicator(self.app._category_indicator, "✓", self.app.theme_manager.colors["positive"])
        else:
            self._set_indicator(self.app._category_indicator, "✗", self.app.theme_manager.colors["negative"])

    @staticmethod
    def _set_indicator(label: ttk.Label | None, text: str, color: str = "") -> None:
        if label is None:
            return
        label.configure(text=text, foreground=color if color else label.master["style"])
