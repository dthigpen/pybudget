import argparse
import sys
from . import normalize, split, apply, report, init, categorize


def main(argv=None) -> None:
    if argv is None:
        argv = sys.argv[1:]
    parser = argparse.ArgumentParser(prog='pybudget', description='Budgeting CLI')
    subparsers = parser.add_subparsers(dest='command', required=True)

    init_parser = subparsers.add_parser(
        'init',
        help='Initialize starter files. (e.g. an importer, changeset, or budget file)',
    )
    init.setup_parser(init_parser)

    normalize_parser = subparsers.add_parser(
        'normalize', help='Normalize raw bank transactions'
    )
    normalize.setup_parser(normalize_parser)

    split_parser = subparsers.add_parser(
        'split', help='Split transactions into files by group'
    )
    split.setup_parser(split_parser)

    categorize_parser = subparsers.add_parser(
        'categorize', help='categorize transactions'
    )
    categorize.setup_parser(categorize_parser)

    apply_parser = subparsers.add_parser(
        'apply', help='apply transaction updates into base file'
    )
    apply.setup_parser(apply_parser)

    report_parser = subparsers.add_parser('report', help='Generate budget reports')
    report.setup_parser(report_parser)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == '__main__':
    main()
