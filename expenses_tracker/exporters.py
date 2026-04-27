from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from openpyxl import Workbook
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def export_reports(
    transactions: list[dict[str, Any]],
    category_rows: list[dict[str, Any]],
    month_rows: list[dict[str, Any]],
    output_dir: str | Path = "reports",
    fmt: str = "all",
) -> list[Path]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    generated_files: list[Path] = []

    if fmt in {"excel", "all"}:
        excel_file = output_path / f"report_{timestamp}.xlsx"
        _export_excel(excel_file, transactions, category_rows, month_rows)
        generated_files.append(excel_file)

    if fmt in {"pdf", "all"}:
        pdf_file = output_path / f"report_{timestamp}.pdf"
        _export_pdf(pdf_file, transactions, category_rows, month_rows)
        generated_files.append(pdf_file)

    return generated_files


def _export_excel(
    output_file: Path,
    transactions: list[dict[str, Any]],
    category_rows: list[dict[str, Any]],
    month_rows: list[dict[str, Any]],
) -> None:
    workbook = Workbook()

    movement_sheet = workbook.active
    movement_sheet.title = "Movimientos"
    movement_sheet.append(
        ["ID", "Fecha", "Tipo", "Categoria", "Monto", "Descripcion", "Creado"]
    )
    for row in transactions:
        movement_sheet.append(
            [
                row["id"],
                row["transaction_date"],
                row["transaction_type"],
                row["category"],
                float(row["amount"]),
                row["description"],
                row["created_at"],
            ]
        )

    category_sheet = workbook.create_sheet("PorCategoria")
    category_sheet.append(["Categoria", "Ingresos", "Gastos", "Balance"])
    for row in category_rows:
        category_sheet.append(
            [
                row["category"],
                float(row["income"]),
                float(row["expense"]),
                float(row["balance"]),
            ]
        )

    month_sheet = workbook.create_sheet("PorMes")
    month_sheet.append(["Mes", "Ingresos", "Gastos", "Balance"])
    for row in month_rows:
        month_sheet.append(
            [
                row["month"],
                float(row["income"]),
                float(row["expense"]),
                float(row["balance"]),
            ]
        )

    workbook.save(output_file)


def _export_pdf(
    output_file: Path,
    transactions: list[dict[str, Any]],
    category_rows: list[dict[str, Any]],
    month_rows: list[dict[str, Any]],
) -> None:
    base_styles = getSampleStyleSheet()
    styles = _build_pdf_styles(base_styles)
    document = SimpleDocTemplate(
        str(output_file),
        pagesize=A4,
        leftMargin=28,
        rightMargin=28,
        topMargin=36,
        bottomMargin=26,
    )
    elements: list[Any] = []

    summary_metrics = _compute_summary_metrics(transactions, category_rows, month_rows)
    summary_data = _build_executive_summary(summary_metrics)

    elements.append(_build_cover_banner(summary_metrics, styles))
    elements.append(Spacer(1, 12))
    elements.append(_build_kpi_table(summary_metrics, styles))
    elements.append(Spacer(1, 10))

    elements.append(Paragraph("Resumen ejecutivo", styles["section_title"]))
    elements.append(Paragraph(summary_data, styles["body_text"]))
    elements.append(PageBreak())

    category_table_rows = [
        [
            escape(str(row["category"])),
            f"{float(row['income']):.2f}",
            f"{float(row['expense']):.2f}",
            f"{float(row['balance']):.2f}",
        ]
        for row in category_rows
    ]
    _append_paginated_table(
        elements=elements,
        styles=styles,
        title="Resumen por categoria",
        header=["Categoria", "Ingresos", "Gastos", "Balance"],
        rows=category_table_rows,
        chunk_size=28,
        col_widths=[180, 95, 95, 95],
        text_column_indexes=[0],
    )

    month_table_rows = [
        [
            escape(str(row["month"])),
            f"{float(row['income']):.2f}",
            f"{float(row['expense']):.2f}",
            f"{float(row['balance']):.2f}",
        ]
        for row in month_rows
    ]
    _append_paginated_table(
        elements=elements,
        styles=styles,
        title="Resumen por mes",
        header=["Mes", "Ingresos", "Gastos", "Balance"],
        rows=month_table_rows,
        chunk_size=30,
        col_widths=[140, 105, 105, 105],
        text_column_indexes=[0],
    )

    movement_table_rows = [
        [
            escape(str(row["transaction_date"])),
            escape(str(row["transaction_type"])),
            escape(str(row["category"])),
            f"{float(row['amount']):.2f}",
            escape(str(row["description"])),
        ]
        for row in transactions
    ]
    _append_paginated_table(
        elements=elements,
        styles=styles,
        title="Movimientos",
        header=["Fecha", "Tipo", "Categoria", "Monto", "Descripcion"],
        rows=movement_table_rows,
        chunk_size=22,
        col_widths=[86, 76, 102, 70, 136],
        text_column_indexes=[0, 1, 2, 4],
    )

    document.build(elements, onFirstPage=_draw_page_number, onLaterPages=_draw_page_number)


def _append_paginated_table(
    elements: list[Any],
    styles: Any,
    title: str,
    header: list[str],
    rows: list[list[str]],
    chunk_size: int,
    col_widths: list[int],
    text_column_indexes: list[int],
) -> None:
    if not rows:
        elements.append(Paragraph(title, styles["section_title"]))
        elements.append(Paragraph("Sin datos para este bloque.", styles["body_text"]))
        elements.append(Spacer(1, 10))
        return

    for index, chunk in enumerate(_chunks(rows, chunk_size)):
        if index > 0:
            elements.append(PageBreak())

        table_title = title if index == 0 else f"{title} (continuacion {index + 1})"
        elements.append(Paragraph(table_title, styles["section_title"]))
        elements.append(
            _styled_table(
                [header, *chunk],
                col_widths=col_widths,
                text_column_indexes=text_column_indexes,
            )
        )
        elements.append(Spacer(1, 10))


def _styled_table(
    data: list[list[str]],
    col_widths: list[int],
    text_column_indexes: list[int],
) -> Table:
    table = Table(data, colWidths=col_widths, repeatRows=1)
    style_commands: list[tuple[Any, ...]] = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f3a5f")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 10),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
        ("TOPPADDING", (0, 0), (-1, 0), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f5f8fc"), colors.white]),
        ("ALIGN", (0, 1), (-1, -1), "RIGHT"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#b8c4d6")),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 1), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 5),
    ]

    for column_index in text_column_indexes:
        style_commands.append(("ALIGN", (column_index, 1), (column_index, -1), "LEFT"))

    table.setStyle(TableStyle(style_commands))
    return table


def _compute_summary_metrics(
    transactions: list[dict[str, Any]],
    category_rows: list[dict[str, Any]],
    month_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    total_income = 0.0
    total_expense = 0.0
    categories: set[str] = set()
    period_start = "N/A"
    period_end = "N/A"

    if transactions:
        dates = [str(row["transaction_date"]) for row in transactions]
        period_start = min(dates)
        period_end = max(dates)

        for row in transactions:
            amount = float(row["amount"])
            categories.add(str(row["category"]))
            if row["transaction_type"] == "income":
                total_income += amount
            else:
                total_expense += amount

    balance = total_income - total_expense
    top_expense = _top_category(category_rows, "expense")
    top_income = _top_category(category_rows, "income")

    return {
        "period_start": period_start,
        "period_end": period_end,
        "transactions_count": len(transactions),
        "total_income": total_income,
        "total_expense": total_expense,
        "balance": balance,
        "categories_count": len(categories),
        "months_count": len(month_rows),
        "top_expense": top_expense,
        "top_income": top_income,
    }


def _build_executive_summary(metrics: dict[str, Any]) -> str:
    lines = [
        f"Periodo analizado: {escape(str(metrics['period_start']))} a {escape(str(metrics['period_end']))}",
        f"Movimientos registrados: {metrics['transactions_count']}",
        f"Ingresos acumulados: {float(metrics['total_income']):.2f}",
        f"Gastos acumulados: {float(metrics['total_expense']):.2f}",
        f"Balance neto: {float(metrics['balance']):.2f}",
        f"Categorias activas: {metrics['categories_count']}",
        f"Meses con actividad: {metrics['months_count']}",
        f"Categoria con mayor gasto: {escape(str(metrics['top_expense']))}",
        f"Categoria con mayor ingreso: {escape(str(metrics['top_income']))}",
    ]
    return "<br/>".join(lines)


def _build_pdf_styles(base_styles: Any) -> dict[str, ParagraphStyle]:
    return {
        "cover_title": ParagraphStyle(
            "cover_title",
            parent=base_styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=24,
            leading=28,
            textColor=colors.white,
        ),
        "cover_subtitle": ParagraphStyle(
            "cover_subtitle",
            parent=base_styles["Normal"],
            fontName="Helvetica",
            fontSize=11,
            leading=14,
            textColor=colors.HexColor("#e6edf7"),
        ),
        "section_title": ParagraphStyle(
            "section_title",
            parent=base_styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=14,
            leading=18,
            textColor=colors.HexColor("#1f3a5f"),
            spaceAfter=6,
        ),
        "body_text": ParagraphStyle(
            "body_text",
            parent=base_styles["BodyText"],
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#243447"),
        ),
        "kpi_cell": ParagraphStyle(
            "kpi_cell",
            parent=base_styles["BodyText"],
            fontName="Helvetica",
            fontSize=10,
            leading=13,
            textColor=colors.HexColor("#0f233d"),
        ),
    }


def _build_cover_banner(metrics: dict[str, Any], styles: dict[str, ParagraphStyle]) -> Table:
    subtitle = (
        f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}<br/>"
        f"Periodo: {escape(str(metrics['period_start']))} a {escape(str(metrics['period_end']))}"
    )
    content = Paragraph(
        "<b>Reporte de gastos personales</b><br/>" + subtitle,
        styles["cover_subtitle"],
    )

    title = Paragraph("Reporte de gastos personales", styles["cover_title"])
    table = Table([[title], [content]], colWidths=[520])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#1f3a5f")),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
                ("LEFTPADDING", (0, 0), (-1, -1), 14),
                ("RIGHTPADDING", (0, 0), (-1, -1), 14),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    return table


def _build_kpi_table(metrics: dict[str, Any], styles: dict[str, ParagraphStyle]) -> Table:
    cells = [
        (
            "Balance neto",
            f"{float(metrics['balance']):.2f}",
            colors.HexColor("#d6f5e8"),
        ),
        (
            "Ingresos acumulados",
            f"{float(metrics['total_income']):.2f}",
            colors.HexColor("#dceeff"),
        ),
        (
            "Gastos acumulados",
            f"{float(metrics['total_expense']):.2f}",
            colors.HexColor("#ffe3de"),
        ),
        (
            "Movimientos registrados",
            str(metrics["transactions_count"]),
            colors.HexColor("#eef1ff"),
        ),
    ]

    data = [
        [
            Paragraph(f"<b>{cells[0][0]}</b><br/>{cells[0][1]}", styles["kpi_cell"]),
            Paragraph(f"<b>{cells[1][0]}</b><br/>{cells[1][1]}", styles["kpi_cell"]),
        ],
        [
            Paragraph(f"<b>{cells[2][0]}</b><br/>{cells[2][1]}", styles["kpi_cell"]),
            Paragraph(f"<b>{cells[3][0]}</b><br/>{cells[3][1]}", styles["kpi_cell"]),
        ],
    ]

    table = Table(data, colWidths=[260, 260])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, 0), cells[0][2]),
                ("BACKGROUND", (1, 0), (1, 0), cells[1][2]),
                ("BACKGROUND", (0, 1), (0, 1), cells[2][2]),
                ("BACKGROUND", (1, 1), (1, 1), cells[3][2]),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#9fb1c9")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#9fb1c9")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return table


def _top_category(category_rows: list[dict[str, Any]], key: str) -> str:
    if not category_rows:
        return "N/A"

    top_row = max(category_rows, key=lambda row: float(row[key]))
    top_value = float(top_row[key])
    if top_value <= 0:
        return "N/A"
    return f"{top_row['category']} ({top_value:.2f})"


def _chunks(items: list[list[str]], chunk_size: int) -> list[list[list[str]]]:
    return [items[index : index + chunk_size] for index in range(0, len(items), chunk_size)]


def _draw_page_number(canvas: Any, doc: Any) -> None:
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#b8c4d6"))
    canvas.line(doc.leftMargin, 22, A4[0] - doc.rightMargin, 22)

    canvas.setFillColor(colors.HexColor("#556273"))
    canvas.setFont("Helvetica", 9)
    canvas.drawString(doc.leftMargin, 10, "Personal expenses tracker")
    canvas.drawRightString(A4[0] - doc.rightMargin, 10, f"Pagina {doc.page}")
    canvas.restoreState()
