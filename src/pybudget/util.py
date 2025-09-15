import hashlib
import sys
from pathlib import Path
import csv
from typing import Any, Literal

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


def read_csv(path: Path):
    with open(path, newline='') as f:
        return list(csv.DictReader(f))


def write_csv(rows: list[dict], path: Path = None, fieldnames: list = None):
    if path is None or path == '-':
        writer = csv.DictWriter(
            sys.stdout, fieldnames=fieldnames, extrasaction='ignore'
        )
        writer.writeheader()
        writer.writerows(rows)
        sys.stdout.flush()
        try:
            sys.stdout.close()
        except Exception as e:
            # TODO match exact exception
            sys.stderr.write(f'EXCEPTION: {e}')
            pass  # don't care if stdout is already closed (e.g. piping)
    else:
        with open(path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(rows)


def read_json(path: Path) -> Any:
    return json.loads(Path(path).read_text(path))


def write_json(data: Any, path: Path = None, **json_kwargs):
    if path is None or path == '-':
        json.dump(data, sys.stdout, **json_kwargs)
        sys.stdout.flush()
        try:
            sys.stdout.close()
        except Exception as e:
            # TODO match exact exception
            sys.stderr.write(f'EXCEPTION: {e}')
            pass  # don't care if stdout is already closed (e.g. piping)
    else:
        with open(path, 'w', newline='') as f:
            json.dump(data, f, **json_kwargs)


def write_csv_or_json(
    data: Any, path: Path, fmt: Literal['csv', 'json'] = None, **kwargs
):
    if not fmt:
        fmt = path.suffix[1:] if path.suffix else ''

    if fmt == 'json':
        return write_json(data, path=path, **kwargs)
    elif fmt == 'csv':
        return write_csv(data, path=path, **kwargs)
    else:
        raise ValueError(f'Cannot output to path {path}, unknown output format {fmt}.')


def read_csv_or_json(path: Path, fmt: Literal['csv', 'json'] = None, **kwargs):
    if not fmt:
        fmt = path.suffix[1:] if path.suffix else ''

    if fmt == 'json':
        return read_json(path=path, **kwargs)
    elif fmt == 'csv':
        return read_csv(path=path, **kwargs)
    else:
        raise ValueError(f'Cannot read from path {path}, unknown input format {fmt}.')


def write_file_or_stdout():
    pass
