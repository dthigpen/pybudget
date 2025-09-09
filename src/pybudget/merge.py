#!/usr/bin/env python3
import argparse
import csv
import sys
from pathlib import Path
from collections import OrderedDict
from typing import Optional, Sequence
import signal

from pybudget.util import stable_id, eprint, order_columns

signal.signal(signal.SIGPIPE, signal.SIG_DFL)


def read_csv(path):
    with open(path, newline='') as f:
        return list(csv.DictReader(f))


def write_csv(rows, fieldnames, path=None):
    if path is None or path == '-':
        writer = csv.DictWriter(
            sys.stdout, fieldnames=fieldnames, extrasaction='ignore'
        )
        writer.writeheader()
        writer.writerows(rows)
        sys.stdout.flush()
        try:
            sys.stdout.close()
        except Exception:
            pass  # don't care if stdout is already closed (e.g. piping)
    else:
        with open(path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(rows)


def apply_changeset(
    primary_rows: list[dict], changeset: list[dict], skip_dangling=False
):
    # Build lookup by id
    merged = OrderedDict((row['id'], row.copy()) for row in primary_rows)
    all_fields = set(primary_rows[0].keys())
    counter = len(merged)
    for row in changeset:
        rid = row.get('id', '').strip()
        nonempty_fields = {k: v for k, v in row.items() if v and k != 'id'}
        all_fields.update(row.keys())

        if rid and not nonempty_fields:
            # Delete
            if rid in merged:
                del merged[rid]
            else:
                if skip_dangling:
                    eprint(f'WARN: dangling delete for id {rid}')
                else:
                    sys.exit(f'ERROR: dangling delete for id {rid}')
        elif rid and nonempty_fields:
            # Update
            if rid in merged:
                merged[rid].update(nonempty_fields)
            else:
                if skip_dangling:
                    eprint(f'WARN: dangling update for id {rid}')
                else:
                    sys.exit(f'ERROR: dangling update for id {rid}')
        elif not rid and nonempty_fields:
            # Add
            # Generate a pseudo-id (could use hash or UUID here)
            new_row = {**{k: '' for k in all_fields}, **nonempty_fields, 'id': ''}
            new_id = stable_id(new_row)
            new_row['id'] = new_id
            merged[new_id] = new_row
        else:
            if skip_dangling:
                eprint(f'WARN: Unable to handle row with data {row}')
            else:
                sys.exit(f'ERROR: Unable to handle row with data {row}')

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


def run(args: argparse.Namespace) -> None:
    primary_rows_lists = [read_csv(p) for p in args.transaction_files]
    primary_rows = flatten(primary_rows_lists)
    secondaries = [read_csv(s) for s in args.changeset]

    merged_rows = primary_rows
    fieldnames = list(primary_rows[0].keys())
    header_cols = order_columns(fieldnames)

    for sec in secondaries:
        merged_rows, fieldnames = apply_changeset(
            merged_rows, sec, skip_dangling=args.skip_dangling
        )
    merged_rows.sort(key=lambda d: d.get('date', ''), reverse=False)
    write_csv(merged_rows, header_cols, args.output)


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
