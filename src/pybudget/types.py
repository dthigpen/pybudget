from dataclasses import dataclass, fields, asdict
from typing import Optional
from datetime import datetime

from .utils import str_to_datetime, datetime_to_str


@dataclass
class Transaction:
    date: datetime = None
    description: str = None
    amount: float = None
    id: Optional[str] = None
    account: Optional[str] = None
    category: Optional[str] = None

    @classmethod
    def from_str_dict(cls, row: dict) -> 'Transaction':
        kwargs = {}
        for f in fields(cls):
            field_name = f.name
            field_type = f.type
            value = row.get(field_name)
            if field_type == datetime:
                kwargs[field_name] = str_to_datetime(value) if value else None
            elif field_type is float:
                kwargs[field_name] = float(value) if value else 0.0
            elif field_type == Optional[str] or field_type is str:
                kwargs[field_name] = (
                    value.strip() if value is not None and value.strip() else None
                )

            else:
                raise ValueError(f'Unsupported field type: {field_type}')
        return cls(**kwargs)

    def to_str_dict(self) -> dict:
        row = {}
        # TODO determine if this should output None as '' or not include at all
        for f in fields(self):
            field_name = f.name
            val = getattr(self, f.name)
            if isinstance(val, datetime):
                row[field_name] = datetime_to_str(val)
            elif field_name == 'amount':
                # format to two decimal places for money
                row[field_name] = f'{val:.2f}'
            elif val is None:
                row[field_name] = ''
            else:
                row[field_name] = str(val)
        return row

    def to_json_dict(self) -> dict:
        # NOTE note sure if this is the best thing to do here but it keeps the json clean
        data = {
            k: v for k, v in self.to_dict().items() if v is not None and v is not ''
        }
        data.pop('id', None)

        if date := data.get('date'):
            data['date'] = datetime_to_str(date)
        return data

    @classmethod
    def from_json_dict(cls, json_dict: dict) -> 'Transaction':
        kwargs = {}
        for f in fields(cls):
            field_name = f.name
            field_type = f.type
            value = json_dict.get(field_name)
            if value is None:
                continue
            if field_type == datetime:
                value = str_to_datetime(value)
            kwargs[field_name] = value

        return cls(**kwargs)

    def to_dict(self) -> dict:
        return asdict(self)
