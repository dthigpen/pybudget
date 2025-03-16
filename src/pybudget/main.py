import argparse
import csv
import itertools
from pathlib import Path

import rich
from rich.console import Console, Group
from rich.table import Table
from rich.text import Text
from rich.panel import Panel
from rich import prompt

TRANSACTION_FIELDS = ["date", "description", "amount", "account", "category"]
DEFAULT_TRANSACTION_FIELD_NAMES = [
    "Date",
    "Decription",
    "Amount",
    "Account",
    "Category",
]
DEFAULT_TRANSACTION_FIELD_NAMES_MAP = {
    f.lower(): f for f in DEFAULT_TRANSACTION_FIELD_NAMES
}

DEFAULT_CATGORIES_FIELD_NAMES = ["Name", "Type", "Goal"]
DEFAULT_CATGORIES_FIELD_NAMES_MAP = {
    f.lower(): f for f in DEFAULT_CATGORIES_FIELD_NAMES
}


def __validate_txn(txn: dict, category_names: set):
    pass


def __read_transactions_csv(csv_path: Path, column_names=None, default_values=None):
    column_names = column_names or {}
    default_values = default_values or {}
    with open(csv_path, newline="") as csvfile:
        reader = csv.DictReader(csvfile)
        normalized_row = {}
        for row in reader:
            for field in TRANSACTION_FIELDS:
                if column_names.get(field):
                    col_name = column_names[field]
                    normalized_row[field] = row[col_name]
                else:
                    if row.get(field):
                        normalized_row[field] = row[field]
                    elif row.get(field.title()):
                        normalized_row[field] = row[field.title()]

                if field not in normalized_row and field in default_values:
                    normalized_row[field] = default_values[field]

            required_fields = set(TRANSACTION_FIELDS) - set(["category"])
            actual_fields = set(normalized_row.keys())
            missing_fields = required_fields - actual_fields
            if missing_fields:
                raise ValueError(
                    f"Expected to receive column names or defaults for {csv_path}. Missing field {missing_fields}"
                )
            # transform amount to float
            # normalized_row['amount'] = float(normalized_row['amount'])
            # TODO validate date is in correct format: date, category exists or is unassigned or empty
            yield dict(normalized_row)


def __create_transactions_table() -> Table:
    table = Table(show_header=True, title="Transactions")
    # TODO make sure order is the same as TRANSACTIONS_HEADER
    table.add_column("Date", width=12)
    table.add_column("Description")
    table.add_column("Amount", justify="right")
    table.add_column("Account", justify="right")
    table.add_column("Category")
    return table


def __dict_to_ordered_values(d: dict, keys: list):
    return list(map(lambda k: d[k], keys))


def cmd_list_transactions(args):
    table = __create_transactions_table()
    for row in __read_transactions_csv(args.transactions):
        row["amount"] = "{0:.2f}".format(float(row["amount"]))
        values = __dict_to_ordered_values(row, TRANSACTION_FIELDS)
        table.add_row(*values)

    console = Console()
    console.print(table)

    print(f"Listing transactions from {args.transactions}")


def cmd_edit_transaction(args):
    print(f"Editing transaction in {args.transactions}: {args.transaction_id}")


def cmd_delete_transaction(args):
    print(f"Deleting transaction in {args.transactions}: {args.transaction_id}")


def cmd_categorize_transactions(args):
    print(f"Assigning categories in {args.transactions} using {args.categories}")


def cmd_import_transactions(args):
    print(f"Importing transactions from {args.import_paths} into {args.transactions}")
    # build up column names mapping
    column_names = {}
    if args.date_column:
        column_names["date"] = args.date_column
    if args.desc_column:
        column_names["description"] = args.desc_column
    if args.amount_column:
        column_names["amount"] = args.amount_column
    if args.account_column:
        column_names["account"] = args.account_column
    if args.category_column:
        column_names["category"] = args.category_column
    # build up defaults
    default_values = {}
    if args.account_value:
        default_values["account"] = args.account_value
    if args.category_value:
        default_values["category"] = args.category_value

    if args.transactions.is_file():
        existing_transactions = [r for r in __read_transactions_csv(args.transactions)]
    else:
        existing_transactions = []
    new_transactions = []
    for import_path in args.import_paths:
        for row in __read_transactions_csv(
            import_path, column_names=column_names, default_values=default_values
        ):
            if args.flip_sign:
                orig_amount = float(row['amount'])
                row['amount'] = "{0:.2f}".format(-1 * orig_amount)
            new_transactions.append(row)

    # sort transactions
    new_transactions = __sort_transactions(new_transactions)

    # print new transactions
    console = Console()
    table = __create_transactions_table()
    for txn in new_transactions:
        values = __dict_to_ordered_values(txn, TRANSACTION_FIELDS)
        table.add_row(*values)
    console.print(table)

    # find duplicates in existing transactions
    duplicates = []
    for txn in new_transactions:
        if txn in existing_transactions:
            duplicates.append(txn)

    if duplicates:
        table = __create_transactions_table()
        table.title = 'Duplicates With Existing'
        for txn in duplicates:
            values = __dict_to_ordered_values(txn, TRANSACTION_FIELDS)
            table.add_row(*values)
        console.print(table)
    # summarize output
    def get_month(txn):
        return txn['date'][:7]
    # NOTE it should already be sorted from above
    transactions_by_month = {}
    for k, g in itertools.groupby(new_transactions, key=get_month):
        if k not in transactions_by_month:
            transactions_by_month[k] = []
        transactions_by_month[k].extend(list(g))

    # find count by month
    month_counts = {k:len(v) for k,v in transactions_by_month.items()}
    months = list(map(lambda e: f'({e[1]}) {e[0]}', sorted(month_counts.items(), key=lambda x: x[0])))

    summary_text = Text("Import Summary", justify="center")
    console.print(
        Panel(
            Group(
                summary_text,
                Text(f"Transactions: {len(new_transactions)}"),
                Text(f"Months: {', '.join(months)}"),
                Text(f"Duplicates: {len(duplicates)} (Already in existing transactions)"),
            )
        )
    )
    do_import = prompt.Confirm.ask(f'Import all {len(new_transactions)} transactions?')
    if do_import:
        existing_transactions.extend(new_transactions)
        __write_transactions_to_file(existing_transactions, args.transactions)
        console.print(Text('Done!'))
    # console.print()

def __sort_transactions(transactions: list) -> list:
    return sorted(transactions, key=lambda r: (r['date'], r['description']))

def __write_transactions_to_file(all_transactions: list, output_file_path):
    all_transactions = __sort_transactions(all_transactions)
    with open(output_file_path, 'w') as output_file:
        dict_writer = csv.DictWriter(output_file, TRANSACTION_FIELDS)
        dict_writer.writeheader()
        dict_writer.writerows(all_transactions)
        
def cmd_new_transaction(args):
    print(f"Adding a new transaction to {args.transactions}")


def cmd_list_categories(args):
    print(f"Listing categories from {args.categories}")


def cmd_new_category(args):
    print(f"Creating a new category in {args.categories}")


def cmd_generate_report(args):
    print(
        f"Generating {args.type} report for {args.period} using transactions from {args.transactions}"
    )


def cmd_backup(args):
    print(f"Creating a backup at {args.destination}")


def existing_file(p):
    p = Path(p)
    if p.is_file():
        return p
    raise argparse.ArgumentTypeError(f"{p} must be an existing file path")


def main():
    parser = argparse.ArgumentParser(
        prog="pybudget", description="Simple Budget & Expense Tracker"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Transactions group
    transactions_parser = subparsers.add_parser(
        "transactions", help="Manage transactions"
    )
    transactions_subparsers = transactions_parser.add_subparsers(
        dest="action", required=True
    )

    list_parser = transactions_subparsers.add_parser("list", help="List transactions")
    list_parser.add_argument(
        "transactions", type=existing_file, help="Path to transactions CSV file"
    )
    list_parser.set_defaults(func=cmd_list_transactions)

    edit_parser = transactions_subparsers.add_parser("edit", help="Edit a transaction")
    edit_parser.add_argument(
        "transactions", type=Path, help="Path to transactions CSV file"
    )
    edit_parser.add_argument("transaction_id", help="ID of the transaction to edit")
    edit_parser.set_defaults(func=cmd_edit_transaction)

    delete_parser = transactions_subparsers.add_parser(
        "delete", help="Delete a transaction"
    )
    delete_parser.add_argument(
        "transactions", type=Path, help="Path to transactions CSV file"
    )
    delete_parser.add_argument("transaction_id", help="ID of the transaction to delete")
    delete_parser.set_defaults(func=cmd_delete_transaction)

    categorize_parser = transactions_subparsers.add_parser(
        "categorize", help="Categorize transactions"
    )
    categorize_parser.add_argument(
        "transactions", type=Path, help="Path to transactions CSV file"
    )
    categorize_parser.add_argument(
        "-c",
        "--categories",
        type=Path,
        required=True,
        help="Path to categories CSV file",
    )
    categorize_parser.set_defaults(func=cmd_categorize_transactions)

    import_parser = transactions_subparsers.add_parser(
        "import", help="Import transactions from another CSV"
    )
    import_parser.add_argument(
        "transactions", type=Path, help="Path to transactions CSV file"
    )
    import_parser.add_argument(
        "--import-paths",
        type=existing_file,
        required=True,
        nargs="+",
        help="Paths to CSV files to import from",
    )
    import_parser.add_argument(
        "--desc-column", help="Column name for transaction descriptions"
    )
    import_parser.add_argument(
        "--date-column", help="Column name for transaction dates"
    )
    import_parser.add_argument(
        "--amount-column", help="Column name for transaction amounts"
    )
    import_parser.add_argument("--account-column", help="Column name for account names")
    import_parser.add_argument(
        "--category-column", help="Column name for account names"
    )
    # TODO should -value be added for the rest?
    import_parser.add_argument(
        "--account-value", help="Literal value to use for the Account if not in the CSV"
    )
    import_parser.add_argument(
        "--category-value",
        help="Literal value to use for the Category if not in the CSV, or leave out to assign later",
    )
    import_parser.add_argument(
            "--flip-sign", action='store_true', help="Flip the sign of the transactions. Useful for credit card statements since those 'expenses' are usually positive instead of negative"
        )
    import_parser.set_defaults(func=cmd_import_transactions)

    new_txn_parser = transactions_subparsers.add_parser(
        "new", help="Add a new transaction"
    )
    new_txn_parser.add_argument(
        "transactions", type=Path, help="Path to transactions CSV file"
    )
    new_txn_parser.set_defaults(func=cmd_new_transaction)

    # Categories group
    categories_parser = subparsers.add_parser("categories", help="Manage categories")
    categories_subparsers = categories_parser.add_subparsers(
        dest="action", required=True
    )

    list_categories_parser = categories_subparsers.add_parser(
        "list", help="List all categories"
    )
    list_categories_parser.add_argument(
        "categories", type=Path, help="Path to categories CSV file"
    )
    list_categories_parser.set_defaults(func=cmd_list_categories)

    new_category_parser = categories_subparsers.add_parser(
        "new", help="Create a new category"
    )
    new_category_parser.add_argument(
        "categories", type=Path, help="Path to categories CSV file"
    )
    new_category_parser.set_defaults(func=cmd_new_category)

    # Reports group
    reports_parser = subparsers.add_parser("reports", help="Generate spending reports")
    reports_subparsers = reports_parser.add_subparsers(dest="action", required=True)

    report_generate_parser = reports_subparsers.add_parser(
        "generate", help="Generate a spending report"
    )
    report_generate_parser.add_argument(
        "transactions", type=Path, help="Path to transactions CSV file"
    )
    report_generate_parser.add_argument(
        "--type",
        choices=["monthly", "yearly", "category"],
        default="monthly",
        help="Type of report",
    )
    report_generate_parser.add_argument(
        "--period", help="Specific period (e.g., '2024-03' for March 2024)"
    )
    report_generate_parser.set_defaults(func=cmd_generate_report)

    # Backup group
    backup_parser = subparsers.add_parser("backup", help="Backup data")
    backup_subparsers = backup_parser.add_subparsers(dest="action", required=True)

    backup_create_parser = backup_subparsers.add_parser(
        "create", help="Create a backup"
    )
    backup_create_parser.add_argument(
        "destination", type=Path, help="Backup file or directory"
    )
    backup_create_parser.set_defaults(func=cmd_backup)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
