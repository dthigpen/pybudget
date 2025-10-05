#!/usr/bin/env python3
"""
report.py - Generate budget reports from transactions and a JSON budget file.

Usage:
    report.py --budget budgets/2025-05.json --transactions final-transactions/*.csv
    report.py --budget budgets/2025-05.json --transactions txns.csv -f csv > reports/2025-05.csv
"""

import argparse
import csv
import json
import sys
import signal
from pathlib import Path
from typing import Dict, List, Any, Optional, TextIO, Sequence
from collections import defaultdict, namedtuple
import itertools
import io

from pybudget import util

# for txt formatted report
try:
    from tabulate import tabulate
except:
    pass

# pipe-safe
signal.signal(signal.SIGPIPE, signal.SIG_DFL)

Transaction = Dict[str, str]
BudgetEntry = Dict[str, Any]


def read_csv_or_json(path: Path) -> list[dict]:
    def read_csv(p):
        with open(p, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            return list(reader)

    def read_json(p):
        with open(path, encoding='utf-8') as f:
            return json.load(f)

    if path.name.endswith('.json'):
        return read_json(path)
    elif path.name.endswith('.csv'):
        return read_csv(path)
    else:
        # try to read anyway
        try:
            return read_json(path)
        except:
            return read_csv(path)


def read_budget(path: Path) -> List[BudgetEntry]:
    """Read budget entries from JSON or CSV file."""
    return read_csv_or_json(path)


def read_transactions(paths: List[str], period=None) -> List[Transaction]:
    """Read all transactions from CSV files."""
    rows: List[Transaction] = []
    # TODO update to yield txns with generator
    for p in paths:
        with open(p, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            subset = []
            if period:
                for r in reader:
                    if r.get('date', '').startswith(period):
                        subset.append(r)
            else:
                subset = reader
            rows.extend(subset)
    return rows


def aggregate(
    transactions: List[Dict[str, Any]], budget: List[Dict[str, Any]], period: str
) -> Dict[str, Any]:
    """
    Aggregate transactions into structured report data.
    """
    # Build budget lookup
    budget_map = {
        row['name']: row for row in budget if row['type'] in {'income', 'expense'}
    }
    fund_map = {row['name']: row for row in budget if row['type'] == 'fund'}

    # Group transactions by category
    txn_by_category: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for txn in transactions:
        category = txn.get('category', '').strip()
        txn_by_category[category].append(txn)

    # Initialize report
    report: Dict[str, Any] = {
        'period': period,
        'income': {'categories': [], 'total': 0.0},
        'expenses': {'categories': [], 'total': 0.0},
        'funds': [],
        'uncategorized': {'categories': [], 'total': 0.0},
        'unbudgeted': {'categories': [], 'total': 0.0},
        'hidden': {'count': 0},
    }

    def fmt_float(value):
        return round(float(value), 2)

    for category, txns in txn_by_category.items():
        actual = sum(float(t.get('amount', 0) or 0) for t in txns)
        actual = fmt_float(actual)

        if not category:  # Uncategorized
            row = {
                'name': 'Uncategorized',
                'transactions': txns,
                'budget': 0.0,
                'actual': actual,
                'variance': actual,
                'notes': '',
            }
            report['uncategorized']['categories'].append(row)
            report['uncategorized']['total'] += actual

        elif category in fund_map:  # Treat transactions toward a fund
            f_row = fund_map[category]
            start_balance = fmt_float(f_row.get('balance') or 0)
            goal = fmt_float(f_row.get('goal') or 0)
            reconcile = fmt_float(f_row.get('reconcile_amount') or 0)
            end_balance = start_balance + actual + reconcile

            report['funds'].append(
                {
                    'name': category,
                    'transactions': txns,
                    'start_balance': start_balance,
                    'actual': actual,
                    'end_balance': end_balance,
                    'goal': goal,
                    'reconcile_amount': reconcile,
                    'notes': f_row.get('notes', ''),
                }
            )

        elif category in budget_map:  # Regular income/expense
            b_row = budget_map[category]
            budget_val = fmt_float(float(b_row.get('budget') or 0))
            section = 'income' if b_row['type'] == 'income' else 'expenses'
            row = {
                'name': category,
                'transactions': txns,
                'budget': budget_val,
                'actual': actual,
                'variance': actual - budget_val,
                'notes': b_row.get('notes', ''),
            }
            report[section]['categories'].append(row)
            report[section]['total'] += actual

        else:  # Not in budget or fund list
            row = {
                'name': f'Unbudgeted:{category}',
                'transactions': txns,
                'budget': 0.0,
                'actual': actual,
                'variance': actual,
                'notes': '',
            }
            report['unbudgeted']['categories'].append(row)
            report['unbudgeted']['total'] += actual

    # Add any funds with no transactions yet
    for name, f_row in fund_map.items():
        if not any(f['name'] == name for f in report['funds']):
            start_balance = fmt_float(f_row.get('balance') or 0)
            goal = fmt_float(f_row.get('goal') or 0)
            reconcile = fmt_float(f_row.get('reconcile_amount') or 0)
            report['funds'].append(
                {
                    'name': name,
                    'transactions': [],
                    'start_balance': start_balance,
                    'actual': 0.0,
                    'end_balance': start_balance + reconcile,
                    'goal': goal,
                    'reconcile_amount': reconcile,
                    'notes': f_row.get('notes', ''),
                }
            )

    return report


def compute_summary(report: dict) -> dict:
    """
    Compute summary totals from the structured report.
    Returns a dict with Income, Expenses, Cash flow, Uncategorized, Unbudgeted.
    """
    income = report['income']['total']
    expenses = report['expenses']['total']
    uncategorized = report['uncategorized']['total']
    unbudgeted = report['unbudgeted']['total']

    return {
        'Income': income,
        'Expenses': expenses,
        'Cash flow': income - expenses,
        'Uncategorized': uncategorized,
        'Unbudgeted': unbudgeted,
    }


def write_txt_report(report: dict, out: TextIO) -> None:
    period = report['period']
    out.write(f'\nBudget Report for {period}\n')
    out.write('=' * (len(period) + 17) + '\n\n')

    # --- Summary ---
    summary = compute_summary(report)
    rows = [[k, v] for k, v in summary.items()]
    out.write('Summary:\n')
    out.write(tabulate(rows, headers=['Item', 'Amount'], floatfmt='.2f'))
    out.write('\n\n')

    # --- Sections ---
    for section in ['income', 'expenses', 'uncategorized', 'unbudgeted']:
        rows = [
            [row['name'], row['budget'], row['actual'], row['variance'], row['notes']]
            for row in report[section]['categories']
        ]
        out.write(f'{section.capitalize()}:\n')
        if rows:
            out.write(
                tabulate(
                    rows,
                    headers=['Name', 'Budget', 'Actual', 'Variance', 'Notes'],
                    floatfmt='.2f',
                )
            )
        else:
            out.write('(none)')
        out.write('\n\n')

    # --- Funds ---
    fund_rows = [
        [
            row['name'],
            row['start_balance'],
            row['actual'],
            row['end_balance'],
            row['goal'],
            row['reconcile_amount'],
            row['notes'],
        ]
        for row in report['funds']
    ]
    out.write('Funds:\n')
    if fund_rows:
        out.write(
            tabulate(
                fund_rows,
                headers=[
                    'Name',
                    'Start',
                    'Actual',
                    'End',
                    'Goal',
                    'Reconcile',
                    'Notes',
                ],
                floatfmt='.2f',
            )
        )
    else:
        out.write('(none)')
    out.write('\n')


def write_csv_report(report: dict, out: TextIO) -> None:
    writer = csv.writer(out)
    writer.writerow(
        [
            'period',
            'section',
            'name',
            'budget',
            'actual',
            'variance',
            'start_balance',
            'end_balance',
            'goal',
            'reconcile_amount',
            'notes',
        ]
    )

    period = report['period']

    # --- Summary ---
    summary = compute_summary(report)
    for key, value in summary.items():
        writer.writerow([period, 'summary', key, '', value, '', '', '', '', '', ''])

    # --- Sections ---
    for section in ['income', 'expenses', 'uncategorized', 'unbudgeted']:
        for row in report[section]['categories']:
            writer.writerow(
                [
                    period,
                    section,
                    row['name'],
                    row.get('budget', ''),
                    row.get('actual', ''),
                    row.get('variance', ''),
                    '',
                    '',
                    '',
                    '',
                    row.get('notes', ''),
                ]
            )

    # --- Funds ---
    for row in report['funds']:
        writer.writerow(
            [
                period,
                'funds',
                row['name'],
                '',
                row['actual'],
                '',
                row['start_balance'],
                row['end_balance'],
                row['goal'],
                row['reconcile_amount'],
                row['notes'],
            ]
        )


import json
from typing import TextIO


def write_json_report(report: dict, out: TextIO) -> None:
    """
    Write the report to JSON, including the computed summary.
    """
    import copy

    enriched_report = copy.deepcopy(report)
    enriched_report['summary'] = compute_summary(report)
    # remove txns
    for section in enriched_report.values():
        if not isinstance(section, dict):
            continue
        for category in section.get('categories', []):
            category.pop('transactions', None)
    json.dump(enriched_report, out, indent=2)


def init_budget(
    period: str, output: str, fmt: str = 'json', from_report: Optional[str] = None
) -> None:
    """Initialize a new budget file for given period.

    Args:
        period: Target period in YYYY-MM format.
        output: Output path or "-" for stdout.
        fmt: "json" (default) or "csv".
        from_report: Optional prior report file to clone (json or csv).
    """
    budget_rows = []

    if from_report:
        report_path = Path(from_report)

        if report_path.suffix == '.json':
            report = json.loads(report_path.read_text(encoding='utf-8'))
            categories = report.get('categories', [])
            funds = report.get('funds', [])

        elif report_path.suffix == '.csv':
            with open(report_path, newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                categories, funds = [], []
                for row in reader:
                    section = row.get('section', '').strip().lower()
                    if section == 'category':
                        categories.append(row)
                    elif section == 'fund':
                        funds.append(row)
        else:
            raise ValueError(f'Unsupported report format: {report_path.suffix}')

        # Build budget rows from prior report
        for c in categories:
            budget_rows.append(
                {
                    'period': period,
                    'type': c.get('type', 'expense'),
                    'name': c['name'],
                    'budget': c.get('budget', 0),
                    'balance': '',
                    'goal': '',
                    'reconcile_amount': '',
                    'override_actual': '',
                    'notes': '',
                }
            )
        for f in funds:
            budget_rows.append(
                {
                    'period': period,
                    'type': 'fund',
                    'name': f['name'],
                    'budget': 0,
                    'balance': f.get('end_balance_calc', f.get('end_balance', 0)),
                    'goal': f.get('goal', ''),
                    'reconcile_amount': '',
                    'override_actual': '',
                    'notes': '',
                }
            )

    else:
        # Dummy starter template
        budget_rows = [
            {
                'period': period,
                'type': 'income',
                'name': 'Salary',
                'budget': 3000,
                'balance': '',
                'goal': '',
                'reconcile_amount': '',
                'override_actual': '',
                'notes': '',
            },
            {
                'period': period,
                'type': 'expense',
                'name': 'Rent',
                'budget': 1200,
                'balance': '',
                'goal': '',
                'reconcile_amount': '',
                'override_actual': '',
                'notes': '',
            },
            {
                'period': period,
                'type': 'expense',
                'name': 'Food',
                'budget': 400,
                'balance': '',
                'goal': '',
                'reconcile_amount': '',
                'override_actual': '',
                'notes': '',
            },
            {
                'period': period,
                'type': 'fund',
                'name': 'Emergency Fund',
                'budget': 100,
                'balance': 1500,
                'goal': 2000,
                'reconcile_amount': '',
                'override_actual': '',
                'notes': '',
            },
        ]

    # Write output
    if fmt == 'json':
        out = json.dumps(budget_rows, indent=2)
    elif fmt == 'csv':
        fieldnames = [
            'period',
            'type',
            'name',
            'budget',
            'balance',
            'goal',
            'reconcile_amount',
            'override_actual',
            'notes',
        ]
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(budget_rows)
        out = buf.getvalue()
    else:
        raise ValueError(f'Unsupported format {fmt}')

    if output == '-' or not output:
        sys.stdout.write(out)
        sys.stdout.flush()
    else:
        Path(output).write_text(out, encoding='utf-8')


def setup_parser(parser: argparse.ArgumentParser) -> None:
    """Add report-specific arguments to a parser."""
    # --- report subcommand (existing) ---
    # report_parser = subparsers.add_parser('report', help='Generate budget report')
    parser.add_argument(
        '--budget',
        required=True,
        type=util.existing_file,
        help='Budget JSON or CSV file',
    )
    parser.add_argument(
        '--transactions', required=True, nargs='+', help='Transaction CSV file(s)'
    )
    parser.add_argument(
        '--format',
        choices=['txt', 'csv', 'json'],
        default='txt',
        help='Output format (default: txt)',
    )
    parser.add_argument('--output', default='-', help='Output path (default: stdout)')
    #
    #     # --- init subcommand (new) ---
    #     init_parser = subparsers.add_parser('init', help='Initialize a budget file')
    #     init_parser.add_argument(
    #         '--period', required=True, help='Period to initialize (YYYY-MM)'
    #     )
    #     init_parser.add_argument(
    #         '--from-report',
    #         type=existing_file,
    #         help='Optional prior report (CSV or JSON) to base new budget on',
    #     )
    #     init_parser.add_argument(
    #         '--format',
    #         choices=['json', 'csv'],
    #         default='json',
    #         help='Output format (default: json)',
    #     )
    #     init_parser.add_argument(
    #         '--output', default='-', help='Output file (default: stdout)'
    #     )
    parser.set_defaults(func=run)


def run(args: argparse.Namespace) -> None:
    budget = read_budget(args.budget)
    # should handle period more intelligently, like generating reports for all periods in the budget
    # for now just allow one
    all_periods = set(r['period'] for r in budget)
    if len(all_periods) > 1:
        util.eprint(
            f'Budget must contain only one period (for now). Periods: {all_periods}'
        )
        exit(1)
    period = list(all_periods)[0]

    transactions = read_transactions(args.transactions, period=period)

    aggregated = aggregate(transactions, budget, period)

    if args.format == 'txt':
        write_txt_report(
            aggregated, sys.stdout if args.output == '-' else open(args.output, 'w')
        )
    elif args.format == 'csv':
        write_csv_report(
            aggregated,
            sys.stdout if args.output == '-' else open(args.output, 'w', newline=''),
        )
    elif args.format == 'json':
        out = sys.stdout if args.output == '-' else open(args.output, 'w')
        write_json_report(aggregated, out)
    else:
        raise ValueError(f'Unsupported format: {args.format}')

    # elif args.command == 'init':
    #     init_budget(args.period, args.output, fmt=args.format, from_report=args.from_report)


def main(argv: Optional[Sequence[str]] = None) -> None:
    if argv is None:
        argv = sys.argv[1:]
    parser = argparse.ArgumentParser(
        description='Budget reporting and initialization tool'
    )
    setup_parser(parser)
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == '__main__':
    main()
