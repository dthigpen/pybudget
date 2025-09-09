import argparse
import sys
from . import normalize, split, merge, report


def main(argv=None) -> None:
    if argv is None:
        argv = sys.argv[1:]
    parser = argparse.ArgumentParser(prog='pybudget', description='Budgeting CLI')
    subparsers = parser.add_subparsers(dest='command', required=True)

    normalize_parser = subparsers.add_parser(
        'normalize', help='Normalize raw bank transactions'
    )
    normalize.setup_parser(normalize_parser)

    split_parser = subparsers.add_parser(
        'split', help='Split transactions into files by group'
    )
    split.setup_parser(split_parser)

    merge_parser = subparsers.add_parser(
        'merge', help='Merge transaction updates into base file'
    )
    merge.setup_parser(merge_parser)

    report_parser = subparsers.add_parser('report', help='Generate budget reports')
    report.setup_parser(report_parser)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == '__main__':
    main()
