import hashlib
import sys
from pathlib import Path

DEFAULT_ORDERED_COLUMNS = [
    'id',
    'date',
    'description',
    'amount',
    'account',
    'category',
    'notes',
]


def order_columns(given_fields: list[str], append_extras=True) -> list[str]:
    standard_set = set(DEFAULT_ORDERED_COLUMNS)
    given_set = set(given_fields)
    extras = given_set - standard_set
    standard_list = list(filter(lambda x: x in given_set, DEFAULT_ORDERED_COLUMNS))
    standard_list.extend(list(extras))
    return standard_list


def stable_id(row: dict[str, str]) -> str:
    """Generate stable hash ID from critical fields."""
    raw_id = '|'.join(
        [
            str(row.get(col, '')).strip()
            for col in ['date', 'description', 'amount', 'account']
        ]
    )
    return hashlib.sha1(raw_id.encode('utf-8')).hexdigest()[:10]


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def existing_file(p: str) -> Path:
    p = Path(p)
    if not p.is_file():
        raise argparse.ArgumentTypeError(f'Path {p} must be an existing file')
    return p
