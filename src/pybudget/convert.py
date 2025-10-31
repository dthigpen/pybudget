import argparse
from pathlib import Path
from .aligned_csv import convert_to_aligned, convert_to_regular


def setup_parser(parser: argparse.ArgumentParser) -> None:
    subparsers = parser.add_subparsers(dest='convert_cmd', required=True)

    to_aligned = subparsers.add_parser(
        'to-aligned-csv', help='Convert CSV to aligned format'
    )
    to_aligned.add_argument('input', type=Path)
    to_aligned.add_argument('--output', type=Path, default='-')
    to_aligned.add_argument('--max-width', type=int, default=None)
    to_aligned.set_defaults(func=run_to_aligned)

    from_aligned = subparsers.add_parser(
        'from-aligned-csv', help='Convert aligned CSV back to regular CSV'
    )
    from_aligned.add_argument('input', type=Path)
    from_aligned.add_argument('--output', type=Path, default='-')
    from_aligned.set_defaults(func=run_from_aligned)


def run_to_aligned(args: argparse.Namespace) -> None:
    out = args.output if args.output != Path('-') else Path('/dev/stdout')
    convert_to_aligned(args.input, out, args.max_width)


def run_from_aligned(args: argparse.Namespace) -> None:
    out = args.output if args.output != Path('-') else Path('/dev/stdout')
    convert_to_regular(args.input, out)
