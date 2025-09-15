#!/usr/bin/env python3
import argparse
import csv
import sys
from pathlib import Path
from typing import Optional, Sequence, Any
import signal

from pybudget.util import stable_id, eprint, order_columns, read_csv, write_csv

signal.signal(signal.SIGPIPE, signal.SIG_DFL)


def apply_changeset(
    primary_rows: list[dict[str, Any]],
    changeset: list[dict[str, Any]],
    skip_dangling: bool = False,
):
    """
    Apply a set of changes (add, delete, update, split) to primary_rows.

    - `add`: row with no id; will be given a new id
    - `delete`: row with id only (deletes matching transaction)
    - `update`: row with id and fields to update
    - `split`: multiple rows with the same id but different amounts;
               must sum to the original amount
    """
    merged = {row['id']: row.copy() for row in primary_rows}
    all_fields = set(primary_rows[0].keys())
    split_groups: dict[str, list[dict[str, Any]]] = {}

    for row in changeset:
        action = row.get('type', '').strip().lower()
        rid = row.get('id', '').strip()
        nonempty_fields = {
            k: v for k, v in row.items() if v and k not in ('id', 'type')
        }
        all_fields.update(row.keys())

        if action == 'delete':
            if rid in merged:
                del merged[rid]
            else:
                msg = f'delete: dangling id {rid}'
                if skip_dangling:
                    eprint(f'WARN: {msg}')
                else:
                    sys.exit(f'ERROR: {msg}')

        elif action == 'update':
            if rid in merged:
                merged[rid].update(nonempty_fields)
            else:
                msg = f'update: dangling id {rid}'
                if skip_dangling:
                    eprint(f'WARN: {msg}')
                else:
                    sys.exit(f'ERROR: {msg}')

        elif action == 'add':
            # Create a new row with a generated id
            new_row = {**{k: '' for k in all_fields}, **nonempty_fields}
            new_id = stable_id(new_row)
            new_row['id'] = new_id
            merged[new_id] = new_row

        elif action == 'split':
            if not rid:
                sys.exit('ERROR: split requires an id')
            split_groups.setdefault(rid, []).append(nonempty_fields)

        else:
            msg = f'Unknown or missing action type: {row}'
            if skip_dangling:
                eprint(f'WARN: {msg}')
            else:
                sys.exit(f'ERROR: {msg}')

    # Handle splits after gathering all rows
    for rid, splits in split_groups.items():
        if rid not in merged:
            msg = f'split: dangling id {rid}'
            if skip_dangling:
                eprint(f'WARN: {msg}')
                continue
            else:
                sys.exit(f'ERROR: {msg}')

        original = merged[rid]
        original_amount = float(original.get('amount', 0.0))
        split_total = sum(float(s.get('amount', 0.0)) for s in splits)

        if abs(split_total - original_amount) > 1e-6:
            sys.exit(
                f'ERROR: split amounts {split_total} != original {original_amount}'
            )

        # Remove the original
        del merged[rid]

        # Insert each split as a new row
        for s in splits:
            new_row = original.copy()
            new_row.update(s)
            new_id = stable_id(new_row)
            new_row['id'] = new_id
            merged[new_id] = new_row

    return list(merged.values()), sorted(all_fields)


def flatten(xss) -> list:
    return [x for xs in xss for x in xs]


def setup_parser(parser: argparse.ArgumentParser) -> None:
    """Add merge-specific arguments to a parser."""
    parser.add_argument(
        'transaction_files', help='Primary transactions CSV (base file).', nargs='+'
    )
    parser.add_argument(
        '-s',
        '--changeset',
        nargs='*',
        help='Update CSVs (e.g., categorizations, adds, deletes).',
    )
    parser.add_argument(
        '-o',
        '--output',
        help='Output file (default: stdout).',
    )
    # TODO change this to warn-dangling and error out by default
    parser.add_argument(
        '--skip-dangling',
        action='store_true',
        help='Skip changeset rows that have unknown IDs.',
    )
    parser.set_defaults(func=run)


def load_csv_changeset(path: Path) -> list[dict[str, Any]]:
    """Load a CSV changeset, ensuring 'type' is normalized to lowercase."""
    with path.open(newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
            if 'type' not in row or not row['type']:
                raise ValueError(f"Missing 'type' in changeset row: {row}")
            row['type'] = row['type'].strip().lower()
            rows.append(row)
        return rows


def load_json_changeset(path: Path) -> list[dict[str, Any]]:
    """Load a JSON changeset (array of objects)."""
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, list):
        raise ValueError('JSON changeset must be a list of objects')
    rows = []
    for row in data:
        if 'type' not in row or not row['type']:
            raise ValueError(f"Missing 'type' in changeset row: {row}")
        row['type'] = str(row['type']).strip().lower()
        rows.append(row)
    return rows


def load_changeset(path: Path) -> list[dict[str, Any]]:
    """Dispatch to the right loader based on file extension."""
    ext = path.suffix.lower()
    if ext == '.csv':
        return load_csv_changeset(path)
    elif ext == '.json':
        return load_json_changeset(path)
    else:
        raise ValueError(f'Unsupported changeset format: {path}')


def run(args: argparse.Namespace) -> None:
    primary_rows_lists = [read_csv(p) for p in args.transaction_files]
    primary_rows = flatten(primary_rows_lists)

    # Load changesets (CSV or JSON)
    secondaries = [load_changeset(Path(s)) for s in args.changeset]

    merged_rows = primary_rows
    fieldnames = list(primary_rows[0].keys())
    header_cols = order_columns(fieldnames)

    for sec in secondaries:
        merged_rows, fieldnames = apply_changeset(
            merged_rows, sec, skip_dangling=args.skip_dangling
        )

    merged_rows.sort(key=lambda d: d.get('date', ''), reverse=False)
    write_csv(merged_rows, path=args.output, fieldnames=header_cols)


def main(argv: Optional[Sequence[str]] = None) -> None:
    if argv is None:
        argv = sys.argv[1:]
    parser = argparse.ArgumentParser(
        description='Merge normalized transactions with updates (categorization, notes, adds, deletes).'
    )
    setup_parser(parser)
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == '__main__':
    main()
