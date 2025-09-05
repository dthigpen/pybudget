#!/usr/bin/env python3
"""
normalize.py - Normalize raw bank transaction CSVs into a standard schema.

Reads one or more bank CSV exports and normalizes them according to importer
config files. Each importer defines column mappings and optional static values.
Outputs a single normalized CSV with consistent columns.

Usage:
    normalize.py --importers importers/*.ini input1.csv input2.csv -o output.csv
    cat input.csv | normalize.py --importers importers/*.ini > output.csv
"""

import argparse
import csv
import hashlib
import sys
import signal
from pathlib import Path
from typing import List, Dict, Any
import configparser

from pybudget.util import stable_id

# pipe-safe: exit quietly on broken pipes
signal.signal(signal.SIGPIPE, signal.SIG_DFL)

# Standard normalized schema
NORMALIZED_COLUMNS = [
    'id',
    'date',
    'description',
    'amount',
    'account',
    'category',
    'notes',
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Normalize bank CSV transactions.')
    parser.add_argument(
        'inputs', nargs='*', help='CSV files to normalize (default: stdin).'
    )
    parser.add_argument(
        '--importers', nargs='+', required=True, help='INI importer config files.'
    )
    parser.add_argument(
        '-o', '--output', default='-', help='Output file (default: stdout).'
    )
    return parser.parse_args()


def load_importers(paths: List[str]) -> List[configparser.ConfigParser]:
    """Load INI importer configs."""
    configs = []
    for path in paths:
        cfg = configparser.ConfigParser()
        try:
            cfg.read(path)
        except configparser.MissingSectionHeaderError:
            cfg_string = '[DEFAULT]\n' + Path(path).read_text()
            cfg.read_string(cfg_string)
        configs.append(cfg)
    return configs


def match_importer(
    header: List[str], importers: List[configparser.ConfigParser], filename: str = None
) -> configparser.ConfigParser:
    """
    Match a CSV header against importers.
    Uses `match_header` (exact) or `match_header_pattern` (regex).
    """
    import re

    header_str = ','.join(header)

    for cfg in importers:
        if 'DEFAULT' not in cfg:
            continue
        sect = cfg['DEFAULT']

        if 'match_header' in sect:
            if header_str == sect['match_header']:
                return cfg
        if 'match_header_pattern' in sect:
            if re.fullmatch(sect['match_header_pattern'], header_str):
                return cfg
        if 'match_file_name_pattern' in sect and filename and filename != '-':
            if re.fullmatch(sect['match_file_name_pattern'], filename):
                return cfg
    sys.stderr.write(f'ERROR: No importer matched header: {header_str}\n')
    sys.exit(1)


def normalize_row(
    row: Dict[str, str], importer: configparser.ConfigParser
) -> Dict[str, Any]:
    """
    Normalize a single row according to importer config.
    Supports *_column (source mapping) and *_value (static values).
    """
    sect = importer['DEFAULT']
    norm = {col: '' for col in NORMALIZED_COLUMNS}

    for field in ['date', 'description', 'amount', 'account', 'category', 'notes']:
        col_key = f'{field}_column'
        val_key = f'{field}_value'

        if col_key in sect and sect[col_key] in row:
            norm[field] = row[sect[col_key]].strip()
        elif val_key in sect:
            norm[field] = sect[val_key].strip()

    # Add stable id
    norm['id'] = stable_id(norm)
    return norm


def process_file(
    path: str, importers: List[configparser.ConfigParser], writer: csv.DictWriter
) -> None:
    """Normalize a single input file."""
    if path == '-':
        filename = path
        f = sys.stdin
    else:
        f = open(path, newline='', encoding='utf-8')
        filename = Path(path).name
    with f:
        reader = csv.DictReader(f)
        importer = match_importer(reader.fieldnames, importers, filename=filename)
        for row in reader:
            writer.writerow(normalize_row(row, importer))


def main() -> None:
    args = parse_args()
    importers = load_importers(args.importers)

    if args.output == '-':
        out_f = sys.stdout
    else:
        out_f = open(args.output, 'w', newline='', encoding='utf-8')

    with out_f:
        writer = csv.DictWriter(out_f, fieldnames=NORMALIZED_COLUMNS)
        writer.writeheader()

        if args.inputs:
            for path in args.inputs:
                process_file(path, importers, writer)
        else:
            process_file('-', importers, writer)

        out_f.flush()
        try:
            out_f.close()
        except Exception:
            pass


if __name__ == '__main__':
    main()
