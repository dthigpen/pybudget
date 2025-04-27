import argparse
import csv
import sys
import json
from enum import Enum
from typing import Literal
from pathlib import Path
from pybudget import database, csv_tools
from pybudget.utils import str_to_datetime
from pybudget.types import Transaction
import difflib

from rich import box
from rich.console import Console
from rich.table import Table

DATA_FILE_NAME = 'pyb_transactions.csv'
CONFIG_FILE_NAME = 'pyb_config.json'
TRANSACTION_FIELDS = ['date', 'description', 'amount', 'account', 'category']
DATA_FILE_COLUMNS = ['id', 'date', 'description', 'amount', 'account', 'category']


class OutputFormat(Enum):
    DEFAULT = 'default'
    TABLE = 'table'
    CSV = 'csv'


class OutputLocation(Enum):
    STDOUT = 'stdout'
    FILE = 'file'


def __create_transactions_table(title: str = None) -> Table:
    title = title or 'Transactions'
    table = Table(show_header=True, box=box.MARKDOWN, title=title)
    table.add_column('ID', no_wrap=True)
    table.add_column('Date', no_wrap=True, width=12)
    table.add_column('Description', no_wrap=True)
    table.add_column('Amount', no_wrap=True, justify='right')
    table.add_column('Account', no_wrap=True, justify='right')
    table.add_column('Category', no_wrap=True)
    return table


def __dict_to_ordered_values(d: dict, keys: list):
    return list(map(lambda k: d[k], keys))


def handle_list_transactions(args):
    list_transactions(
        args.data,
        args.config,
        args.filter,
        only_uncategorized=args.uncategorized,
        output_format=args.output_format,
        output_path=args.output_file,
        suggest_categories=args.suggest_categories,
    )


def parse_filter_arg(filter_str):
    import re

    match = re.match(r'(\w+)([!=<>~]{1,2})(.*)', filter_str)
    if not match:
        raise ValueError(f'Invalid filter: {filter_str}')
    return match.group(1), match.group(2), match.group(3).strip()


def match_filters(txn, filters, field_types=None, strict=False):
    for field, op, value in filters:
        row_val = getattr(txn, field)

        # Determine type
        if field_types and field in field_types:
            field_type = field_types[field]
        else:
            # Default: string
            field_type = 'string'
        if row_val is None:
            if field_type == 'string':
                # coerce None to '' if doing a string search
                row_val = ''
            else:
                return False

        try:
            if field_type == 'float':
                row_val = float(row_val)
                value = float(value)
            elif field_type == 'date':
                value = str_to_datetime(value)
            elif field_type == 'int':
                row_val = int(row_val)
                value = int(value)
            else:
                row_val = str(row_val).lower()
                value = str(value).lower()
        except (ValueError, TypeError) as e:
            if strict:
                raise ValueError(
                    f"Error parsing field '{field}' with value '{row_val}' and filter value '{value}': {e}"
                )
            return False

        operators = {'=', '!=', '>', '<', '>=', '<=', '~', '!~'}
        if strict and op not in operators:
            raise ValueError(f'Unknown filter operator: {op}')

        if op == '=' and row_val != value:
            return False
        elif op == '!=' and row_val == value:
            return False
        elif op == '>' and row_val <= value:
            return False
        elif op == '<' and row_val >= value:
            return False
        elif op == '>=' and row_val < value:
            return False
        elif op == '<=' and row_val > value:
            return False
        elif op == '~' and value not in row_val:
            return False
        elif op == '!~' and value in row_val:
            return False

    return True


def list_transactions(
    data_path: Path,
    config_path: Path,
    filters: list[str] = None,
    only_uncategorized=False,
    output_format: OutputFormat = None,
    output_path: Path = None,
    suggest_categories: bool = False,
):
    filters = [parse_filter_arg(f) for f in filters] if filters else []

    transactions_csv = csv_tools.TransactionsCSV(data_path)
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

    columns = ['id', *TRANSACTION_FIELDS]
    if suggest_categories:
        columns.append('suggested_category')

    field_types = {
        'id': 'string',
        'date': 'date',
        'description': 'string',
        'amount': 'float',
        'category': 'string',
        'account': 'string',
    }
    # TODO do not keep all results in memory, use generator
    row_dicts = []
    for t in transactions_csv.read_many():
        if (only_uncategorized and t.category) or (
            filters
            and not match_filters(t, filters, field_types=field_types, strict=True)
        ):
            continue
        dict_values = t.to_str_dict()
        if suggest_categories:
            dict_values['suggested_category'] = ''
        row_dicts.append(dict_values)

    # sort by date before output
    row_dicts.sort(key=lambda t: t['date'])
    if output_format == OutputFormat.TABLE:
        output_rows_to_table(row_dicts, columns)
    elif output_format == OutputFormat.CSV:
        output_rows_as_csv(row_dicts, columns, output_path)
    else:
        raise ValueError(f'Unrecognized output format: {output_format.value}')


def output_rows_to_table(row_dicts: list[dict], columns: list[str], title: str = None):
    console = Console()
    table = __create_transactions_table(title=title)
    if 'suggested_category' in columns:
        table.add_column('Suggested', no_wrap=True)
    for row_dict in row_dicts:
        values = __dict_to_ordered_values(row_dict, columns)
        table.add_row(*values)

    console.print(table)


def output_rows_as_csv(row_dicts: list[dict], columns: list[str], output_path: Path):
    to_stdout = not output_path or output_path == '-'
    output_file = sys.stdout if to_stdout else open(output_path, 'w')
    try:
        csv_writer = csv.DictWriter(output_file, fieldnames=columns)
        csv_writer.writeheader()
        for row_dict in row_dicts:
            csv_writer.writerow(row_dict)
    finally:
        if not to_stdout and output_file:
            output_file.close()


def edit_transactions(
    data_path: Path,
    config_path: Path,
    from_path: Path | Literal['-'],
    transaction_id: str = None,
    new_date: str = None,
    new_description: str = None,
    new_amount: float = None,
    new_account: str = None,
    new_category: str = None,
    dry_run=False,
):
    transactions_csv = csv_tools.TransactionsCSV(data_path)
    column_names = {c: c for c in DATA_FILE_COLUMNS}
    updated = []
    txn_update_dicts = []

    if from_path:
        txn_update_dicts = csv_tools.read_dicts_from_csv(
            from_path, column_names_mapping=column_names
        )
    elif transaction_id is not None:
        updates_dict = {
            'id': transaction_id,
            'date': new_date,
            'description': new_description,
            'amount': new_amount,
            'account': new_account,
            'category': new_category,
        }
        updates_dict = {k: v for k, v in updates_dict.items() if v is not None}
        txn_update_dicts = [updates_dict]
    else:
        raise ValueError('No transactions specified to edit')
    for txn_updates_dict in txn_update_dicts:
        txn_id_to_update = txn_updates_dict.get('id', None)
        if txn_id_to_update is None:
            raise ValueError(
                f'Column named "id" must be present for updated to take place'
            )

        orig_transaction = transactions_csv.read_one(txn_id_to_update)
        updated_transaction = Transaction.from_str_dict(
            orig_transaction.to_str_dict() | txn_updates_dict
        )
        if not dry_run:
            transactions_csv.update(updated_transaction)
        updated.append(updated_transaction)

    txn_dicts = [t.to_str_dict() for t in updated]
    output_rows_to_table(txn_dicts, DATA_FILE_COLUMNS, title='Updated Transactions')


def handle_edit_transaction(args):
    # print(f'Editing transaction in {args.transactions}: {args.transaction_id}')
    if args.transaction_id is None and args.from_path is None:
        raise ValueError(
            'A transaction_id or --from argument must be applied. See --help for details.'
        )
    edit_transactions(
        args.data,
        args.config,
        args.from_path,
        args.transaction_id,
        new_date=args.date,
        new_amount=args.amount,
        new_account=args.account,
        new_category=args.category,
        dry_run=args.dry_run,
    )


def handle_delete_transaction(args):
    print(f'Deleting transaction in {args.transactions}: {args.transaction_id}')


def find_importer(p: Path, importers: list):
    """Find an importer for the given csv path"""
    matching_importer = None
    for importer in importers:
        if not importer.get('matcher'):
            print(f'Importer named "{importer["name"]}" has no matcher criteria')
            continue
        passed_matcher = True
        for criteria, value in importer.get('matcher', {}).items():
            if criteria == 'filenameContains':
                if value not in p.name:
                    passed_matcher = False
                    break
            elif criteria == 'headers':
                # TODO handle custom delimiter
                with open(p) as f:
                    header_line = f.readline()
                for col in value:
                    if col not in header_line:
                        passed_matcher = False
                        break
            else:
                raise ValueError(f'Unrecognized matcher criteria: {criteria}')
        if passed_matcher:
            matching_importer = importer
            break
    return matching_importer


def handle_import_transactions(args):
    import_transactions(
        args.data, args.config, args.csv_paths, importer_name=args.importer
    )


def validate_transaction(txn: Transaction):
    if (
        txn.date is None
        or not txn.description
        or txn.amount is None
        or txn.account is None
    ):
        raise ValueError(
            'Transaction must have a valid date, description, amount, and account value. Invalid transaction: {txn}'
        )


def import_transactions(
    data_path: Path,
    config_path: Path,
    csv_paths: list[Path],
    importer_name: str = None,
    dry_run=False,
):
    transactions_csv = csv_tools.TransactionsCSV(data_path)
    config = load_config(config_path)
    importers = config.get('importers')
    named_importer = None
    if importer_name:
        named_importer = next(
            (x for x in importers if x['name'] == importer_name), None
        )
        if not named_importer:
            raise ValueError(f'Failed to find importer by name "{importer_name}"')
    added_transactions = []
    for p in csv_paths:
        # find matching importer or use named one
        matching_importer = (
            named_importer if named_importer else find_importer(p, importers)
        )
        if matching_importer:
            print(f'Using "{matching_importer["name"]}" importer')
        else:
            raise ValueError(
                'Failed to find a matching importer. Please check your importers conditions and try again.'
            )

        # get column name mapping for importer
        column_names = {
            'date': matching_importer.get('dateColumn', 'Transaction Date'),
            'description': matching_importer.get('descriptionColumn', 'Description'),
            'amount': matching_importer.get('amountColumn', 'Amount'),
            'account': matching_importer.get('accountColumn', 'Account'),
            'category': matching_importer.get('categoryColumn', None),
        }
        # get default value mapping for importer
        default_values = {
            'date': matching_importer.get('dateValue'),
            'description': matching_importer.get('descriptionValue'),
            'amount': matching_importer.get('amountValue'),
            'account': matching_importer.get('accountValue'),
            'category': matching_importer.get('categoryValue'),
        }
        transactions_in_file = []
        for txn_dict in csv_tools.read_dicts_from_csv(
            p, column_names_mapping=column_names, default_values=default_values
        ):
            transaction = Transaction.from_str_dict(txn_dict)
            validate_transaction(transaction)
            # flip sign for something like a credit card
            # where transactions "add" to the credit
            if matching_importer.get('flipSign'):
                transaction.amount = -1 * transaction.amount

            transactions_in_file.append(transaction)
        if not dry_run:
            added_transactions.extend(transactions_csv.add(*transactions_in_file))
        else:
            added_transactions.extend(transactions_in_file)

        print(f'Finished importing {p}')

    columns = ['id', *TRANSACTION_FIELDS]
    new_txn_dicts = [t.to_str_dict() for t in added_transactions]
    output_rows_to_table(new_txn_dicts, columns)
    if not dry_run:
        print(f'Imported {len(added_transactions)} new transactions')
    else:
        print(f'Would have imported {len(added_transactions)} new transactions')


def handle_new_transaction(args):
    print(f'Adding a new transaction to {args.transactions}')


def handle_generate_report(args):
    print(
        f'Generating {args.type} report for {args.period} using transactions from {args.transactions}'
    )


def existing_file(p):
    p = Path(p)
    if p.is_file():
        return p
    raise argparse.ArgumentTypeError(f'{p} must be an existing file path')


def existing_json_file(p):
    p = existing_file(p)
    return json.loads(p.read_text())


def load_config(p):
    default_config = {
        'categories': [],
        'importers': [],
    }
    actual = existing_json_file(p)
    return {**default_config, **actual}


def parse_args(system_args):
    def add_common_arguments(parser):
        parser.add_argument(
            '--data',
            type=Path,
            default=Path.cwd() / DATA_FILE_NAME,
            help='Path to the transactions CSV',
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
    #     list_parser = subparsers.add_parser('list', help='list data')
    #     list_sub = list_parser.add_subparsers(dest='list_target', required=True)
    #
    #     list_transactions_parser = list_sub.add_parser(
    #         'transactions', aliases=['t', 'ts', 'txn', 'txns'], help='list transactions'
    #     )
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
