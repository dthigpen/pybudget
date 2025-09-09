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
from typing import List, Dict, Optional, Sequence

from pybudget import util

# pipe-safe: exit quietly on broken pipes
signal.signal(signal.SIGPIPE, signal.SIG_DFL)


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
    if path == '-' or not path:
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


def setup_parser(parser: argparse.ArgumentParser) -> None:
    """Add split-specific arguments to a parser."""
    parser.add_argument(
        'input_csvs', nargs='*', help='Normalized CSV files (default: stdin).'
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
    parser.set_defaults(func=run)


def run(args: argparse.Namespace) -> None:
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.input_csvs:
        for path in args.input_csvs:
            split_file(path, args.by, out_dir)
    else:
        split_file('-', args.by, out_dir)


def main(argv: Optional[Sequence[str]] = None) -> None:
    if argv is None:
        argv = sys.argv[1:]
    parser = argparse.ArgumentParser(
        description='Split normalized transactions by day, month, or year'
    )
    setup_parser(parser)
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == '__main__':
    main()
