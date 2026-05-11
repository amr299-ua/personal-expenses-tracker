"""Embedded matplotlib chart panel for the statistics tab.

Encapsulates rendering, tooltips and zoom for the two embedded charts.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk  # type: ignore[attr-defined]
from matplotlib.figure import Figure

from expenses_tracker.i18n import format_number, tr


class EmbeddedChartPanel:
    """Renders category and month charts inside tkinter frames."""

    def __init__(
        self,
        *,
        category_frame: ttk.Frame,
        month_frame: ttk.Frame,
        language: str,
        colors: dict[str, str],
        show_income: tk.BooleanVar,
        show_expense: tk.BooleanVar,
        show_balance: tk.BooleanVar,
        master: tk.Tk | tk.Toplevel,
    ) -> None:
        self._category_frame = category_frame
        self._month_frame = month_frame
        self._language = language
        self._colors = colors
        self._show_income = show_income
        self._show_expense = show_expense
        self._show_balance = show_balance
        self._master = master

        self._canvas_category: FigureCanvasTkAgg | None = None
        self._canvas_month: FigureCanvasTkAgg | None = None
        self._toolbar_category: NavigationToolbar2Tk | None = None
        self._toolbar_month: NavigationToolbar2Tk | None = None
        self._scroll_cids: list[int] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_charts(
        self,
        category_rows: list[dict[str, Any]],
        month_rows: list[dict[str, Any]],
    ) -> None:
        """Redraw both embedded charts with fresh data."""
        self._destroy_chart(self._canvas_category, self._toolbar_category)
        self._destroy_chart(self._canvas_month, self._toolbar_month)
        self._scroll_cids.clear()

        if not category_rows and not month_rows:
            return

        if category_rows:
            self._canvas_category = self._render_category_chart(category_rows)
        if month_rows:
            self._canvas_month = self._render_month_chart(month_rows)

    def set_language(self, language: str) -> None:
        """Update the language used for chart labels."""
        self._language = language

    def set_colors(self, colors: dict[str, str]) -> None:
        """Update the color palette used for chart series."""
        self._colors = colors

    def destroy(self) -> None:
        """Clean up matplotlib widgets."""
        self._destroy_chart(self._canvas_category, self._toolbar_category)
        self._destroy_chart(self._canvas_month, self._toolbar_month)

    # ------------------------------------------------------------------
    # Render helpers
    # ------------------------------------------------------------------

    def _render_category_chart(self, rows: list[dict[str, Any]]) -> FigureCanvasTkAgg | None:
        figure = Figure(figsize=(5, 3), dpi=100)
        axis = figure.add_subplot(111)
        categories = [r["category"] for r in rows]
        expense_values = [float(r["expense"]) for r in rows]
        income_values = [float(r["income"]) for r in rows]
        x = range(len(categories))
        axis.bar(
            x,
            income_values,
            label=tr(self._language, "legend_income"),
            color=self._colors["positive"],
        )
        axis.bar(
            x,
            expense_values,
            label=tr(self._language, "legend_expense"),
            color=self._colors["negative"],
            alpha=0.85,
        )
        axis.set_xticks(list(x))
        axis.set_xticklabels(categories, rotation=30, ha="right", fontsize=8)
        axis.legend(fontsize=8)
        axis.set_title(tr(self._language, "chart_title_category"), fontsize=10)
        self._add_tooltip_to_bars(axis, categories, income_values, expense_values)
        figure.tight_layout()

        canvas = FigureCanvasTkAgg(figure, master=self._category_frame)  # type: ignore[no-untyped-call]
        canvas.draw()  # type: ignore[no-untyped-call]
        canvas.get_tk_widget().pack(fill="both", expand=True)  # type: ignore[no-untyped-call]
        toolbar = NavigationToolbar2Tk(canvas, self._category_frame, pack_toolbar=False)  # type: ignore[no-untyped-call]
        toolbar.update()
        toolbar.pack(fill="x", side="bottom")
        self._toolbar_category = toolbar

        cid = self._enable_scroll_zoom(figure, axis)
        if cid is not None:
            self._scroll_cids.append(cid)
        return canvas

    def _render_month_chart(self, rows: list[dict[str, Any]]) -> FigureCanvasTkAgg | None:
        figure = Figure(figsize=(5, 3), dpi=100)
        axis = figure.add_subplot(111)
        months = [r["month"] for r in rows]
        income_values = [float(r["income"]) for r in rows]
        expense_values = [float(r["expense"]) for r in rows]
        balance_values = [float(r["balance"]) for r in rows]
        if self._show_income.get():
            axis.plot(
                months,
                income_values,
                marker="o",
                label=tr(self._language, "legend_income"),
                color=self._colors["positive"],
            )
        if self._show_expense.get():
            axis.plot(
                months,
                expense_values,
                marker="o",
                label=tr(self._language, "legend_expense"),
                color=self._colors["negative"],
            )
        if self._show_balance.get():
            axis.plot(
                months,
                balance_values,
                marker="o",
                label=tr(self._language, "legend_balance"),
                color=self._colors["accent"],
            )
        axis.set_xticks(range(len(months)))
        axis.set_xticklabels(months, rotation=30, ha="right", fontsize=8)
        if any([self._show_income.get(), self._show_expense.get(), self._show_balance.get()]):
            axis.legend(fontsize=8)
        axis.set_title(tr(self._language, "chart_title_month"), fontsize=10)
        axis.grid(alpha=0.3)
        self._add_tooltip_to_lines(axis, months, income_values, expense_values, balance_values)
        figure.tight_layout()

        canvas = FigureCanvasTkAgg(figure, master=self._month_frame)  # type: ignore[no-untyped-call]
        canvas.draw()  # type: ignore[no-untyped-call]
        canvas.get_tk_widget().pack(fill="both", expand=True)  # type: ignore[no-untyped-call]
        toolbar = NavigationToolbar2Tk(canvas, self._month_frame, pack_toolbar=False)  # type: ignore[no-untyped-call]
        toolbar.update()
        toolbar.pack(fill="x", side="bottom")
        self._toolbar_month = toolbar

        cid = self._enable_scroll_zoom(figure, axis)
        if cid is not None:
            self._scroll_cids.append(cid)
        return canvas

    @staticmethod
    def _destroy_chart(canvas: FigureCanvasTkAgg | None, toolbar: NavigationToolbar2Tk | None) -> None:
        if canvas is not None:
            canvas.get_tk_widget().destroy()  # type: ignore[no-untyped-call]
        if toolbar is not None:
            toolbar.destroy()

    def _add_tooltip_to_bars(
        self,
        axis: Any,
        categories: list[str],
        income_values: list[float],
        expense_values: list[float],
    ) -> None:
        tooltip = tk.Toplevel(self._master)
        tooltip.overrideredirect(True)
        tooltip.withdraw()
        label = ttk.Label(tooltip, text="", background="yellow", relief="solid", borderwidth=1, padding=(4, 2))
        label.pack()

        def on_motion(event: Any) -> None:
            if event.inaxes != axis:
                tooltip.withdraw()
                return
            found = False
            for bar, cat, inc, exp in zip(axis.patches, categories, income_values, expense_values, strict=False):
                if bar.contains_point((event.x, event.y), radius=5):
                    text = (
                        f"{cat}\n"
                        f"{tr(self._language, 'legend_income')}: {format_number(self._language, inc)}\n"
                        f"{tr(self._language, 'legend_expense')}: {format_number(self._language, exp)}"
                    )
                    label.configure(text=text)
                    tooltip.deiconify()
                    tooltip.geometry(f"+{self._master.winfo_pointerx() + 15}+{self._master.winfo_pointery() + 15}")
                    found = True
                    break
            if not found:
                tooltip.withdraw()

        axis.figure.canvas.mpl_connect("motion_notify_event", on_motion)

    def _add_tooltip_to_lines(
        self,
        axis: Any,
        months: list[str],
        income_values: list[float],
        expense_values: list[float],
        balance_values: list[float],
    ) -> None:
        tooltip = tk.Toplevel(self._master)
        tooltip.overrideredirect(True)
        tooltip.withdraw()
        label = ttk.Label(tooltip, text="", background="yellow", relief="solid", borderwidth=1, padding=(4, 2))
        label.pack()

        def on_motion(event: Any) -> None:
            if event.inaxes != axis:
                tooltip.withdraw()
                return
            found = False
            for i, month in enumerate(months):
                x_data = i
                for y_data, _key, _color in [
                    (income_values[i], "legend_income", self._colors["positive"]),
                    (expense_values[i], "legend_expense", self._colors["negative"]),
                    (balance_values[i], "legend_balance", self._colors["accent"]),
                ]:
                    x_display, y_display = axis.transData.transform((x_data, y_data))
                    dist = ((event.x - x_display) ** 2 + (event.y - y_display) ** 2) ** 0.5
                    if dist < 10:
                        inc = format_number(self._language, income_values[i])
                        exp = format_number(self._language, expense_values[i])
                        bal = format_number(self._language, balance_values[i])
                        text = (
                            f"{month}\n"
                            f"{tr(self._language, 'legend_income')}: {inc}\n"
                            f"{tr(self._language, 'legend_expense')}: {exp}\n"
                            f"{tr(self._language, 'legend_balance')}: {bal}"
                        )
                        label.configure(text=text)
                        tooltip.deiconify()
                        tooltip.geometry(f"+{self._master.winfo_pointerx() + 15}+{self._master.winfo_pointery() + 15}")
                        found = True
                        break
                if found:
                    break
            if not found:
                tooltip.withdraw()

        axis.figure.canvas.mpl_connect("motion_notify_event", on_motion)

    def _enable_scroll_zoom(self, figure: Any, axis: Any) -> int | None:
        def on_scroll(event: Any) -> None:
            if event.inaxes != axis:
                return
            x_min, x_max = axis.get_xlim()
            y_min, y_max = axis.get_ylim()
            factor = 0.9 if event.step > 0 else 1.1
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
        return cid  # type: ignore[no-any-return]
