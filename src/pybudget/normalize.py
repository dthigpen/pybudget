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
from typing import List, Dict, Any, Optional, Sequence
import configparser
import re

from pybudget import util

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
IMPORTER_SECTION_NAME = 'importer'


def snake_to_camel(s: str) -> str:
    """Convert snake_case (or kebab-case) to camelCase."""
    parts = re.split(r'[_-]+', s)
    return parts[0] + ''.join(p.capitalize() for p in parts[1:])


def load_importer(path: Path) -> Dict[str, Any]:
    """
    Load a single importer INI file into a normalized dict.
    Keys are camelCase regardless of input style.
    """
    cfg = configparser.ConfigParser()
    text = path.read_text()

    # Allow configs without explicit [importer] section header
    if not text.strip().lower().startswith('['):
        text = f'[importer]\n{text}'

    cfg.read_string(text)

    if 'importer' not in cfg:
        raise ValueError(f'No [importer] section found in {path}')

    sect = cfg['importer']

    # Normalize keys to camelCase
    importer_dict: Dict[str, Any] = {}
    for key, val in sect.items():
        camel_key = snake_to_camel(key.strip())
        importer_dict[camel_key] = val.strip()

    importer_dict['__path__'] = str(path)  # keep reference for debugging
    return importer_dict


def match_importer(
    header: List[str], importers: List[Dict[str, Any]], filename: str | None = None
) -> Dict[str, Any]:
    """
    Match a CSV header against a list of importer dicts.
    Uses matchHeader (exact), matchHeaderPattern (regex), or matchFileNamePattern (regex).
    """
    header_str = ','.join(header)

    for imp in importers:
        if 'matchHeader' in imp:
            if header_str == imp['matchHeader']:
                return imp
        if 'matchHeaderPattern' in imp:
            if re.fullmatch(imp['matchHeaderPattern'], header_str):
                return imp
        if 'matchFileNamePattern' in imp and filename and filename != '-':
            if re.fullmatch(imp['matchFileNamePattern'], filename):
                return imp

    sys.stderr.write(f'ERROR: No importer matched header: {header_str}\n')
    sys.exit(1)


def normalize_row(row: Dict[str, str], importer: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize a single row according to importer config dict.
    Supports *Column (source mapping) and *Value (static values).
    """
    norm = {col: '' for col in NORMALIZED_COLUMNS}

    for field in ['date', 'description', 'amount', 'account', 'category', 'notes']:
        col_key = f'{field}Column'
        val_key = f'{field}Value'

        if col_key in importer and importer[col_key] in row:
            norm[field] = row[importer[col_key]].strip()
        elif val_key in importer:
            norm[field] = importer[val_key].strip()

    # Handle amount + flipSign
    try:
        norm['amount'] = float(norm['amount'])
    except (TypeError, ValueError):
        norm['amount'] = 0.0

    flip_sign = importer.get('flipSign', 'false').lower() in ('true', '1', 'yes')
    if flip_sign:
        norm['amount'] *= -1

    # Add stable id
    norm['id'] = util.stable_id(norm)
    return norm


def normalize_keys(d: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize dict keys to camelCase."""

    def to_camel(s: str) -> str:
        parts = s.replace('-', '_').split('_')
        return parts[0] + ''.join(p.capitalize() for p in parts[1:])

    return {to_camel(k): v for k, v in d.items()}


def load_ini_importer(path: Path) -> Dict[str, Any]:
    """Load and normalize a single INI importer config into dict form."""
    cfg = configparser.ConfigParser()
    try:
        cfg.read(path)
    except configparser.MissingSectionHeaderError:
        # Wrap raw key=val files with a section
        cfg_string = '[importer]\n' + path.read_text()
        cfg.read_string(cfg_string)

    if 'importer' not in cfg:
        raise ValueError(f'Importer file {path} missing [importer] section')

    return normalize_keys(dict(cfg['importer']))


def load_json_importer(path: Path) -> Dict[str, Any]:
    """Load and normalize a single JSON importer config into dict form."""
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f'Importer JSON {path} must be an object at the top level')

    return normalize_keys(data)


def load_importers(paths: List[Path]) -> List[Dict[str, Any]]:
    """
    Load multiple importers (INI or JSON).
    Returns list of normalized dicts.
    """
    importers: List[Dict[str, Any]] = []

    for path in paths:
        ext = path.suffix.lower()
        if ext in ('.ini', ''):
            importers.append(load_ini_importer(path))
        elif ext == '.json':
            importers.append(load_json_importer(path))
        else:
            raise ValueError(f'Unsupported importer format: {path}')

    return importers


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


def setup_parser(parser: argparse.ArgumentParser) -> None:
    """Add normalize-specific arguments to a parser."""
    parser.add_argument('input_csvs', nargs='+', help='Input CSV(s)')
    parser.add_argument(
        '--importers',
        nargs='+',
        type=util.existing_file,
        required=True,
        help='INI importer config files.',
    )
    parser.add_argument('-o', '--output', help='Output CSV (default: stdout)')
    parser.set_defaults(func=run)


def run(args: argparse.Namespace) -> None:
    # print(f"Normalizing {args.input} → {args.output or 'stdout'}")
    importers = load_importers(args.importers)

    if args.output == '-' or not args.output:
        out_f = sys.stdout
    else:
        out_f = open(args.output, 'w', newline='', encoding='utf-8')

    with out_f:
        writer = csv.DictWriter(out_f, fieldnames=NORMALIZED_COLUMNS)
        writer.writeheader()

        if args.input_csvs:
            for path in args.input_csvs:
                process_file(path, importers, writer)
        else:
            process_file('-', importers, writer)

        out_f.flush()
        try:
            out_f.close()
        except Exception:
            pass


def main(argv: Optional[Sequence[str]] = None) -> None:
    if argv is None:
        argv = sys.argv[1:]
    parser = argparse.ArgumentParser(description='Normalize raw bank transactions')
    setup_parser(parser)
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == '__main__':
    main()
