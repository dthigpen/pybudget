import argparse
import csv
import sys
import json
import re
from enum import Enum
from typing import Literal
from pathlib import Path
from pybudget import csv_tools
from pybudget.utils import str_to_datetime, datetime_to_str, safe_file_update_context
from pybudget.types import Transaction
from pybudget.filtering import construct_filters_query
from pybudget import suggestions
from pybudget.transactions import (
    list_transactions,
    import_transactions,
    edit_transactions,
)
import difflib
from tabulate import tabulate
from tinydb import TinyDB, Query


DATA_FILE_NAME = 'pybudget_db.json'
CONFIG_FILE_NAME = 'pybudget_config.json'
TRANSACTION_FIELDS = ['date', 'description', 'amount', 'account', 'category']
DATA_FILE_COLUMNS = ['id', 'date', 'description', 'amount', 'account', 'category']


class OutputFormat(Enum):
    DEFAULT = 'default'
    TABLE = 'table'
    CSV = 'csv'


class OutputLocation(Enum):
    STDOUT = 'stdout'
    FILE = 'file'


def __dict_to_ordered_values(d: dict, keys: list):
    return list(map(lambda k: d.get(k, ''), keys))


def __determine_output_format(
    output_format: OutputFormat, output_path: Path
) -> OutputFormat:
    if not output_format:
        if output_path:
            output_format = OutputFormat.CSV
        else:
            output_format = OutputFormat.Table
    # set the final output format variables
    to_file = output_path and output_path != '-'
    if to_file:
        if output_format == OutputFormat.TABLE:
            raise ValueError(
                f'Cannot output format "{output_format.value}" to file path {output_path}. Please remove the --output-format argument to output as CSV to the file.'
            )
        elif output_format == OutputFormat.DEFAULT:
            output_format = OutputFormat.CSV
    else:
        if output_format == OutputFormat.DEFAULT:
            output_format = OutputFormat.TABLE
    return output_format


def handle_list_transactions(args):
    row_dicts = list_transactions(
        args.db,
        args.config,
        args.filter,
        only_uncategorized=args.uncategorized,
        suggest_categories=args.suggest_categories,
    )

    output_format = args.output_format
    output_path = args.output_file
    output_format = __determine_output_format(output_format, output_path)
    columns = ['id', *TRANSACTION_FIELDS]
    if args.suggest_categories:
        columns.append('suggested_category')
    if output_format == OutputFormat.TABLE:
        output_rows_to_table(row_dicts, columns)
    elif output_format == OutputFormat.CSV:
        output_rows_as_csv(row_dicts, columns, output_path)
    else:
        raise ValueError(f'Unrecognized output format: {output_format.value}')


def output_rows_to_table(row_dicts: list[dict], columns: list[str], title: str = None):
    alias_mapping = {'id': 'ID', 'suggesed_category': 'Suggested'}
    headers = list(map(lambda c: alias_mapping.get(c, c.title()), columns))
    rows = []
    for row_dict in row_dicts:
        values = __dict_to_ordered_values(row_dict, columns)
        rows.append(values)

    print(tabulate(rows, headers=headers, tablefmt='github'))


def output_rows_as_csv(row_dicts: list[dict], columns: list[str], output_path: Path):
    empty_values = {c: '' for c in columns}
    to_stdout = not output_path or output_path == '-'
    output_file = sys.stdout if to_stdout else open(output_path, 'w')
    try:
        csv_writer = csv.DictWriter(output_file, fieldnames=columns)
        csv_writer.writeheader()
        for row_dict in row_dicts:
            row_dict = empty_values | row_dict
            csv_writer.writerow(row_dict)
    finally:
        if not to_stdout and output_file:
            output_file.close()


def handle_edit_transaction(args):
    if args.transaction_id is None and args.from_path is None:
        raise ValueError(
            'A transaction_id or --from argument must be applied. See --help for details.'
        )
    with safe_file_update_context(args.db, dry_run=args.dry_run) as db_path:
        updated_txn_str_dicts = edit_transactions(
            db_path,
            args.config,
            args.from_path,
            args.transaction_id,
            new_date=args.date,
            new_amount=args.amount,
            new_account=args.account,
            new_category=args.category,
        )
        output_rows_to_table(
            updated_txn_str_dicts, DATA_FILE_COLUMNS, title='Updated Transactions'
        )


def handle_import_transactions(args):
    with safe_file_update_context(args.db, dry_run=args.dry_run) as db_path:
        new_txn_str_dicts = list(
            import_transactions(
                db_path,
                args.config,
                args.csv_paths,
                importer_name=args.importer,
            )
        )
        added_ids = list(map(lambda d: d['id'], new_txn_str_dicts))
        # table needs str fields only so convert txn -> dict -> str value dict
        columns = ['id', *TRANSACTION_FIELDS]
        output_rows_to_table(new_txn_str_dicts, columns)
        print(f'Imported {len(added_ids)} new transactions')


def handle_init(args):
    starter_config = {
        'importers': [
            {
                'name': 'My Bank Checking',
                'descriptionColumn': 'Description',
                'amountColumn': 'Amount',
                'accountValue': 'My Bank Checking',
                'dateColumn': 'Date',
                'dateFormat': '%Y-%m-%d',
            }
        ],
    }
    config_path = Path.cwd() / CONFIG_FILE_NAME
    if config_path.is_file():
        print('Config file already exists at {config_path}')
    else:
        config_path.write_text(json.dumps(starter_config, indent=4))
        print(f'Created starter config at {config_path}')
    db_path = Path.cwd() / DATA_FILE_NAME
    if db_path.is_file():
        print('Database file already exists at {db_path}')
    else:
        db = TinyDB(db_path)
        transactions = db.table('transactions')
        categories = db.table('categories')
        print(f'Created database file at {db_path}')


def handle_new_transaction(args):
    print(f'Adding a new transaction to {args.transactions}')


def handle_generate_report(args):
    print(
        f'Generating {args.type} report for {args.period} using transactions from {args.transactions}'
    )


def parse_args(system_args):
    def add_common_arguments(parser):
        parser.add_argument(
            '--db',
            type=Path,
            default=Path.cwd() / DATA_FILE_NAME,
            help='Path to the pybudget database file',
        )
        parser.add_argument(
            '--config',
            type=Path,
            default=Path.cwd() / CONFIG_FILE_NAME,
            help='Path to the config file',
        )

    parser = argparse.ArgumentParser(description='pybudget CLI')
    parser.set_defaults(func=lambda args: parser.print_help())
    add_common_arguments(parser)
    subparsers = parser.add_subparsers(dest='command')

    # Init parser
    init_parser = subparsers.add_parser(
        'init', help='Initialize a starter pybudget.json'
    )
    init_parser.set_defaults(func=handle_init)

    # Import group
    import_parser = subparsers.add_parser('import', help='Import data')
    import_sub = import_parser.add_subparsers(dest='import_target', required=True)

    import_transactions_parser = import_sub.add_parser(
        'transactions', aliases=['t', 'ts', 'txn', 'txns'], help='Import transactions'
    )
    add_common_arguments(import_transactions_parser)
    import_transactions_parser.add_argument(
        'csv_paths', nargs='+', type=Path, help='Path(s) to CSV files to import'
    )
    import_transactions_parser.add_argument(
        '--importer', help='Name of the importer defined in config.json'
    )
    import_transactions_parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Run through the operation without actually persisting any changes',
    )
    import_transactions_parser.set_defaults(func=handle_import_transactions)

    # List command
    list_parser = subparsers.add_parser('list', help='list data')
    list_sub = list_parser.add_subparsers(dest='list_target', required=True)

    list_transactions_parser = list_sub.add_parser(
        'transactions', aliases=['t', 'ts', 'txn', 'txns'], help='list transactions'
    )
    add_common_arguments(list_transactions_parser)
    list_transactions_parser.add_argument(
        '--filter',
        action='append',
        help='Adda filter expression like "field~value", "amount>100", etc. Can be used multiple times.',
    )
    list_transactions_parser.add_argument(
        '--uncategorized',
        action='store_true',
        help='A filter to only show uncategorized transactions',
    )
    list_transactions_parser.add_argument(
        '-s',
        '--suggest-categories',
        action='store_true',
        help='Add a column for suggested categories for the uncategorized',
    )
    list_transactions_parser.add_argument(
        '-f',
        '--output-format',
        choices=list(OutputFormat),
        type=OutputFormat,
        default=OutputFormat.DEFAULT,
        help='The format of the output. If an output file is specified, this option is ignored and CSV format is used.',
    )
    list_transactions_parser.add_argument(
        '-o',
        '--output-file',
        type=Path,
        help='The file to output to instead of stdout. File will be in CSV format.',
    )

    list_transactions_parser.set_defaults(func=handle_list_transactions)

    # Edit command
    edit_parser = subparsers.add_parser('edit', help='Edit a transaction')
    edit_sub = edit_parser.add_subparsers(dest='edit_target', required=True)
    edit_txns_parser = edit_sub.add_parser(
        'transactions', aliases=['t', 'ts', 'txn', 'txns'], help='list transactions'
    )
    add_common_arguments(edit_txns_parser)
    edit_source = edit_txns_parser.add_mutually_exclusive_group(required=True)
    edit_source.add_argument(
        '--id', dest='transaction_id', help='ID of the transaction to edit'
    )
    edit_source.add_argument(
        '--from', dest='from_path', help='Apply edits from either a file or from stdin'
    )
    edit_txns_parser.add_argument(
        '--amount', type=float, help='A new amount to apply to the transaction'
    )
    edit_txns_parser.add_argument(
        '--description', help='A new description to apply to the transaction.'
    )
    edit_txns_parser.add_argument(
        '--date',
        help='A new date to apply to the transaction. In the format YYYY-MM-DD',
    )
    edit_txns_parser.add_argument(
        '--account', help='A new account to apply to the transaction.'
    )
    edit_txns_parser.add_argument(
        '--category',
        help='A new category to apply to the transaction, or use "" for uncategorized.',
    )
    edit_txns_parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Run through the operation without actually persisting any changes.',
    )
    edit_txns_parser.set_defaults(func=handle_edit_transaction)

    return parser.parse_args(system_args)


def main():
    args = parse_args(sys.argv[1:])
    args.func(args)


if __name__ == '__main__':
    main()
