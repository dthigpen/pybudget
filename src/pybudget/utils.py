from datetime import datetime
import shutil
import tempfile
import os
from pathlib import Path
from contextlib import contextmanager


def str_to_datetime(value: str) -> datetime:
    return datetime.strptime(value, '%Y-%m-%d')


def datetime_to_str(value: datetime) -> str:
    return value.strftime('%Y-%m-%d')


def extract_filters(args):
    filters = {}

    # Convert date strings to datetime objects if provided
    if args.start_date:
        filters['start_date'] = datetime.strptime(args.start_date, '%Y-%m-%d')
    if args.end_date:
        filters['end_date'] = datetime.strptime(args.end_date, '%Y-%m-%d')

    # Add any field-based filters
    field_filters = {}
    for field in ['description', 'account', 'category']:
        val = getattr(args, field, None)
        if val:
            field_filters[field] = val
    if field_filters:
        filters['fields'] = field_filters

    return filters


@contextmanager
def safe_file_update_context(
    original_path: Path, suffix='.tmp', keep_backup: bool = False, dry_run: bool = False
):
    """
    Context manager to safely update a file. Work with a temp copy and commit changes only if all succeeds.

    Usage:
        with safe_file_update_context(Path("data.csv")) as temp_path:
            # read/write temp_path
            ...
        # temp file replaces original only if block succeeds
    """
    original_path = Path(original_path).resolve()
    parent_dir = original_path.parent

    # Create a temp file in the same directory
    with tempfile.NamedTemporaryFile(
        mode='w+b', dir=parent_dir, suffix=suffix, delete=False
    ) as tmp:
        temp_path = Path(tmp.name)

    try:
        print(f'Creating temp file from {original_path.name}')
        # Copy contents and metadata to the temp file
        if original_path.is_file():
            shutil.copy2(original_path, temp_path)

        yield temp_path  # Let the caller modify the temp file

        print(f'Cleaning up temp file {temp_path.name}')
        if dry_run:
            return

        if keep_backup:
            backup_path = original_path.with_suffix(original_path.suffix + '.bak')
            shutil.copy2(original_path, backup_path)

        # Atomically replace the original file with the temp one
        temp_path.replace(original_path)

    except Exception as e:
        temp_path.unlink(missing_ok=True)
        raise RuntimeError(f'Failed to update {original_path}: {e}') from e
