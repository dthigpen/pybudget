import re
from datetime import datetime
from pybudget.utils import str_to_datetime
from tinydb import Query

FILTER_FIELD_TYPES = {
    'id': 'int',
    'date': 'date',
    'description': 'string',
    'amount': 'float',
    'category': 'string',
    'account': 'string',
}


def parse_filter_arg(filter_str: str) -> tuple[str, str, str | float | int | datetime]:
    re_match = re.match(r'(\w+)([!=<>~]{1,2})(.*)', filter_str)
    if not re_match:
        raise ValueError(f'Invalid filter: {filter_str}')
    field_name, op, op_value = (
        re_match.group(1),
        re_match.group(2),
        re_match.group(3).strip(),
    )

    aliases = {'desc': 'description'}
    field_name = aliases.get(field_name, field_name)

    return field_name, op, op_value


def apply_filters(rows: list[dict], filters: list[str]):
    """Returns only rows matching all given filter expressions."""
    parsed_filters = [parse_filter_arg(f) for f in filters]

    def matches(row):
        for field, op, value in parsed_filters:
            rv = row.get(field)
            if FILTER_FIELD_TYPES[field] == 'date' and isinstance(rv, str):
                value = datetime.fromisoformat(value)
                rv = datetime.fromisoformat(rv)
            if FILTER_FIELD_TYPES[field] == 'int':
                value = int(value)
                rv = int(rv)
            if FILTER_FIELD_TYPES[field] == 'float':
                value = float(value)
                rv = float(rv)

            if op == '=' and rv != value:
                return False
            elif op == '!=' and rv == value:
                return False
            elif op == '>' and rv <= value:
                return False
            elif op == '<' and rv >= value:
                return False
            elif op == '>=' and rv < value:
                return False
            elif op == '<=' and rv > value:
                return False
            elif op == '~' and value.lower() not in str(rv).lower():
                return False
        return True

    return (r for r in rows if matches(r))


def construct_filters_query(
    filters: list[str],
) -> Query:
    filters = [parse_filter_arg(f) for f in filters] if filters else []
    query = None
    for field_name, op, op_value in filters:
        q = Query()[field_name]

        # now determine the type
        if field_name in FILTER_FIELD_TYPES:
            field_type = FILTER_FIELD_TYPES[field_name]
        else:
            field_type = 'string'
            print(f'Warning: unknown field {field_name}')
            # TODO could also raise here if strict mode

        row_value_fn = lambda v: v
        try:
            if field_type == 'float':
                op_value = float(op_value)
            elif field_type == 'int':
                op_value = int(op_value)
            elif field_type == 'date' and '~' not in op:
                op_value = str_to_datetime(op_value)
                row_value_fn = str_to_datetime
            else:
                op_value = str(op_value).lower()
                row_value_fn = lambda v: str('' if v is None else v).lower()
        except (ValueError, TypeError) as e:
            msg = f"Error parsing filter for field '{field}': {e}"
            if strict:
                raise ValueError(msg)
            print(msg)

        match op:
            case '=':
                q = q.test(lambda v: row_value_fn(v) == op_value)
            case '!=':
                q = q.test(lambda v: row_value_fn(v) != op_value)
            case '<':
                q = q.test(lambda v: row_value_fn(v) < op_value)
            case '<=':
                q = q.test(lambda v: row_value_fn(v) <= op_value)
            case '>':
                q = q.test(lambda v: row_value_fn(v) > op_value)
            case '>=':
                q = q.test(lambda v: row_value_fn(v) >= op_value)
            case '~':
                q = q.test(lambda v: op_value in row_value_fn(v))
            case '!~':
                q = q.test(lambda v: op_value not in row_value_fn(v))
        if not query:
            query = q
        else:
            query = query & q
    return query
