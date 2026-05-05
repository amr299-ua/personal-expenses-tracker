from __future__ import annotations

import argparse
import sys
from datetime import date
from typing import Any

import logging

from expenses_tracker.charts import generate_charts
from expenses_tracker.db import ExpenseDatabase, TransactionInput
from expenses_tracker.exporters import export_reports
from expenses_tracker.i18n import list_languages, normalize_language, tr

logger = logging.getLogger("expenses_tracker.cli")


def _localize_transaction_type(value: str, language: str) -> str:
    if value == "income":
        return tr(language, "type_income")
    if value == "expense":
        return tr(language, "type_expense")
    return value


def _build_parser(language: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="expenses",
        description=tr(language, "cli_description"),
    )
    parser.add_argument(
        "--db-path",
        default="data/expenses.db",
        help=tr(language, "arg_db_path"),
    )
    parser.add_argument(
        "--lang",
        default=language,
        help=tr(language, "arg_lang"),
    )
    parser.add_argument(
        "--list-languages",
        action="store_true",
        help=tr(language, "arg_list_languages"),
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init-db", help=tr(language, "cmd_init_db"))

    add_parser = subparsers.add_parser("add", help=tr(language, "cmd_add"))
    add_parser.add_argument("--type", choices=["income", "expense"], required=True)
    add_parser.add_argument("--amount", type=float, required=True)
    add_parser.add_argument("--category", required=True)
    add_parser.add_argument("--date", required=True, help=tr(language, "arg_date"))
    add_parser.add_argument("--description", default="")

    list_parser = subparsers.add_parser("list", help=tr(language, "cmd_list"))
    list_parser.add_argument("--limit", type=_positive_int, default=20)

    subparsers.add_parser("balance", help=tr(language, "cmd_balance"))
    subparsers.add_parser("stats", help=tr(language, "cmd_stats"))

    plot_parser = subparsers.add_parser("plot", help=tr(language, "cmd_plot"))
    plot_parser.add_argument(
        "--type",
        dest="plot_type",
        choices=["category", "month", "bar", "line", "pie", "scatter", "bar3d", "all"],
        default="all",
        help=tr(language, "arg_plot_type"),
    )
    plot_parser.add_argument(
        "--output-dir",
        default="reports",
        help=tr(language, "arg_output_dir"),
    )

    export_parser = subparsers.add_parser("export", help=tr(language, "cmd_export"))
    export_parser.add_argument(
        "--format",
        dest="export_format",
        choices=["excel", "csv", "pdf", "all"],
        default="all",
        help=tr(language, "arg_export_format"),
    )
    export_parser.add_argument(
        "--output-dir",
        default="reports",
        help=tr(language, "arg_output_dir"),
    )

    return parser


def main() -> int:
    pre_parser = argparse.ArgumentParser(add_help=False)
    pre_parser.add_argument("--lang", default="en")
    pre_parser.add_argument("--list-languages", action="store_true")

    pre_args, _ = pre_parser.parse_known_args(sys.argv[1:])
    parser_language = normalize_language(pre_args.lang)

    if pre_args.list_languages:
        print(tr(parser_language, "supported_languages"))
        for code, name in list_languages():
            print(f"- {code}: {name}")
        return 0

    parser = _build_parser(parser_language)
    args = parser.parse_args()
    language = normalize_language(args.lang)

    database = ExpenseDatabase(args.db_path)
    logger.info("CLI command", extra={"command": args.command, "db_path": str(database.db_path)})

    if args.command == "init-db":
        database.initialize()
        logger.info("Database initialized", extra={"path": str(database.db_path)})
        print(tr(language, "db_initialized", path=database.db_path))
        return 0

    if args.command == "add":
        database.initialize()
        try:
            transaction_date = _parse_date(args.date, language)
            transaction_id = database.add_transaction(
                TransactionInput(
                    amount=args.amount,
                    transaction_type=args.type,
                    category=args.category,
                    transaction_date=transaction_date,
                    description=args.description,
                ),
                language=language,
            )
        except ValueError as error:
            logger.warning("Add transaction failed", extra={"error": str(error)})
            print(tr(language, "error_invalid_data"))
            print(str(error))
            return 1

        logger.info("Transaction added", extra={"id": transaction_id})
        print(tr(language, "transaction_saved_id", id=transaction_id))
        return 0

    if args.command == "list":
        database.initialize()
        rows = database.fetch_transactions(limit=args.limit)
        logger.info("Listed transactions", extra={"count": len(rows)})
        if not rows:
            print(tr(language, "no_transactions"))
            return 0

        for row in rows:
            localized_type = _localize_transaction_type(str(row["transaction_type"]), language)
            print(
                f"[{row['id']}] {row['transaction_date']} | {localized_type} | "
                f"{row['category']} | {row['amount']:.2f} | {row['description']}"
            )
        return 0

    if args.command == "balance":
        database.initialize()
        balance = database.get_balance()
        logger.info("Balance queried", extra={"balance": balance})
        print(tr(language, "current_balance", amount=balance))
        return 0

    if args.command == "stats":
        database.initialize()
        _print_stats(database, language)
        return 0

    if args.command == "plot":
        database.initialize()
        _generate_plots(database, args.plot_type, args.output_dir, language)
        return 0

    if args.command == "export":
        database.initialize()
        _export_reports(database, args.export_format, args.output_dir, language)
        return 0

    parser.print_help()
    return 1


def _parse_date(raw_value: str, language: str) -> date:
    try:
        return date.fromisoformat(raw_value)
    except ValueError as error:
        raise ValueError(tr(language, "invalid_date")) from error


def _positive_int(raw_value: str) -> int:
    try:
        value = int(raw_value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be an integer") from error

    if value <= 0:
        raise argparse.ArgumentTypeError("must be greater than 0")
    return value


def _print_stats(database: ExpenseDatabase, language: str) -> None:
    print(tr(language, "stats_general_title"))
    print(tr(language, "current_balance", amount=database.get_balance()))
    print()

    _print_category_stats(database.get_totals_by_category(), language)
    print()
    _print_month_stats(database.get_totals_by_month(), language)


def _print_category_stats(rows: list[dict[str, Any]], language: str) -> None:
    print(tr(language, "stats_category_title"))
    if not rows:
        print(tr(language, "stats_no_data"))
        return

    for row in rows:
        print(tr(language, "stats_category_row", **row))


def _print_month_stats(rows: list[dict[str, Any]], language: str) -> None:
    print(tr(language, "stats_month_title"))
    if not rows:
        print(tr(language, "stats_no_data"))
        return

    for row in rows:
        print(tr(language, "stats_month_row", **row))


def _generate_plots(database: ExpenseDatabase, plot_type: str, output_dir: str, language: str) -> None:
    category_rows = database.get_totals_by_category()
    month_rows = database.get_totals_by_month()

    if not category_rows and not month_rows:
        print(tr(language, "no_chart_data"))
        return

    generated_files = generate_charts(
        category_rows=category_rows,
        month_rows=month_rows,
        output_dir=output_dir,
        kind=plot_type,
        language=language,
    )

    if not generated_files:
        print(tr(language, "no_chart_generated"))
        return

    for file_path in generated_files:
        print(tr(language, "chart_generated", path=file_path))


def _export_reports(database: ExpenseDatabase, export_format: str, output_dir: str, language: str) -> None:
    transactions = database.fetch_transactions(limit=None)
    category_rows = database.get_totals_by_category()
    month_rows = database.get_totals_by_month()

    if not transactions:
        print(tr(language, "no_report_data"))
        return

    generated_files = export_reports(
        transactions=transactions,
        category_rows=category_rows,
        month_rows=month_rows,
        output_dir=output_dir,
        fmt=export_format,
        language=language,
    )

    if not generated_files:
        print(tr(language, "no_report_generated"))
        return

    for file_path in generated_files:
        print(tr(language, "report_generated", path=file_path))


if __name__ == "__main__":
    raise SystemExit(main())
