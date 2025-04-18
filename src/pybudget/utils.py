from datetime import datetime


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


def match_filters(row, filters):
    """Check if a CSV row matches the provided filter criteria."""
    # Date filters
    if 'start_date' in filters:
        row_date = parse_date(row.get('date'))
        if not row_date or row_date < filters['start_date']:
            return False
    if 'end_date' in filters:
        row_date = parse_date(row.get('date'))
        if not row_date or row_date > filters['end_date']:
            return False

    # Field-based filters
    for key, val in filters.get('fields', {}).items():
        row_val = row.get(key, '')
        if key == 'description':
            if val.lower() not in row_val.lower():
                return False
        else:
            if row_val != val:
                return False

    return True


def parse_date(date_str):
    """Try to parse a date string into a datetime object."""
    try:
        return datetime.strptime(date_str, '%Y-%m-%d')
    except (ValueError, TypeError):
        return None
