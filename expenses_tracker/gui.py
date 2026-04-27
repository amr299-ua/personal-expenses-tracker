from __future__ import annotations

import calendar
from datetime import date, timedelta
import json
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

from expenses_tracker.charts import generate_charts
from expenses_tracker.db import ExpenseDatabase, TransactionInput
from expenses_tracker.exporters import export_reports


MONTH_NAMES_ES = [
    "",
    "Enero",
    "Febrero",
    "Marzo",
    "Abril",
    "Mayo",
    "Junio",
    "Julio",
    "Agosto",
    "Septiembre",
    "Octubre",
    "Noviembre",
    "Diciembre",
]

TYPE_UI_TO_DB = {"Ingreso": "income", "Gasto": "expense"}
TYPE_DB_TO_UI = {"income": "Ingreso", "expense": "Gasto"}
FILTER_TYPE_TO_DB = {"Todos": "", "Ingresos": "income", "Gastos": "expense"}

CATEGORIES_BY_TYPE = {
    "Ingreso": [
        "Salario",
        "Ingresos por negocio",
        "Freelance",
        "Intereses",
        "Dividendos",
        "Venta",
        "Reembolso",
        "Regalo",
        "Entrada extra",
        "Inversion",
        "Otros",
    ],
    "Gasto": [
        "Comida",
        "Luz",
        "Agua",
        "Gas",
        "Transporte",
        "Alquiler",
        "Internet",
        "Telefonia",
        "Salud",
        "Educacion",
        "Ocio",
        "Impuestos",
        "Hogar",
        "Mascotas",
        "Suscripciones",
        "Inversion",
        "Otros",
    ],
}

CHART_TYPE_OPTIONS = [
    ("Todas (recomendado)", "all"),
    ("Barras por categoria", "bar"),
    ("Linea mensual", "line"),
    ("Pastel (queso)", "pie"),
    ("Puntos mensual", "scatter"),
    ("Barras 3D mensual", "bar3d"),
]
CHART_LABEL_TO_KIND = {label: kind for label, kind in CHART_TYPE_OPTIONS}


class CalendarDialog(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Misc,
        initial_date: date,
        on_select: Callable[[date], None],
        title: str = "Seleccionar fecha",
    ) -> None:
        super().__init__(parent)
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

        ttk.Button(controls, text="<", width=3, command=self._prev_month).pack(side="left")
        self.month_label = ttk.Label(controls, anchor="center", font=("TkDefaultFont", 10, "bold"))
        self.month_label.pack(side="left", fill="x", expand=True)
        ttk.Button(controls, text=">", width=3, command=self._next_month).pack(side="right")

        self.days_frame = ttk.Frame(shell)
        self.days_frame.pack(fill="both", expand=True)

        footer = ttk.Frame(shell)
        footer.pack(fill="x", pady=(8, 0))
        ttk.Button(footer, text="Hoy", command=self._select_today).pack(side="left")
        ttk.Button(footer, text="Cerrar", command=self.destroy).pack(side="right")

        self._render()

    def _render(self) -> None:
        for widget in self.days_frame.winfo_children():
            widget.destroy()

        self.month_label.config(text=f"{MONTH_NAMES_ES[self._shown_month]} {self._shown_year}")

        weekdays = ["Lu", "Ma", "Mi", "Ju", "Vi", "Sa", "Do"]
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
    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent)
        self.title("Selecciona el tipo de grafica")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.selected_kind: str | None = None

        frame = ttk.Frame(self, padding=12)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="Elige el tipo de grafica a generar:").pack(anchor="w", pady=(0, 6))

        default_label = CHART_TYPE_OPTIONS[0][0]
        self.chart_type_label_var = tk.StringVar(value=default_label)
        chart_box = ttk.Combobox(
            frame,
            textvariable=self.chart_type_label_var,
            values=[label for label, _kind in CHART_TYPE_OPTIONS],
            state="readonly",
            width=30,
        )
        chart_box.pack(fill="x")

        button_row = ttk.Frame(frame)
        button_row.pack(fill="x", pady=(10, 0))
        ttk.Button(button_row, text="Cancelar", style="Ghost.TButton", command=self._cancel).pack(
            side="right", padx=(6, 0)
        )
        ttk.Button(button_row, text="Generar", style="Accent.TButton", command=self._accept).pack(side="right")

        self.bind("<Return>", lambda _event: self._accept())
        self.bind("<Escape>", lambda _event: self._cancel())

        chart_box.focus_set()

    def _accept(self) -> None:
        label = self.chart_type_label_var.get().strip()
        self.selected_kind = CHART_LABEL_TO_KIND.get(label)
        self.destroy()

    def _cancel(self) -> None:
        self.selected_kind = None
        self.destroy()


class ExpensesApp(tk.Tk):
    def __init__(self, db_path: str = "data/expenses.db") -> None:
        super().__init__()
        self.title("Control de gastos personal")
        self.geometry("1100x720")
        self.minsize(960, 640)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.state_file = Path("data/ui_state.json")
        self._state = self._read_ui_state()
        saved_mode = str(self._state.get("theme_mode", "light"))
        self.theme_mode = saved_mode if saved_mode in {"light", "dark"} else "light"
        self._colors = self._build_palette(self.theme_mode)
        self._setup_theme()

        self.database = ExpenseDatabase(db_path)
        self.database.initialize()

        self.search_var = tk.StringVar(value=str(self._state.get("search", "")))
        self.filter_type_var = tk.StringVar(
            value=self._normalize_filter_type(str(self._state.get("filter_type", "Todos")))
        )
        self.filter_category_var = tk.StringVar(
            value=self._normalize_filter_category(str(self._state.get("filter_category", "Todas")))
        )
        self.filter_from_var = tk.StringVar(value=str(self._state.get("filter_from", "")))
        self.filter_to_var = tk.StringVar(value=str(self._state.get("filter_to", "")))
        self.filtered_count_var = tk.StringVar(value="Mostrando: 0")

        self.sort_column = str(self._state.get("sort_column", "date"))
        self.sort_desc = bool(self._state.get("sort_desc", True))
        self._column_titles = {
            "id": "ID",
            "date": "Fecha",
            "type": "Tipo",
            "category": "Categoria",
            "amount": "Monto",
            "description": "Descripcion",
        }

        self._build_ui()
        self._refresh_all()

    def _build_ui(self) -> None:
        container = ttk.Frame(self, padding=16, style="App.TFrame")
        container.pack(fill="both", expand=True)

        header = ttk.Frame(container, padding=14, style="Header.TFrame")
        header.pack(fill="x", pady=(0, 8))

        heading = ttk.Frame(header, style="Header.TFrame")
        heading.pack(side="left", fill="x", expand=True)

        title_label = ttk.Label(heading, text="Panel de finanzas", style="HeaderTitle.TLabel")
        title_label.pack(anchor="w")
        subtitle_label = ttk.Label(
            heading,
            text="Controla movimientos, filtra datos y genera reportes visuales.",
            style="HeaderSubtitle.TLabel",
        )
        subtitle_label.pack(anchor="w", pady=(2, 0))

        buttons = ttk.Frame(header, style="Header.TFrame")
        buttons.pack(side="right")

        self.theme_button = ttk.Button(buttons, style="Ghost.TButton", command=self._toggle_theme)
        self.theme_button.pack(side="left", padx=3)
        self._update_theme_button_text()

        ttk.Button(buttons, text="Refrescar", style="Ghost.TButton", command=self._refresh_all).pack(
            side="left", padx=3
        )
        ttk.Button(buttons, text="Sacar graficas", style="Ghost.TButton", command=self._generate_charts).pack(
            side="left", padx=3
        )
        ttk.Button(
            buttons,
            text="Exportar Excel",
            style="Ghost.TButton",
            command=lambda: self._export("excel"),
        ).pack(side="left", padx=3)
        ttk.Button(
            buttons,
            text="Exportar PDF",
            style="Ghost.TButton",
            command=lambda: self._export("pdf"),
        ).pack(side="left", padx=3)
        ttk.Button(
            buttons,
            text="Exportar Todo",
            style="Accent.TButton",
            command=lambda: self._export("all"),
        ).pack(side="left", padx=3)

        self.balance_var = tk.StringVar(value="Balance actual: 0.00")
        balance_card = ttk.Frame(container, style="Card.TFrame", padding=(14, 10))
        balance_card.pack(fill="x", pady=(0, 8))
        balance_label = ttk.Label(balance_card, textvariable=self.balance_var, style="Metric.TLabel")
        balance_label.pack(anchor="w")

        notebook_shell = ttk.Frame(container, style="Card.TFrame", padding=6)
        notebook_shell.pack(fill="both", expand=True)

        notebook = ttk.Notebook(notebook_shell)
        notebook.pack(fill="both", expand=True)

        tab_register = ttk.Frame(notebook, padding=12, style="App.TFrame")
        tab_transactions = ttk.Frame(notebook, padding=12, style="App.TFrame")
        tab_stats = ttk.Frame(notebook, padding=12, style="App.TFrame")

        notebook.add(tab_register, text="Registrar")
        notebook.add(tab_transactions, text="Movimientos")
        notebook.add(tab_stats, text="Estadisticas")

        self._build_register_tab(tab_register)
        self._build_transactions_tab(tab_transactions)
        self._build_stats_tab(tab_stats)

    def _build_register_tab(self, parent: ttk.Frame) -> None:
        form = ttk.Frame(parent, style="Card.TFrame", padding=12)
        form.pack(fill="x", padx=8, pady=6)

        ttk.Label(form, text="Tipo").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Label(form, text="Monto").grid(row=0, column=1, sticky="w", pady=4)
        ttk.Label(form, text="Categoria").grid(row=0, column=2, sticky="w", pady=4)
        ttk.Label(form, text="Fecha (YYYY-MM-DD)").grid(row=0, column=3, sticky="w", pady=4)

        self.type_var = tk.StringVar(value="Gasto")
        self.amount_var = tk.StringVar()
        self.category_var = tk.StringVar()
        self.date_var = tk.StringVar(value=date.today().isoformat())

        type_box = ttk.Combobox(
            form,
            textvariable=self.type_var,
            values=["Ingreso", "Gasto"],
            state="readonly",
            width=12,
        )
        type_box.grid(row=1, column=0, sticky="we", padx=(0, 10), pady=(0, 8))
        type_box.bind("<<ComboboxSelected>>", lambda _event: self._on_register_type_changed())

        ttk.Entry(form, textvariable=self.amount_var, width=16).grid(
            row=1, column=1, sticky="we", padx=(0, 10), pady=(0, 8)
        )
        self.category_box = ttk.Combobox(
            form,
            textvariable=self.category_var,
            values=CATEGORIES_BY_TYPE[self.type_var.get()],
            state="readonly",
            width=20,
        )
        self.category_box.grid(row=1, column=2, sticky="we", padx=(0, 10), pady=(0, 8))
        self._on_register_type_changed()
        date_field = ttk.Frame(form)
        date_field.grid(row=1, column=3, sticky="we", padx=(0, 10), pady=(0, 8))
        ttk.Entry(date_field, textvariable=self.date_var, width=18).pack(side="left", fill="x", expand=True)
        ttk.Button(
            date_field,
            text="...",
            width=3,
            command=lambda: self._open_calendar_for_var(self.date_var, "Fecha del movimiento"),
        ).pack(side="left", padx=(4, 0))

        ttk.Label(form, text="Descripcion").grid(row=2, column=0, sticky="w", pady=4)
        self.description_text = tk.Text(
            form,
            width=80,
            height=4,
            relief="solid",
            borderwidth=1,
            background=self._colors["input_bg"],
            foreground=self._colors["text"],
            highlightthickness=0,
            padx=8,
            pady=6,
        )
        self.description_text.grid(row=3, column=0, columnspan=4, sticky="we", pady=(0, 8))

        actions = ttk.Frame(form, style="Card.TFrame")
        actions.grid(row=4, column=0, columnspan=4, sticky="e")

        ttk.Button(actions, text="Guardar movimiento", style="Accent.TButton", command=self._add_transaction).pack(
            side="left", padx=4
        )
        ttk.Button(actions, text="Limpiar", style="Ghost.TButton", command=self._clear_form).pack(
            side="left", padx=4
        )

        for column_index in range(4):
            form.columnconfigure(column_index, weight=1)

    def _build_transactions_tab(self, parent: ttk.Frame) -> None:
        filters = ttk.LabelFrame(parent, text="Filtros", padding=10, style="Card.TLabelframe")
        filters.pack(fill="x", padx=0, pady=(0, 8))

        ttk.Label(filters, text="Buscar").grid(row=0, column=0, sticky="w")
        ttk.Label(filters, text="Tipo").grid(row=0, column=1, sticky="w")
        ttk.Label(filters, text="Categoria").grid(row=0, column=2, sticky="w")
        ttk.Label(filters, text="Desde (YYYY-MM-DD)").grid(row=0, column=3, sticky="w")
        ttk.Label(filters, text="Hasta (YYYY-MM-DD)").grid(row=0, column=4, sticky="w")

        search_entry = ttk.Entry(filters, textvariable=self.search_var)
        search_entry.grid(row=1, column=0, sticky="we", padx=(0, 8), pady=(2, 0))

        type_box = ttk.Combobox(
            filters,
            textvariable=self.filter_type_var,
            values=["Todos", "Ingresos", "Gastos"],
            state="readonly",
            width=10,
        )
        type_box.grid(row=1, column=1, sticky="we", padx=(0, 8), pady=(2, 0))
        type_box.bind("<<ComboboxSelected>>", lambda _event: self._on_filter_change())

        self.category_filter_box = ttk.Combobox(
            filters,
            textvariable=self.filter_category_var,
            values=["Todas"],
            state="readonly",
            width=18,
        )
        self.category_filter_box.grid(row=1, column=2, sticky="we", padx=(0, 8), pady=(2, 0))
        self.category_filter_box.bind("<<ComboboxSelected>>", lambda _event: self._on_filter_change())

        from_field = ttk.Frame(filters)
        from_field.grid(row=1, column=3, sticky="we", padx=(0, 8), pady=(2, 0))
        from_entry = ttk.Entry(from_field, textvariable=self.filter_from_var, width=14)
        from_entry.pack(side="left", fill="x", expand=True)
        from_entry.bind("<KeyRelease>", lambda _event: self._on_filter_change())
        ttk.Button(
            from_field,
            text="...",
            width=3,
            command=lambda: self._open_calendar_for_var(
                self.filter_from_var,
                "Fecha inicial",
                on_change=self._on_filter_change,
            ),
        ).pack(side="left", padx=(4, 0))

        to_field = ttk.Frame(filters)
        to_field.grid(row=1, column=4, sticky="we", padx=(0, 8), pady=(2, 0))
        to_entry = ttk.Entry(to_field, textvariable=self.filter_to_var, width=14)
        to_entry.pack(side="left", fill="x", expand=True)
        to_entry.bind("<KeyRelease>", lambda _event: self._on_filter_change())
        ttk.Button(
            to_field,
            text="...",
            width=3,
            command=lambda: self._open_calendar_for_var(
                self.filter_to_var,
                "Fecha final",
                on_change=self._on_filter_change,
            ),
        ).pack(side="left", padx=(4, 0))

        filter_actions = ttk.Frame(filters, style="Card.TFrame")
        filter_actions.grid(row=1, column=5, sticky="e")
        ttk.Button(filter_actions, text="Aplicar", style="Accent.TButton", command=self._load_transactions).pack(
            side="left", padx=3
        )
        ttk.Button(filter_actions, text="Limpiar", style="Ghost.TButton", command=self._clear_filters).pack(
            side="left", padx=3
        )

        quick_ranges = ttk.Frame(filters, style="Card.TFrame")
        quick_ranges.grid(row=2, column=0, columnspan=6, sticky="w", pady=(8, 0))
        ttk.Label(quick_ranges, text="Atajos de fecha:").pack(side="left", padx=(0, 6))
        ttk.Button(
            quick_ranges,
            text="Hoy",
            style="Ghost.TButton",
            command=lambda: self._apply_date_preset("today"),
        ).pack(
            side="left", padx=2
        )
        ttk.Button(
            quick_ranges,
            text="Semana",
            style="Ghost.TButton",
            command=lambda: self._apply_date_preset("week"),
        ).pack(
            side="left", padx=2
        )
        ttk.Button(
            quick_ranges,
            text="Mes",
            style="Ghost.TButton",
            command=lambda: self._apply_date_preset("month"),
        ).pack(
            side="left", padx=2
        )
        ttk.Button(
            quick_ranges,
            text="Año",
            style="Ghost.TButton",
            command=lambda: self._apply_date_preset("year"),
        ).pack(
            side="left", padx=2
        )
        ttk.Button(
            quick_ranges,
            text="Todo",
            style="Ghost.TButton",
            command=lambda: self._apply_date_preset("all"),
        ).pack(
            side="left", padx=2
        )

        for column_index in range(5):
            filters.columnconfigure(column_index, weight=1)

        self.search_var.trace_add("write", self._on_search_change)

        info_row = ttk.Frame(parent, style="App.TFrame")
        info_row.pack(fill="x", pady=(0, 6))
        ttk.Label(info_row, textvariable=self.filtered_count_var, style="Muted.TLabel").pack(side="right")

        tree_area = ttk.Frame(parent, style="Card.TFrame", padding=8)
        tree_area.pack(fill="both", expand=True)

        columns = ("id", "date", "type", "category", "amount", "description")
        self.transactions_tree = ttk.Treeview(tree_area, columns=columns, show="headings", height=20)
        self.transactions_tree.pack(fill="both", expand=True, side="left")

        for column_name, title in self._column_titles.items():
            self.transactions_tree.heading(
                column_name,
                text=title,
                command=lambda selected=column_name: self._on_sort_change(selected),
            )

        self.transactions_tree.column("id", width=60, anchor="center")
        self.transactions_tree.column("date", width=120, anchor="center")
        self.transactions_tree.column("type", width=100, anchor="center")
        self.transactions_tree.column("category", width=160, anchor="w")
        self.transactions_tree.column("amount", width=100, anchor="e")
        self.transactions_tree.column("description", width=420, anchor="w")

        scrollbar = ttk.Scrollbar(tree_area, orient="vertical", command=self.transactions_tree.yview)
        scrollbar.pack(fill="y", side="right")
        self.transactions_tree.configure(yscrollcommand=scrollbar.set)
        self._refresh_sort_headers()

    def _build_stats_tab(self, parent: ttk.Frame) -> None:
        top = ttk.Frame(parent, style="App.TFrame")
        top.pack(fill="both", expand=True)

        left = ttk.LabelFrame(top, text="Por categoria", padding=8, style="Card.TLabelframe")
        right = ttk.LabelFrame(top, text="Por mes", padding=8, style="Card.TLabelframe")
        left.pack(fill="both", expand=True, side="left", padx=(0, 5))
        right.pack(fill="both", expand=True, side="left", padx=(5, 0))

        self.category_tree = ttk.Treeview(
            left,
            columns=("category", "income", "expense", "balance"),
            show="headings",
            height=14,
        )
        self.category_tree.pack(fill="both", expand=True, side="left")

        self.category_tree.heading("category", text="Categoria")
        self.category_tree.heading("income", text="Ingresos")
        self.category_tree.heading("expense", text="Gastos")
        self.category_tree.heading("balance", text="Balance")

        self.category_tree.column("category", width=160, anchor="w")
        self.category_tree.column("income", width=100, anchor="e")
        self.category_tree.column("expense", width=100, anchor="e")
        self.category_tree.column("balance", width=100, anchor="e")

        cat_scroll = ttk.Scrollbar(left, orient="vertical", command=self.category_tree.yview)
        cat_scroll.pack(fill="y", side="right")
        self.category_tree.configure(yscrollcommand=cat_scroll.set)

        self.month_tree = ttk.Treeview(
            right,
            columns=("month", "income", "expense", "balance"),
            show="headings",
            height=14,
        )
        self.month_tree.pack(fill="both", expand=True, side="left")

        self.month_tree.heading("month", text="Mes")
        self.month_tree.heading("income", text="Ingresos")
        self.month_tree.heading("expense", text="Gastos")
        self.month_tree.heading("balance", text="Balance")

        self.month_tree.column("month", width=120, anchor="center")
        self.month_tree.column("income", width=100, anchor="e")
        self.month_tree.column("expense", width=100, anchor="e")
        self.month_tree.column("balance", width=100, anchor="e")

        month_scroll = ttk.Scrollbar(right, orient="vertical", command=self.month_tree.yview)
        month_scroll.pack(fill="y", side="right")
        self.month_tree.configure(yscrollcommand=month_scroll.set)

    def _add_transaction(self) -> None:
        try:
            parsed_date = date.fromisoformat(self.date_var.get().strip())
            amount = float(self.amount_var.get().strip())
            db_type = TYPE_UI_TO_DB.get(self.type_var.get().strip())
            if db_type is None:
                raise ValueError("Selecciona un tipo valido (Ingreso o Gasto).")

            transaction = TransactionInput(
                amount=amount,
                transaction_type=db_type,
                category=self.category_var.get().strip(),
                transaction_date=parsed_date,
                description=self.description_text.get("1.0", "end").strip(),
            )
            transaction_id = self.database.add_transaction(transaction)
        except ValueError as error:
            messagebox.showerror("Dato invalido", str(error), parent=self)
            return
        except Exception as error:
            messagebox.showerror("Error", f"No se pudo guardar: {error}", parent=self)
            return

        messagebox.showinfo("Exito", f"Movimiento guardado con ID {transaction_id}", parent=self)
        self._clear_form(keep_date=True)
        self._refresh_all()

    def _clear_form(self, keep_date: bool = False) -> None:
        self.type_var.set("Gasto")
        self.amount_var.set("")
        self._on_register_type_changed()
        if not keep_date:
            self.date_var.set(date.today().isoformat())
        self.description_text.delete("1.0", "end")

    def _on_register_type_changed(self) -> None:
        current_type = self.type_var.get().strip()
        category_options = CATEGORIES_BY_TYPE.get(current_type, CATEGORIES_BY_TYPE["Gasto"])
        self.category_box.configure(values=category_options)

        if self.category_var.get() not in category_options:
            self.category_var.set(category_options[0])

    def _refresh_all(self) -> None:
        self._load_transactions()
        self._load_stats()

    def _load_transactions(self) -> None:
        self._clear_tree(self.transactions_tree)
        rows = self.database.fetch_transactions(limit=None)
        self._sync_category_filter(rows)

        filtered_rows = self._apply_transaction_filters(rows)
        sorted_rows = self._sort_transactions(filtered_rows)

        for row in sorted_rows:
            self.transactions_tree.insert(
                "",
                "end",
                values=(
                    row["id"],
                    row["transaction_date"],
                    TYPE_DB_TO_UI.get(str(row["transaction_type"]), str(row["transaction_type"])),
                    row["category"],
                    f"{float(row['amount']):.2f}",
                    row["description"],
                ),
            )

        self.filtered_count_var.set(f"Mostrando: {len(sorted_rows)} de {len(rows)}")

    def _on_search_change(self, *_: object) -> None:
        self._on_filter_change()

    def _on_filter_change(self) -> None:
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

        CalendarDialog(self, initial, _apply, title=title)

    def _clear_filters(self) -> None:
        self.search_var.set("")
        self.filter_type_var.set("Todos")
        self.filter_category_var.set("Todas")
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
        values = ["Todas", *categories]
        self.category_filter_box.configure(values=values)
        if self.filter_category_var.get() not in values:
            self.filter_category_var.set("Todas")

    def _apply_transaction_filters(self, rows: list[dict[str, object]]) -> list[dict[str, object]]:
        search = self.search_var.get().strip().lower()
        selected_type_db = FILTER_TYPE_TO_DB.get(self.filter_type_var.get().strip(), "")
        selected_category = self.filter_category_var.get().strip().lower()
        date_from = self._safe_parse_date(self.filter_from_var.get())
        date_to = self._safe_parse_date(self.filter_to_var.get())

        filtered: list[dict[str, object]] = []
        for row in rows:
            row_type = str(row["transaction_type"]).lower()
            row_category = str(row["category"]).lower()
            row_date = self._safe_parse_date(str(row["transaction_date"]))

            if selected_type_db and row_type != selected_type_db:
                continue
            if selected_category != "todas" and row_category != selected_category:
                continue
            if date_from and row_date and row_date < date_from:
                continue
            if date_to and row_date and row_date > date_to:
                continue

            if search:
                searchable = " ".join(
                    [
                        str(row["id"]),
                        str(row["transaction_date"]),
                        TYPE_DB_TO_UI.get(str(row["transaction_type"]), str(row["transaction_type"])),
                        str(row["category"]),
                        str(row["amount"]),
                        str(row["description"]),
                    ]
                ).lower()
                if search not in searchable:
                    continue

            filtered.append(row)

        return filtered

    def _sort_transactions(self, rows: list[dict[str, object]]) -> list[dict[str, object]]:
        return sorted(
            rows,
            key=self._row_sort_key,
            reverse=self.sort_desc,
        )

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
            label = title
            if column_name == self.sort_column:
                label = f"{title} {arrow}"
            self.transactions_tree.heading(
                column_name,
                text=label,
                command=lambda selected=column_name: self._on_sort_change(selected),
            )

    @staticmethod
    def _safe_parse_date(raw_value: str) -> date | None:
        value = raw_value.strip()
        if not value:
            return None
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None

    @staticmethod
    def _normalize_filter_type(value: str) -> str:
        value_clean = value.strip()
        mapping = {
            "all": "Todos",
            "income": "Ingresos",
            "expense": "Gastos",
            "Todos": "Todos",
            "Ingresos": "Ingresos",
            "Gastos": "Gastos",
        }
        return mapping.get(value_clean, "Todos")

    @staticmethod
    def _normalize_filter_category(value: str) -> str:
        value_clean = value.strip()
        if value_clean in {"", "all"}:
            return "Todas"
        return value_clean

    def _read_ui_state(self) -> dict[str, Any]:
        if not self.state_file.exists():
            return {}

        try:
            return json.loads(self.state_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def _save_ui_state(self) -> None:
        data = {
            "theme_mode": self.theme_mode,
            "search": self.search_var.get(),
            "filter_type": self.filter_type_var.get(),
            "filter_category": self.filter_category_var.get(),
            "filter_from": self.filter_from_var.get(),
            "filter_to": self.filter_to_var.get(),
            "sort_column": self.sort_column,
            "sort_desc": self.sort_desc,
        }

        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            self.state_file.write_text(json.dumps(data, ensure_ascii=True, indent=2), encoding="utf-8")
        except OSError:
            return

    def _on_close(self) -> None:
        self._save_ui_state()
        self.destroy()

    def _toggle_theme(self) -> None:
        new_mode = "dark" if self.theme_mode == "light" else "light"
        self._set_theme(new_mode)
        self._save_ui_state()

    def _set_theme(self, mode: str) -> None:
        self.theme_mode = "dark" if mode == "dark" else "light"
        self._colors = self._build_palette(self.theme_mode)
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

    def _update_theme_button_text(self) -> None:
        if hasattr(self, "theme_button"):
            if self.theme_mode == "light":
                self.theme_button.configure(text="Modo oscuro")
            else:
                self.theme_button.configure(text="Modo claro")

    @staticmethod
    def _build_palette(mode: str) -> dict[str, str]:
        if mode == "dark":
            return {
                "bg": "#0b1220",
                "card": "#111827",
                "header": "#020617",
                "text": "#e5e7eb",
                "muted": "#9ca3af",
                "accent": "#38bdf8",
                "accent_hover": "#0ea5e9",
                "line": "#2a3547",
                "input_bg": "#1f2937",
                "notebook_bg": "#182233",
                "select_bg": "#1e3a8a",
                "select_fg": "#dbeafe",
            }

        return {
            "bg": "#f4f7fb",
            "card": "#ffffff",
            "header": "#0f172a",
            "text": "#1f2937",
            "muted": "#6b7280",
            "accent": "#0ea5e9",
            "accent_hover": "#0284c7",
            "line": "#dbe2ea",
            "input_bg": "#ffffff",
            "notebook_bg": "#e9eef5",
            "select_bg": "#dbeafe",
            "select_fg": "#1e3a8a",
        }

    def _setup_theme(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")

        self.configure(background=self._colors["bg"])
        self.option_add("*Font", "TkDefaultFont 10")

        style.configure("TFrame", background=self._colors["bg"])
        style.configure("App.TFrame", background=self._colors["bg"])
        style.configure("Card.TFrame", background=self._colors["card"])
        style.configure("Header.TFrame", background=self._colors["header"])

        style.configure(
            "TButton",
            background=self._colors["card"],
            foreground=self._colors["text"],
            borderwidth=1,
            relief="solid",
            padding=(8, 6),
        )
        style.map(
            "TButton",
            background=[("active", self._colors["notebook_bg"]), ("pressed", self._colors["notebook_bg"])],
            foreground=[("disabled", self._colors["muted"])],
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
            "TEntry",
            fieldbackground=self._colors["input_bg"],
            foreground=self._colors["text"],
            padding=6,
        )
        style.configure(
            "TCombobox",
            fieldbackground=self._colors["input_bg"],
            foreground=self._colors["text"],
            arrowcolor=self._colors["text"],
            padding=5,
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", self._colors["input_bg"])],
            foreground=[("readonly", self._colors["text"])],
            selectforeground=[("readonly", self._colors["text"])],
            selectbackground=[("readonly", self._colors["input_bg"])],
        )

        style.configure("TNotebook", background=self._colors["card"], borderwidth=0)
        style.configure(
            "TNotebook.Tab",
            background=self._colors["notebook_bg"],
            foreground=self._colors["muted"],
            padding=(14, 8),
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", self._colors["card"])],
            foreground=[("selected", self._colors["text"])],
        )

        style.configure(
            "Treeview",
            background=self._colors["card"],
            fieldbackground=self._colors["card"],
            foreground=self._colors["text"],
            rowheight=30,
            bordercolor=self._colors["line"],
            lightcolor=self._colors["line"],
            darkcolor=self._colors["line"],
            relief="solid",
        )
        style.map(
            "Treeview",
            background=[("selected", self._colors["select_bg"])],
            foreground=[("selected", self._colors["select_fg"])],
        )
        style.configure(
            "Treeview.Heading",
            background=self._colors["notebook_bg"],
            foreground=self._colors["text"],
            relief="flat",
            font=("TkDefaultFont", 10, "bold"),
            padding=(6, 6),
        )

        style.configure(
            "TSpinbox",
            fieldbackground=self._colors["input_bg"],
            foreground=self._colors["text"],
            arrowcolor=self._colors["text"],
        )

    def _load_stats(self) -> None:
        self._clear_tree(self.category_tree)
        self._clear_tree(self.month_tree)

        balance = self.database.get_balance()
        self.balance_var.set(f"Balance actual: {balance:.2f}")

        for row in self.database.get_totals_by_category():
            self.category_tree.insert(
                "",
                "end",
                values=(
                    row["category"],
                    f"{float(row['income']):.2f}",
                    f"{float(row['expense']):.2f}",
                    f"{float(row['balance']):.2f}",
                ),
            )

        for row in self.database.get_totals_by_month():
            self.month_tree.insert(
                "",
                "end",
                values=(
                    row["month"],
                    f"{float(row['income']):.2f}",
                    f"{float(row['expense']):.2f}",
                    f"{float(row['balance']):.2f}",
                ),
            )

    def _generate_charts(self) -> None:
        dialog = ChartTypeDialog(self)
        self.wait_window(dialog)

        if not dialog.selected_kind:
            return

        try:
            generated = generate_charts(
                category_rows=self.database.get_totals_by_category(),
                month_rows=self.database.get_totals_by_month(),
                output_dir="reports",
                kind=dialog.selected_kind,
            )
        except Exception as error:
            messagebox.showerror("Error", f"No se pudieron generar graficas: {error}", parent=self)
            return

        if not generated:
            messagebox.showwarning("Sin datos", "No hay datos para generar graficas.", parent=self)
            return

        files_text = "\n".join(path.as_posix() for path in generated)
        messagebox.showinfo("Graficas generadas", files_text, parent=self)

    def _export(self, fmt: str) -> None:
        transactions = self.database.fetch_transactions(limit=None)
        if not transactions:
            messagebox.showwarning("Sin datos", "No hay movimientos para exportar.", parent=self)
            return

        try:
            generated = export_reports(
                transactions=transactions,
                category_rows=self.database.get_totals_by_category(),
                month_rows=self.database.get_totals_by_month(),
                output_dir="reports",
                fmt=fmt,
            )
        except Exception as error:
            messagebox.showerror("Error", f"No se pudo exportar: {error}", parent=self)
            return

        if not generated:
            messagebox.showwarning("Sin archivos", "No se genero ningun archivo.", parent=self)
            return

        files_text = "\n".join(path.as_posix() for path in generated)
        messagebox.showinfo("Reportes generados", files_text, parent=self)

    @staticmethod
    def _clear_tree(tree: ttk.Treeview) -> None:
        for item in tree.get_children():
            tree.delete(item)


def main() -> int:
    try:
        app = ExpensesApp(db_path="data/expenses.db")
    except tk.TclError as error:
        print(f"No se pudo iniciar la interfaz grafica: {error}")
        return 1

    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
