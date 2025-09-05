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
from typing import Dict, List, Any
from collections import defaultdict, namedtuple

# pipe-safe
signal.signal(signal.SIGPIPE, signal.SIG_DFL)

Transaction = Dict[str, str]
BudgetEntry = Dict[str, Any]


def existing_file(p: str) -> Path:
    p = Path(p)
    if not p.is_file():
        raise argparse.ArgumentTypeError(f'Path {p} must be an existing file')
    return p


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Generate budget reports.')
    parser.add_argument(
        '--budget', type=existing_file, required=True, help='Budget JSON or CSV file.'
    )
    parser.add_argument(
        '--transactions',
        type=existing_file,
        nargs='+',
        required=True,
        help='Transaction CSV files.',
    )
    parser.add_argument(
        '-f',
        '--format',
        choices=['csv', 'txt'],
        default='txt',
        help='Output format (default: txt).',
    )
    parser.add_argument(
        '-o', '--output', default='-', help='Output file (default: stdout).'
    )
    return parser.parse_args()


def read_budget(path: Path) -> List[BudgetEntry]:
    """Read budget entries from JSON or CSV file."""
    if path.name.endswith('.json'):
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    elif path.name.endswith('.csv'):
        with open(p, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            return list(reader)


def read_transactions(paths: List[str]) -> List[Transaction]:
    """Read all transactions from CSV files."""
    rows: List[Transaction] = []
    for p in paths:
        with open(p, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows.extend(reader)
    return rows


def aggregate(
    budget: List[BudgetEntry], transactions: List[Transaction]
) -> List[Dict[str, Any]]:
    """Compute actuals and variances per budget entry and produce summary rows."""
    # Build totals per category
    totals = defaultdict(float)
    for row in transactions:
        cat = row.get('category', '').strip()
        amt = float(row.get('amount', 0) or 0)
        totals[cat] += amt

    report_rows: List[Dict[str, Any]] = []
    summary = {'Income': 0.0, 'Expenses': 0.0}

    for entry in budget:
        typ = entry['type']
        name = entry['name']
        budget_amt = float(entry.get('budget', 0) or 0)
        actual = float(entry.get('override_actual', '') or totals.get(name, 0.0))
        variance = actual - budget_amt

        row = {
            'section': 'category' if typ in ('income', 'expense') else 'fund',
            'period': entry.get('period', ''),
            'type': typ,
            'name': name,
            'budget': budget_amt if typ in ('income', 'expense') else '',
            'actual': actual if typ in ('income', 'expense') else '',
            'variance': variance if typ in ('income', 'expense') else '',
            'start_balance': entry.get('balance', ''),
            'end_balance': '',
            'goal': entry.get('goal', ''),
            'reconcile_amount': entry.get('reconcile_amount', ''),
            'notes': entry.get('notes', ''),
        }

        if typ == 'income':
            summary['Income'] += actual
        elif typ == 'expense':
            summary['Expenses'] += actual

        report_rows.append(row)

    # Derived summary rows
    cash_flow = summary['Income'] - summary['Expenses']
    under_budget = sum(
        max(0, float(r['budget']) - float(r['actual']))
        for r in report_rows
        if r['section'] == 'category' and r['type'] == 'expense'
    )
    over_budget = sum(
        max(0, float(r['actual']) - float(r['budget']))
        for r in report_rows
        if r['section'] == 'category' and r['type'] == 'expense'
    )

    report_rows.extend(
        [
            {'section': 'summary', 'name': 'Income', 'actual': summary['Income']},
            {'section': 'summary', 'name': 'Expenses', 'actual': summary['Expenses']},
            {'section': 'summary', 'name': 'Cash flow', 'actual': cash_flow},
            {'section': 'summary', 'name': 'Under budget', 'actual': under_budget},
            {'section': 'summary', 'name': 'Over budget', 'actual': over_budget},
            {
                'section': 'summary',
                'name': 'Net variance',
                'actual': under_budget - over_budget,
            },
        ]
    )

    return report_rows


def write_csv(path: str, rows: List[Dict[str, Any]]) -> None:
    fieldnames = [
        'section',
        'period',
        'type',
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
    if path == '-':
        writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
        sys.stdout.flush()
        try:
            sys.stdout.close()
        except Exception:
            pass
    else:
        with open(path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)


def write_txt(path: str, rows: List[Dict[str, Any]]) -> None:
    def fmt_amt(val: Any) -> str:
        try:
            return f'{float(val):.2f}'
        except Exception:
            return str(val or '')

    lines = []
    lines.append('=== Budget Report ===')
    for r in rows:
        if r['section'] == 'summary':
            lines.append(f'{r["name"]}: {fmt_amt(r["actual"])}')
        elif r['section'] == 'category':
            lines.append(
                f'- {r["type"].title()} {r["name"]}: '
                f'Budget {fmt_amt(r["budget"])}, '
                f'Actual {fmt_amt(r["actual"])}, '
                f'Variance {fmt_amt(r["variance"])}'
            )
        elif r['section'] == 'fund':
            lines.append(
                f'- Fund {r["name"]}: Balance {r["start_balance"]} → {r["end_balance"]} '
                f'(Goal {r["goal"]}, Reconcile {r["reconcile_amount"]})'
            )

    out = '\n'.join(lines)
    if path == '-':
        sys.stdout.write(out + '\n')
        sys.stdout.flush()
    else:
        Path(path).write_text(out, encoding='utf-8')


def main() -> None:
    args = parse_args()
    budget = read_budget(args.budget)
    transactions = read_transactions(args.transactions)
    rows = aggregate(budget, transactions)

    if args.format == 'csv':
        write_csv(args.output, rows)
    else:
        write_txt(args.output, rows)


if __name__ == '__main__':
    main()
