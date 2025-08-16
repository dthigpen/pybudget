import argparse
import csv
import copy
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
    delete_transactions,
)
import difflib
from tabulate import tabulate
from tinydb import TinyDB, Query


TXNS_FILE_NAME = 'pybudget_txns.csv'
CONFIG_FILE_NAME = 'pybudget_config.json'
TXNS_FILE_FIELDS = [
    'id',
    'date',
    'description',
    'amount',
    'account',
    'category',
    'notes',
]
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
    # TODO remove when adding category suggestions back
    args.suggest_categories = False
    txns = list(
        list_transactions(
            args.dir / TXNS_FILE_NAME,
            args.dir / CONFIG_FILE_NAME,
            filters=args.filters,
            suggest_categories=args.suggest_categories,
            ids=args.ids,
        )
    )
    # TODO figure out why there is no date for some
    txns.sort(key=lambda t: t.date if t.date else str_to_datetime('0001-01-01'))
    output_format = args.output_format
    output_path = args.output_file
    output_format = __determine_output_format(output_format, output_path)
    column_excludes = ['suggested_category'] if not args.suggest_categories else []
    if output_format == OutputFormat.TABLE:
        output_transactions_to_table(txns, exclude_columns=column_excludes)
    elif output_format == OutputFormat.CSV:
        output_transactions_to_csv(txns, output_path, exclude_columns=column_excludes)
    else:
        raise ValueError(f'Unrecognized output format: {output_format.value}')


def output_transactions_to_table(
    transactions: list[Transaction], exclude_columns=None, title: str = None
):
    # Display fields with these names differently
    exclude_columns = exclude_columns or set()
    all_columns_ordered = [
        'id',
        'date',
        'description',
        'amount',
        'account',
        'category',
        'suggested_category',
    ]
    columns = [c for c in all_columns_ordered if c not in exclude_columns]
    alias_mapping = {'id': 'ID', 'suggested_category': 'Suggested'}
    headers = list(map(lambda c: alias_mapping.get(c, c.title()), columns))
    rows = []
    for txn in transactions:
        values = __dict_to_ordered_values(txn.to_csv_dict(), columns)
        rows.append(values)

    print(tabulate(rows, headers=headers, tablefmt='github'))


def output_transactions_to_csv(
    transactions: list[Transaction], output_path: Path, exclude_columns=None
):
    exclude_columns = exclude_columns or set()
    all_columns_ordered = [
        'id',
        'date',
        'description',
        'amount',
        'account',
        'category',
        'suggested_category',
    ]
    columns = [c for c in all_columns_ordered if c not in exclude_columns]
    to_stdout = not output_path or output_path == '-'
    output_file = sys.stdout if to_stdout else open(output_path, 'w')
    try:
        csv_writer = csv.DictWriter(output_file, fieldnames=columns)
        csv_writer.writeheader()
        for txn in transactions:
            row_dict = txn.to_csv_dict()
            row_dict = {k: row_dict.get(k, '') for k in columns}
            csv_writer.writerow(row_dict)
    finally:
        if not to_stdout and output_file:
            output_file.close()


def handle_edit_transaction(args):
    if not args.filters and not args.ids and args.from_path is None:
        raise ValueError(
            'An --id argument, --filter argument, or --from argument must be applied. See --help for details.'
        )

    with safe_file_update_context(
        args.dir / TXNS_FILE_NAME, dry_run=args.dry_run
    ) as tmp_txns_path:
        updated_txns = edit_transactions(
            tmp_txns_path,
           args.dir / CONFIG_FILE_NAME,
            args.from_path,
            ids=args.ids,
            filters=args.filters,
            new_date=args.date,
            new_amount=args.amount,
            new_account=args.account,
            new_category=args.category,
        )
        output_transactions_to_table(
            updated_txns, exclude_columns=['suggested_category']
        )


def handle_import_transactions(args):
    txns_path = args.dir / TXNS_FILE_NAME
    with safe_file_update_context(txns_path, dry_run=args.dry_run) as tmp_txns_path:
        new_txns = list(
            import_transactions(
                tmp_txns_path,
                args.dir / CONFIG_FILE_NAME,
                args.csv_paths,
                importer_name=args.importer,
            )
        )
        output_transactions_to_table(new_txns, exclude_columns=['suggested_category'])
        print(f'Imported {len(new_txns)} new transactions')


def handle_init(args):
    budget_dir = args.budget_data_dir

    # create the budget data dir
    if budget_dir.exists():
        print(f'Budget directory already exists at {budget_dir}')
    elif budget_dir != Path.cwd():
        budget_dir.mkdir(parents=True)
        print(f'Created budget directory at {budget_dir}')

    # create the config file pybudget.json
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
    config_path = budget_dir / CONFIG_FILE_NAME
    if config_path.is_file():
        print(f'Config file already exists at {config_path}')
    else:
        config_path.write_text(json.dumps(starter_config, indent=4))
        print(f'Created starter config at {config_path}')

    txns_file = budget_dir / TXNS_FILE_NAME
    if not txns_file.exists():
        txns_csv = csv_tools.TransactionsCSV(txns_file)
        txns_csv.initialize()


def handle_delete_transaction(args):
    if not args.filters and not args.ids:
        raise ValueError(
            'An --id argument, --filter argument, or --from argument must be applied. See --help for details.'
        )
    with safe_file_update_context(
        args.dir / TXNS_FILE_NAME, dry_run=args.dry_run
    ) as tmp_txns_path:
        txns_to_delete = []
        if args.ids:
            txns_to_delete.extend(
                list_transactions(tmp_txns_path, args.dir / CONFIG_FILE_NAME, ids=args.ids)
            )
        if args.filters:
            txns_to_delete.extend(
                list_transactions(
                    tmp_txns_path,
                    args.dir / CONFIG_FILE_NAME,
                    filters=args.filters,
                )
            )
        ids = list(map(lambda t: t.id, txns_to_delete))
        if not ids:
            raise ValueError('No transactions matching query')
        delete_transactions(tmp_txns_path, args.dir / CONFIG_FILE_NAME, ids=ids)
        output_transactions_to_table(
            txns_to_delete, exclude_columns=['suggested_category']
        )


def handle_new_budget(args):
    # TODO handle interactive
    empty_budget_template = {
        'month': 'YYYY-MM',  # TODO set to current year-month
        'income': [],
        'expenses': [],
        'funds': [],
    }
    sample_budget = copy.deepcopy(empty_budget_template)
    sample_budget['income'] = [
        {
            'name': 'Income',
            'budgeted': 3.50,
            'notes': 'Update to your own estimated monthly income',
        }
    ]
    sample_budget['expenses'] = [
        {'name': 'Rent', 'budgeted': 1250},
        {'name': 'Groceries', 'budgeted': 150.0},
        {'name': 'Internet', 'budgeted': 50.0},
    ]
    sample_budget['funds'] = [
        {'name': 'Travel', 'balance': 0, 'goal': 5000},
        {'name': 'Medical Emergency', 'balance': 0, 'goal': 10000},
    ]

    default_report_example = {
        'income': [],
        'expenses': [],
        'funds': [],
    }
    source_budget = None
    if args.from_file:
        source_budget = json.loads(args.from_file.read_text())
        if 'report' not in source_budget:
            print(
                f'Budget being copied from does not have a report element, meaning balances may not be up to date! Run a report to remove this warning. Budget: {args.from_file}'
            )
    elif args.sample:
        # TODO make from and sample mutually exclusive
        source_budget = copy.deepcopy(sample_budget)
    else:
        source_budget = empty_budget_template

    new_budget = empty_budget_template
    new_budget['month'] = args.month

    # copy over income/expenses/funds
    for cat_type in ('income', 'expenses', 'funds'):
        new_budget[cat_type] = copy.deepcopy(source_budget[cat_type])

    # update balances to be those found in the source budget report
    report = source_budget.get('report', {})
    if report:
        new_budget_funds = new_budget['funds']
        for report_fund in report.get('funds', []):
            new_balance = report_fund['balance']
            new_fund = next(
                filter(lambda f: f['name'] == report_fund['name'], new_budget_funds),
                None,
            )
            if new_fund:
                new_fund['balance'] = new_balance
    else:
        print(f'No report to use updated balances from')

    new_budget_path = args.dir / (f'{args.month}-budget.json')
    new_budget_path.write_text(json.dumps(new_budget, indent=4))


def parse_args(system_args):
    def add_common_arguments(parser):
        parser.add_argument(
            '--dir',
            type=Path,
            default=Path.cwd(),
            help='Path to the directory to look for transactions and budget files',
        )
        parser.add_argument(
            '--config',
            type=Path,
            default=Path.cwd() / CONFIG_FILE_NAME,
            help='Path to the config file',
        )

    def add_filtering(parser):
        parser.add_argument(
            '--filter',
            dest='filters',
            action='append',
            help='Add a filter expression like "field~value", "amount>100", etc. Can be used multiple times.',
        )
        parser.add_argument(
            '--id',
            dest='ids',
            type=int,
            nargs='*',
            help='The IDs of specific transactions to use in the query',
        )

    parser = argparse.ArgumentParser(description='pybudget CLI')
    parser.set_defaults(func=lambda args: parser.print_help())
    add_common_arguments(parser)
    subparsers = parser.add_subparsers(dest='command')

    # Init parser
    init_parser = subparsers.add_parser(
        'init', help='Initialize a workspace for your budgets'
    )
    init_parser.add_argument(
        'budget_data_dir',
        type=Path,
        help='The name of a new directory to keep all of your budget data',
    )
    init_parser.set_defaults(func=handle_init)

    # New parser
    new_parser = subparsers.add_parser('new', help='New resource')
    new_sub = new_parser.add_subparsers(dest='new_target', required=True)

    new_budget_parser = new_sub.add_parser(
        'budget', aliases=['b', 'bud', 'bdgt', 'bgt'], help='New monthly budget file'
    )

    new_budget_parser.add_argument(
        'month',
        type=str,
        help='Month of this budget. Typically the upcoming month. E.g. 2025-05',
    )
    new_budget_parser.add_argument(
        '--from',
        dest='from_file',
        type=Path,
        help='Budget file to copy from. Typically the current/previous month',
    )
    new_budget_parser.add_argument(
        '--sample',
        action='store_true',
        help='Populate with example income, expenses, and funds',
    )

    # Report parser
    report_parser = subparsers.add_parser('report', help='Generate a report for an existing budget')
    
    # report_sub = report_parser.add_subparsers(dest='report_target', required=True)

    # report_budget_parser = report_sub.add_parser(
    #     'budget', aliases=['b', 'bud', 'bdgt', 'bgt'], help='report monthly budget file'
    # )
# 
    report_parser.add_argument(
        'month',
        type=str,
        help='Month of the budget to generate a report on. E.g. 2025-05',
    )
#     report_budget_parser.set_defaults(func=handle_report_budget)
    report_parser.set_defaults(func=lambda args: print(args))
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
    add_filtering(list_transactions_parser)
    list_transactions_parser.add_argument(
        '--uncategorized',
        action='store_true',
        help='A filter to only show uncategorized transactions',
    )
    # list_transactions_parser.add_argument(
    #     '-s',
    #     '--suggest-categories',
    #     action='store_true',
    #     help='Add a column for suggested categories for the uncategorized',
    # )
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

    # Delete command
    delete_parser = subparsers.add_parser('delete', help='Delete a transaction')
    delete_sub = delete_parser.add_subparsers(dest='delete_target', required=True)
    delete_txns_parser = delete_sub.add_parser(
        'transactions', aliases=['t', 'ts', 'txn', 'txns'], help='delete transactions'
    )
    add_common_arguments(delete_txns_parser)
    add_filtering(delete_txns_parser)
    delete_txns_parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Run through the operation without actually persisting any changes',
    )
    delete_txns_parser.set_defaults(func=handle_delete_transaction)

    # Edit command
    edit_parser = subparsers.add_parser('edit', help='Edit a transaction')
    edit_sub = edit_parser.add_subparsers(dest='edit_target', required=True)
    edit_txns_parser = edit_sub.add_parser(
        'transactions', aliases=['t', 'ts', 'txn', 'txns'], help='list transactions'
    )
    add_common_arguments(edit_txns_parser)
    # edit_source = edit_txns_parser.add_mutually_exclusive_group(required=True)
    add_filtering(edit_txns_parser)
    edit_txns_parser.add_argument(
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
