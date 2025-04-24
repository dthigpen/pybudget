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
