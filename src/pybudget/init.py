#!/usr/bin/env python3
"""
pybudget init: Initialize budget-related files.
"""

import argparse
import sys
import json
import csv
import io
from pathlib import Path
from typing import Optional
from pybudget import util
# ----------------------
# Init: Budget
# ----------------------


def init_budget(
    period: str,
    output: Path,
    from_report: Optional[str] = None,
) -> None:
    """Initialize a new budget file for a given period."""
    budget_rows = []
    fmt = output.suffix[1:]
    if fmt not in ('json', 'csv'):
        exit(f'Output file type must be of type json or csv')
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
        # Starter template
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

    # Serialize output
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


# ----------------------
# Init: Importer
# ----------------------


def init_importer(output: Path) -> None:
    """Create a starter importer file."""
    template_ini = """[importer]
match_header=Date,Description,Amount
date_column=Date
description_column=Description
amount_column=Amount
account_value=Checking
"""
    template_json = {
        'importer': {
            'matchHeader': 'Date,Description,Amount',
            'dateColumn': 'Date',
            'descriptionColumn': 'Description',
            'amountColumn': 'Amount',
            'accountValue': 'Checking',
        }
    }
    fmt = output.suffix[1:]
    if fmt not in ('json', 'ini'):
        exit(f'Output file type must be of type json or ini')
    if fmt == 'ini':
        Path(output).write_text(template_ini, encoding='utf-8')
    elif fmt == 'json':
        Path(output).write_text(json.dumps(template_json, indent=2), encoding='utf-8')
    else:
        raise ValueError(f'Unsupported importer format {fmt}')


# ----------------------
# Init: Changeset
# ----------------------


def init_changeset(path: str) -> None:
    """Create a starter changeset file."""
    fmt = output.suffix[1:]
    if fmt not in ('json', 'csv'):
        exit(f'Output file type must be of type json or csv')
    if fmt == 'csv':
        fieldnames = ['type', 'id', 'amount', 'category', 'notes']
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow({'type': 'update', 'id': 'example123', 'category': 'Groceries'})
        Path(path).write_text(buf.getvalue(), encoding='utf-8')
    elif fmt == 'json':
        template = [
            {'type': 'update', 'id': 'example123', 'category': 'Groceries'},
            {'type': 'add', 'amount': '25.50', 'category': 'Snacks'},
        ]
        Path(path).write_text(json.dumps(template, indent=2), encoding='utf-8')
    else:
        raise ValueError(f'Unsupported changeset format {fmt}')


# ----------------------
# Parser setup
# ----------------------


def setup_parser(parser: argparse.ArgumentParser) -> None:
    sub = parser.add_subparsers(dest='init_command', required=True)

    # budget
    p_budget = sub.add_parser('budget', help='Initialize a budget file')
    p_budget.add_argument('--period', required=True, help='Target period YYYY-MM')
    p_budget.add_argument(
        '-o', '--output', required=True, type=Path, help='Output file (or - for stdout)'
    )
    p_budget.add_argument('--format', choices=['json', 'csv'], default='json')
    p_budget.add_argument(
        '--from-report', help='Optional prior report file (json or csv)'
    )
    p_budget.set_defaults(func=run)

    # importer
    p_importer = sub.add_parser('importer', help='Initialize an importer file')
    p_importer.add_argument(
        '-o', '--output', type=Path, required=True, help='Output path'
    )
    p_importer.add_argument('--format', choices=['ini', 'json'], default='ini')
    p_importer.set_defaults(func=run)

    # changeset
    p_changeset = sub.add_parser('changeset', help='Initialize a changeset file')
    p_changeset.add_argument(
        '-o', '--output', type=Path, required=True, help='Output path'
    )
    p_changeset.add_argument('--format', choices=['csv', 'json'], default='csv')
    p_changeset.set_defaults(func=run)


def run(args: argparse.Namespace) -> None:
    if args.init_command == 'budget':
        init_budget(args.period, args.output, args.from_report)
    elif args.init_command == 'importer':
        init_importer(args.output)
    elif args.init_command == 'changeset':
        init_changeset(args.output)
