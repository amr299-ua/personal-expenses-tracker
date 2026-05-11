from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Any

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure

from expenses_tracker.charts import (
    budget_comparison_figure,
    category_pie_figure,
    category_totals_figure,
    forecast_figure,
    get_palette,
    month_bars_3d_figure,
    month_scatter_figure,
    month_totals_figure,
    sankey_figure,
)
from expenses_tracker.i18n import normalize_language, tr
from expenses_tracker.security import apply_private_permissions


class ChartViewerDialog(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Misc,
        language: str,
        palette: str,
        kind: str,
        category_rows: list[dict[str, Any]],
        month_rows: list[dict[str, Any]],
        budget_rows: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(parent)
        self._language = normalize_language(language)
        self._colors = get_palette(palette)
        self.title(tr(self._language, "info_charts_generated"))
        self.geometry("900x650")
        self.minsize(700, 500)
        self.transient(parent)
        self.grab_set()

        self._category_rows = category_rows
        self._month_rows = month_rows
        self._budget_rows = budget_rows or []
        self._tabs: list[tuple[str, Figure]] = []

        self._build_tabs(kind)
        self._build_footer()

        self.bind("<Escape>", lambda _event: self.destroy())

    def _build_tabs(self, kind: str) -> None:
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=8, pady=8)

        requested = self._resolve_kinds(kind)

        if "bar" in requested and self._category_rows:
            figure = category_totals_figure(self._category_rows, self._language, self._colors)
            self._add_tab(notebook, tr(self._language, "chart_option_bar"), figure, "bar")

        if "line" in requested and self._month_rows:
            figure = month_totals_figure(self._month_rows, self._language, self._colors)
            self._add_tab(notebook, tr(self._language, "chart_option_line"), figure, "line")

        if "pie" in requested and self._category_rows:
            figure = category_pie_figure(self._category_rows, self._language, self._colors)
            self._add_tab(notebook, tr(self._language, "chart_option_pie"), figure, "pie")

        if "scatter" in requested and self._month_rows:
            figure = month_scatter_figure(self._month_rows, self._language, self._colors)
            self._add_tab(notebook, tr(self._language, "chart_option_scatter"), figure, "scatter")

        if "bar3d" in requested and self._month_rows:
            figure = month_bars_3d_figure(self._month_rows, self._language, self._colors)
            self._add_tab(notebook, tr(self._language, "chart_option_bar3d"), figure, "bar3d")

        if "forecast" in requested and self._month_rows:
            figure = forecast_figure(self._month_rows, self._language, self._colors)
            self._add_tab(notebook, tr(self._language, "chart_option_forecast"), figure, "forecast")

        if "sankey" in requested and self._category_rows:
            figure = sankey_figure(self._category_rows, self._language, self._colors)
            self._add_tab(notebook, tr(self._language, "chart_option_sankey"), figure, "sankey")

        if "budget" in requested and self._budget_rows:
            figure = budget_comparison_figure(self._budget_rows, self._language, self._colors)
            self._add_tab(notebook, tr(self._language, "chart_option_budget"), figure, "budget")

        if not notebook.tabs():
            label = ttk.Label(self, text=tr(self._language, "warning_no_chart_data"))
            label.pack(expand=True)

    def _add_tab(self, notebook: ttk.Notebook, title: str, figure: Figure, kind_key: str) -> None:
        frame = ttk.Frame(notebook)
        notebook.add(frame, text=title)

        canvas = FigureCanvasTkAgg(figure, master=frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

        toolbar = NavigationToolbar2Tk(canvas, frame, pack_toolbar=False)
        toolbar.update()
        toolbar.pack(fill="x", side="bottom")

        axis = figure.axes[0] if figure.axes else None
        if axis is not None:
            self._enable_scroll_zoom(figure, axis)
            if kind_key in ("bar", "budget") and hasattr(axis, "patches"):
                self._add_tooltip_to_bars(axis)
            elif kind_key == "line":
                self._add_tooltip_to_lines(axis)

        self._tabs.append((kind_key, figure))

    def _build_footer(self) -> None:
        footer = ttk.Frame(self)
        footer.pack(fill="x", padx=8, pady=(0, 8))

        ttk.Button(
            footer,
            text=tr(self._language, "btn_export"),
            command=self._export_current_png,
        ).pack(side="left")
        ttk.Button(
            footer,
            text=tr(self._language, "btn_close"),
            command=self.destroy,
        ).pack(side="right")

    def _export_current_png(self) -> None:
        # Find current tab index via notebook
        notebook = None
        for child in self.winfo_children():
            if isinstance(child, ttk.Notebook):
                notebook = child
                break
        if notebook is None:
            return
        current = notebook.index(notebook.select())
        if current < 0 or current >= len(self._tabs):
            return
        kind_key, figure = self._tabs[current]
        output_dir = Path("reports")
        output_dir.mkdir(parents=True, exist_ok=True)
        from datetime import datetime

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        path = output_dir / f"chart_{kind_key}_{timestamp}.png"
        figure.savefig(path, dpi=150)
        apply_private_permissions(path)
        messagebox.showinfo(
            tr(self._language, "info_charts_generated"),
            tr(self._language, "chart_generated", path=path.as_posix()),
            parent=self,
        )

    def _resolve_kinds(self, kind: str) -> set[str]:
        normalized = kind.strip().lower()
        mapping = {
            "all": {"bar", "line", "pie", "scatter", "bar3d", "forecast", "sankey", "budget"},
            "category": {"bar"},
            "month": {"line"},
            "bar": {"bar"},
            "line": {"line"},
            "pie": {"pie"},
            "scatter": {"scatter"},
            "bar3d": {"bar3d"},
            "forecast": {"forecast"},
            "sankey": {"sankey"},
            "budget": {"budget"},
        }
        return mapping.get(normalized, {normalized}) if normalized in mapping else set()

    def _enable_scroll_zoom(self, figure: Figure, axis: Any) -> None:
        def on_scroll(event):
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

        figure.canvas.mpl_connect("scroll_event", on_scroll)

    def _add_tooltip_to_bars(self, axis: Any) -> None:
        tooltip = tk.Toplevel(self)
        tooltip.overrideredirect(True)
        tooltip.withdraw()
        label = ttk.Label(tooltip, text="", background="yellow", relief="solid", borderwidth=1, padding=(4, 2))
        label.pack()

        categories = [str(t.get_text()) for t in axis.get_xticklabels()]
        # Approximate values from patches
        income_vals: list[float] = []
        expense_vals: list[float] = []
        for patch in axis.patches:
            # We don't know which is income/expense; just show height
            pass

        def on_motion(event):
            if event.inaxes != axis:
                tooltip.withdraw()
                return
            found = False
            for i, patch in enumerate(axis.patches):
                if patch.contains_point((event.x, event.y), radius=5):
                    cat = categories[i % len(categories)] if categories else ""
                    val = patch.get_height()
                    text = f"{cat}\n{val:.2f}"
                    label.configure(text=text)
                    tooltip.deiconify()
                    tooltip.geometry(f"+{self.winfo_pointerx() + 15}+{self.winfo_pointery() + 15}")
                    found = True
                    break
            if not found:
                tooltip.withdraw()

        axis.figure.canvas.mpl_connect("motion_notify_event", on_motion)

    def _add_tooltip_to_lines(self, axis: Any) -> None:
        tooltip = tk.Toplevel(self)
        tooltip.overrideredirect(True)
        tooltip.withdraw()
        label = ttk.Label(tooltip, text="", background="yellow", relief="solid", borderwidth=1, padding=(4, 2))
        label.pack()

        lines = [line for line in axis.lines if hasattr(line, "get_xydata")]

        def on_motion(event):
            if event.inaxes != axis:
                tooltip.withdraw()
                return
            found = False
            for line in lines:
                xdata, ydata = line.get_data()
                for i in range(len(xdata)):
                    x_display, y_display = axis.transData.transform((xdata[i], ydata[i]))
                    dist = ((event.x - x_display) ** 2 + (event.y - y_display) ** 2) ** 0.5
                    if dist < 10:
                        label.configure(text=f"{xdata[i]}\n{ydata[i]:.2f}")
                        tooltip.deiconify()
                        tooltip.geometry(f"+{self.winfo_pointerx() + 15}+{self.winfo_pointery() + 15}")
                        found = True
                        break
                if found:
                    break
            if not found:
                tooltip.withdraw()

        axis.figure.canvas.mpl_connect("motion_notify_event", on_motion)
