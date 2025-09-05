#!/usr/bin/env python3
"""
split.py - Split normalized transactions into multiple CSVs by period.

Reads one or more normalized transaction CSVs and splits them into files
by day, month, or year based on the "date" column.

Usage:
    split.py transactions.csv --by month --output-dir split/
    cat transactions.csv | split.py --by year -o split/
"""

import argparse
import csv
import sys
import signal
from pathlib import Path
from typing import List, Dict

from pybudget import util

# pipe-safe: exit quietly on broken pipes
signal.signal(signal.SIGPIPE, signal.SIG_DFL)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Split normalized transactions by period.'
    )
    parser.add_argument(
        'inputs', nargs='*', help='Normalized CSV files (default: stdin).'
    )
    parser.add_argument(
        '--by',
        choices=['day', 'month', 'year'],
        required=True,
        help='Split by day, month, or year.',
    )
    parser.add_argument(
        '-o', '--output-dir', required=True, help='Directory to write split files.'
    )
    return parser.parse_args()


def get_period(date_str: str, by: str) -> str:
    """Extract period string (YYYY[-MM[-DD]]) depending on split granularity."""
    if by == 'year':
        return date_str[:4]
    elif by == 'month':
        return date_str[:7]
    elif by == 'day':
        return date_str[:10]
    else:
        raise ValueError(f'Unsupported split granularity: {by}')


def split_file(path: str, by: str, out_dir: Path) -> None:
    """Split a single input CSV file into multiple period-based files."""
    if path == '-':
        f = sys.stdin
    else:
        f = open(path, newline='', encoding='utf-8')

    with f:
        reader = csv.DictReader(f)
        writers: Dict[str, tuple[csv.DictWriter, 'filehandle']] = {}
        rows_by_period = {}
        header_cols = set()
        for row in reader:
            period = get_period(row['date'], by)
            if period not in rows_by_period:
                rows_by_period[period] = []
            rows_by_period[period].append(row)
            header_cols.update(set(row.keys()))

        # order the header columns and add any missing standard ones
        header_cols = util.order_columns(header_cols)
        for period, rows in rows_by_period.items():
            out_path = out_dir / f'{period}-transactions.csv'
            with open(out_path, 'w', newline='', encoding='utf-8') as fh:
                writer = csv.DictWriter(fh, fieldnames=header_cols)
                writer.writeheader()
                writers[period] = (writer, fh)
                rows.sort(key=lambda d: d.get('date', ''), reverse=False)
                for row in rows:
                    writers[period][0].writerow(row)


def main() -> None:
    args = parse_args()
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.inputs:
        for path in args.inputs:
            split_file(path, args.by, out_dir)
    else:
        split_file('-', args.by, out_dir)


if __name__ == '__main__':
    main()
