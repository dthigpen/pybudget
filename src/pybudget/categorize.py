from __future__ import annotations
import argparse
import csv
import sys
from pathlib import Path
from typing import List, Dict, Any

from pybudget.util import (
    read_csv,
    write_csv,
    write_csv_or_json,
    write_csv_or_json,
    stable_id,
    DEFAULT_ORDERED_COLUMNS,
)  # assuming you already have these
from pybudget import util
from pybudget.suggestions import suggest_categories


def setup_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        'transactions',
        nargs='+',
        help='Input transaction CSV(s) to categorize',
    )
    parser.add_argument(
        '-c',
        '--categorized',
        nargs='*',
        default=[],
        help='Reference categorized CSVs for suggestions',
    )
    parser.add_argument(
        '-o',
        '--output',
        required=True,
        help='Output changeset file (.csv or .json)',
    )
    parser.add_argument(
        '-n',
        '--no-input',
        action='store_true',
        help="Run non-interactively (prepends suggested categories with 'suggested:' unless --auto-confirm is given)",
    )
    parser.add_argument(
        '--overwrite',
        action='store_true',
        help='Overwrite existing output file instead of appending',
    )
    parser.add_argument(
        '--auto-confirm',
        action='store_true',
        help="Automatically confirm suggested categories without prefixing 'suggested:'. Only appies when --no-input is used",
    )
    parser.set_defaults(func=run)


def write_update(update: dict, args, updates: List[dict]):
    """Persist update to CSV or JSON immediately."""
    out_path = Path(args.output)

    if out_path.suffix == '.csv':
        exists = out_path.exists() and not args.overwrite
        with open(out_path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['type', *DEFAULT_ORDERED_COLUMNS])
            if not exists:
                writer.writeheader()
            writer.writerow(update)

    elif out_path.suffix == '.json':
        updates.append(update)
        out_path.write_text(json.dumps(updates, indent=2), encoding='utf-8')

    else:
        sys.exit('ERROR: output file must end with .csv or .json')


def process_edit_interactive(args, txns: List[dict], reference: List[dict]):
    """
    Interactive editor for reviewing and modifying transactions.
    Supports categorization, edits, splits, adds, and deletes.
    """
    updates: List[dict] = []
    known = reference[:]  # transactions used for category suggestions
    idx = 0

    def print_txn(txn, idx):
        print(f'\nTxn {idx + 1}/{len(txns)}')
        print(f'ID: {txn.get("id", "")}')
        print(f'Date: {txn.get("date", "")}')
        print(f'Amount: {txn.get("amount", "")}')
        print(f'Account: {txn.get("account", "")}')
        print(f'Description: {txn.get("description", "")}')
        print(f'Category: {txn.get("category", "") or "(none)"}')

    while 0 <= idx < len(txns):
        txn = txns[idx]
        tid = txn.get('id')
        desc = txn.get('description', '')
        suggestions = suggest_categories(desc, known)
        suggested_cat = suggestions[0][0] if suggestions else None

        print_txn(txn, idx)

        if suggestions:
            print('  Suggestions:')
            for i, (cat, score) in enumerate(suggestions, start=1):
                print(f'    {i}. {cat} ({score:.2f})')

        print(
            '\nOptions: [n]ext, [p]rev, [c]onfirm, [1-9]=pick, [e]dit field, '
            '[d]elete, [s]plit, [a]dd, [q]uit'
        )
        choice = input('> ').strip().lower()

        # --- Navigation ---
        if choice in ('n', 'next'):
            idx += 1
            continue
        elif choice in ('p', 'prev'):
            idx = max(0, idx - 1)
            continue
        elif choice in ('q', 'quit'):
            break

        # --- Confirm / Categorize ---
        elif choice in ('c', 'confirm') and suggested_cat:
            category = suggested_cat
            update = {'type': 'update', 'id': tid, 'category': category}
            write_update(update, args, updates)
            known.append({'description': desc, 'category': category})
            idx += 1
            continue

        elif choice.isdigit():
            sel = int(choice) - 1
            if 0 <= sel < len(suggestions):
                category = suggestions[sel][0]
                update = {'type': 'update', 'id': tid, 'category': category}
                write_update(update, args, updates)
                known.append({'description': desc, 'category': category})
                idx += 1
                continue

        # --- Edit arbitrary fields ---
        elif choice in ('e', 'edit'):
            field = input(
                'Field to edit (date, amount, account, description, category): '
            ).strip()
            if not field:
                continue
            value = input(f'Enter new value for {field}: ').strip()
            if value:
                update = {'type': 'update', 'id': tid, field: value}
                write_update(update, args, updates)
                if field == 'category':
                    known.append({'description': desc, 'category': value})
            idx += 1
            continue

        # --- Delete transaction ---
        elif choice in ('d', 'delete'):
            confirm = input('Delete this transaction? [y/N]: ').strip().lower()
            if confirm == 'y':
                update = {'type': 'delete', 'id': tid}
                write_update(update, args, updates)
                print('Marked for deletion.')
            idx += 1
            continue

        # --- Split transaction ---
        elif choice in ('s', 'split'):
            num_parts = input('How many parts to split into? ').strip()
            try:
                num_parts = int(num_parts)
            except ValueError:
                print('Invalid number.')
                continue

            amounts = []
            for i in range(num_parts):
                amt = input(f'  Amount for part {i + 1}: ').strip()
                cat = input(f'  Category for part {i + 1}: ').strip()
                try:
                    amt = float(amt)
                except ValueError:
                    print('Invalid amount, skipping part.')
                    continue
                amounts.append({'amount': amt, 'category': cat})

            total_split = sum(a['amount'] for a in amounts)
            orig_amt = float(txn.get('amount', 0))
            if abs(total_split - orig_amt) > 0.01:
                print(
                    f'ERROR: split total {total_split:.2f} does not match original {orig_amt:.2f}'
                )
                continue

            update = {'type': 'split', 'id': tid, 'splits': json.dumps(amounts)}
            write_update(update, args, updates)
            print('Split recorded.')
            idx += 1
            continue

        # --- Add new transaction ---
        elif choice in ('a', 'add'):
            new_txn = {}
            for field in ['date', 'description', 'amount', 'account', 'category']:
                val = input(f'{field.capitalize()}: ').strip()
                new_txn[field] = val
            new_txn['type'] = 'add'
            write_update(new_txn, args, updates)
            txns.insert(idx + 1, new_txn)
            print('New transaction added.')
            idx += 1
            continue

        else:
            print('Invalid choice.')

    print('\nDone editing transactions.')


def process_interactive(args, txns: List[dict], reference: List[dict]):
    updates: List[dict] = []
    known = reference[:]
    idx = 0

    while 0 <= idx < len(txns):
        txn = txns[idx]
        tid, desc, date, amount, account = (
            txn['id'],
            txn['description'],
            txn['date'],
            txn['amount'],
            txn['account'],
        )
        existing_category = txn.get('category', '')
        # Skip already categorized
        if txn.get('category'):
            idx += 1
            continue

        suggestions = suggest_categories(desc, known)
        suggested_cat = suggestions[0][0] if suggestions else None

        print(f'\nTxn {idx + 1}/{len(txns)}')
        print(f'Date: {date}')
        print(f'Amount: {amount}')
        print(f'Account: {account}')
        print(f'Description: {desc}')
        print(f'Category: {existing_category}')
        if suggestions:
            print('  Suggestions:')
            for i, (cat, score) in enumerate(suggestions, start=1):
                print(f'    {i}. {cat} ({score:.2f})')

        choice = (
            input('[n]ext, [p]rev, [c]onfirm, [1-9]=pick, [e]dit, [q]uit > ')
            .strip()
            .lower()
        )

        if choice in ('n', 'next'):
            idx += 1

        elif choice in ('p', 'prev'):
            idx = max(0, idx - 1)

        elif choice in ('c', 'confirm') and suggested_cat:
            category = suggested_cat if suggested_cat else ''
            update = {'type': 'update', 'id': tid, 'category': category}
            write_update(update, args, updates)
            known.append({'description': desc, 'category': category})
            idx += 1

        elif choice.isdigit():
            sel = int(choice) - 1
            if 0 <= sel < len(suggestions):
                category = suggestions[sel][0]
                update = {'type': 'update', 'id': tid, 'category': category}
                write_update(update, args, updates)
                known.append({'description': desc, 'category': category})
                idx += 1

        elif choice in ('e', 'edit'):
            new_cat = input(f'Enter category [{suggested_cat or ""}]: ').strip()
            if not new_cat and suggested_cat:
                new_cat = suggested_cat
            if new_cat:
                update = {'type': 'update', 'id': tid, 'category': new_cat}
                write_update(update, args, updates)
                known.append({'description': desc, 'category': new_cat})
            idx += 1

        elif choice in ('q', 'quit'):
            break

        else:
            print('Invalid choice.')


def run(args: argparse.Namespace) -> None:
    # Load transactions
    txns = []
    for t in args.transactions:
        txns.extend(read_csv(t))

    # Load categorized reference
    reference = []
    for c in args.categorized:
        reference.extend(read_csv(c))

    if args.overwrite and Path(args.output).exists():
        Path(args.output).unlink()

    if args.no_input:
        # Non-interactive: apply suggestions directly
        updates: List[dict] = []
        for txn in txns:
            if txn.get('category'):
                continue
            tid, desc = txn['id'], txn['description']
            suggestions = suggest_categories(desc, reference)
            if not suggestions:
                continue
            cat = suggestions[0][0]
            category = cat if args.auto_confirm else f'suggested:{cat}'
            update = {'type': 'update', 'id': tid, 'category': category}
            write_update(update, args, updates)
    else:
        # process_interactive(args, txns, reference)
        process_edit_interactive(args, txns, reference)
