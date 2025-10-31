from pathlib import Path
from typing import List, Dict, Optional
import csv


def read_aligned_csv(path: Path) -> List[Dict[str, str]]:
    """Read a CSV file, trimming trailing spaces inside each field."""
    with path.open(newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        return [
            {
                k.strip(): (v.strip() if isinstance(v, str) else v)
                for k, v in row.items()
            }
            for row in reader
        ]


def write_aligned_csv(
    rows: List[Dict[str, str]],
    fieldnames: List[str],
    output: Path,
    max_width: Optional[int] = None,
) -> None:
    """Write a CSV with columns visually aligned for plain-text editing."""
    if not rows:
        output.write_text('', encoding='utf-8')
        return

    # Compute widths
    widths = {
        fn: min(
            max(len(fn), max((len(str(r.get(fn, ''))) for r in rows), default=0)),
            max_width or float('inf'),
        )
        for fn in fieldnames
    }

    def format_value(value: str, field: str, is_last: bool) -> str:
        val = str(value).rstrip()
        if not is_last:
            # Always one space before and after
            return f' {val:<{int(widths[field])}} '
        else:
            # Only one leading space for last column
            return f' {val}'

    lines = []
    header = ','.join(
        format_value(fn, fn, i == len(fieldnames) - 1)
        for i, fn in enumerate(fieldnames)
    )
    lines.append(header)

    for row in rows:
        line = ','.join(
            format_value(row.get(fn, ''), fn, i == len(fieldnames) - 1)
            for i, fn in enumerate(fieldnames)
        )
        lines.append(line)

    output.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def convert_to_aligned(
    input_path: Path, output_path: Path, max_width: Optional[int] = None
) -> None:
    """Reformat an existing CSV to aligned CSV."""
    with input_path.open(newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        write_aligned_csv(rows, reader.fieldnames, output_path, max_width)


def convert_to_regular(input_path: Path, output_path: Path) -> None:
    """Convert aligned CSV to regular (strip padded spaces)."""
    rows = read_aligned_csv(input_path)
    fieldnames = rows[0].keys() if rows else []
    with output_path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
