from __future__ import annotations

import argparse
from datetime import date
from typing import Any

from expenses_tracker.charts import generate_charts
from expenses_tracker.db import ExpenseDatabase, TransactionInput
from expenses_tracker.exporters import export_reports


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="expenses",
        description="Control de gastos personal en terminal",
    )
    parser.add_argument(
        "--db-path",
        default="data/expenses.db",
        help="Ruta del archivo SQLite (default: data/expenses.db)",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init-db", help="Inicializa la base de datos")

    add_parser = subparsers.add_parser("add", help="Agrega un ingreso o gasto")
    add_parser.add_argument("--type", choices=["income", "expense"], required=True)
    add_parser.add_argument("--amount", type=float, required=True)
    add_parser.add_argument("--category", required=True)
    add_parser.add_argument("--date", required=True, help="Formato YYYY-MM-DD")
    add_parser.add_argument("--description", default="")

    list_parser = subparsers.add_parser("list", help="Lista movimientos recientes")
    list_parser.add_argument("--limit", type=int, default=20)

    subparsers.add_parser("balance", help="Muestra el balance actual")
    subparsers.add_parser("stats", help="Muestra estadisticas por categoria y por mes")

    plot_parser = subparsers.add_parser("plot", help="Genera graficas PNG con matplotlib")
    plot_parser.add_argument(
        "--type",
        dest="plot_type",
        choices=["category", "month", "bar", "line", "pie", "scatter", "bar3d", "all"],
        default="all",
        help="Tipo de grafica a generar",
    )
    plot_parser.add_argument(
        "--output-dir",
        default="reports",
        help="Carpeta de salida para las graficas",
    )

    export_parser = subparsers.add_parser("export", help="Exporta reportes a Excel y/o PDF")
    export_parser.add_argument(
        "--format",
        dest="export_format",
        choices=["excel", "pdf", "all"],
        default="all",
        help="Formato de salida del reporte",
    )
    export_parser.add_argument(
        "--output-dir",
        default="reports",
        help="Carpeta de salida para reportes",
    )

    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    database = ExpenseDatabase(args.db_path)

    if args.command == "init-db":
        database.initialize()
        print(f"Base de datos inicializada en: {database.db_path}")
        return 0

    if args.command == "add":
        database.initialize()
        transaction_date = _parse_date(args.date)
        transaction_id = database.add_transaction(
            TransactionInput(
                amount=args.amount,
                transaction_type=args.type,
                category=args.category,
                transaction_date=transaction_date,
                description=args.description,
            )
        )
        print(f"Movimiento registrado con id: {transaction_id}")
        return 0

    if args.command == "list":
        database.initialize()
        rows = database.fetch_transactions(limit=args.limit)
        if not rows:
            print("No hay movimientos registrados.")
            return 0

        for row in rows:
            print(
                f"[{row['id']}] {row['transaction_date']} | {row['transaction_type']} | "
                f"{row['category']} | {row['amount']:.2f} | {row['description']}"
            )
        return 0

    if args.command == "balance":
        database.initialize()
        balance = database.get_balance()
        print(f"Balance actual: {balance:.2f}")
        return 0

    if args.command == "stats":
        database.initialize()
        _print_stats(database)
        return 0

    if args.command == "plot":
        database.initialize()
        _generate_plots(database, args.plot_type, args.output_dir)
        return 0

    if args.command == "export":
        database.initialize()
        _export_reports(database, args.export_format, args.output_dir)
        return 0

    parser.print_help()
    return 1


def _parse_date(raw_value: str) -> date:
    try:
        return date.fromisoformat(raw_value)
    except ValueError as error:
        raise ValueError(
            "Fecha invalida. Usa el formato YYYY-MM-DD."
        ) from error


def _print_stats(database: ExpenseDatabase) -> None:
    print("=== RESUMEN GENERAL ===")
    print(f"Balance actual: {database.get_balance():.2f}")
    print()

    _print_category_stats(database.get_totals_by_category())
    print()
    _print_month_stats(database.get_totals_by_month())


def _print_category_stats(rows: list[dict[str, Any]]) -> None:
    print("=== TOTAL POR CATEGORIA ===")
    if not rows:
        print("No hay datos para mostrar.")
        return

    for row in rows:
        print(
            f"{row['category']}: ingresos={row['income']:.2f} | "
            f"gastos={row['expense']:.2f} | balance={row['balance']:.2f}"
        )


def _print_month_stats(rows: list[dict[str, Any]]) -> None:
    print("=== TOTAL POR MES ===")
    if not rows:
        print("No hay datos para mostrar.")
        return

    for row in rows:
        print(
            f"{row['month']}: ingresos={row['income']:.2f} | "
            f"gastos={row['expense']:.2f} | balance={row['balance']:.2f}"
        )


def _generate_plots(database: ExpenseDatabase, plot_type: str, output_dir: str) -> None:
    category_rows = database.get_totals_by_category()
    month_rows = database.get_totals_by_month()

    if not category_rows and not month_rows:
        print("No hay datos suficientes para generar graficas.")
        return

    generated_files = generate_charts(
        category_rows=category_rows,
        month_rows=month_rows,
        output_dir=output_dir,
        kind=plot_type,
    )

    if not generated_files:
        print("No se generaron graficas para el tipo solicitado.")
        return

    for file_path in generated_files:
        print(f"Grafica generada: {file_path}")


def _export_reports(database: ExpenseDatabase, export_format: str, output_dir: str) -> None:
    transactions = database.fetch_transactions(limit=None)
    category_rows = database.get_totals_by_category()
    month_rows = database.get_totals_by_month()

    if not transactions:
        print("No hay movimientos para exportar reportes.")
        return

    generated_files = export_reports(
        transactions=transactions,
        category_rows=category_rows,
        month_rows=month_rows,
        output_dir=output_dir,
        fmt=export_format,
    )

    if not generated_files:
        print("No se generaron reportes para el formato solicitado.")
        return

    for file_path in generated_files:
        print(f"Reporte generado: {file_path}")


if __name__ == "__main__":
    raise SystemExit(main())
