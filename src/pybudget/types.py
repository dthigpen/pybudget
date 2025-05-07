from dataclasses import dataclass, fields, asdict
from typing import Optional
from datetime import datetime

from .utils import str_to_datetime, datetime_to_str


@dataclass
class Transaction:
    date: datetime = None
    description: str = None
    amount: float = None
    account: Optional[str] = None
    category: Optional[str] = None

    @classmethod
    def from_csv_dict(cls, row: dict) -> 'Transaction':
        """
        Build a transaction from a dict where every value is a string
        """
        kwargs = {}
        print(f'ROW {row=}')
        for f in fields(cls):
            field_name = f.name
            field_type = f.type
            value = row.get(field_name, '')
            if value is None:
                value = ''
            value = value.strip()
            # treat any blank string as being missing
            if not value:
                continue
            if field_type == datetime:
                kwargs[field_name] = str_to_datetime(value)
            elif field_type is float:
                kwargs[field_name] = float(value)
            elif field_type == Optional[str] or field_type is str:
                kwargs[field_name] = value
            else:
                raise ValueError(f'Unsupported field type: {field_type}')
        return cls(**kwargs)

    def to_csv_dict(self) -> dict:
        """Convert this transaction to a dict where every value is a string"""
        row = {}
        for f in fields(self):
            field_name = f.name
            val = getattr(self, f.name)
            if val is None:
                row[field_name] = ''
            elif isinstance(val, datetime):
                row[field_name] = datetime_to_str(val)
            elif field_name == 'amount':
                # format to two decimal places for money
                row[field_name] = f'{val:.2f}'
            else:
                row[field_name] = str(val)
        return row

    def to_tinydb_dict(self) -> dict:
        """Converts this transaction to a dict that can serialize into JSON"""
        data = self.to_dict()
        if date := data.get('date'):
            data['date'] = datetime_to_str(date)
        return data

    @classmethod
    def from_tinydb_dict(cls, json_dict: dict) -> 'Transaction':
        """Builds a transaction from a JSON formatted dict"""
        kwargs = {}
        for f in fields(cls):
            field_name = f.name
            field_type = f.type
            value = json_dict.get(field_name)
            if value is None:
                continue
            if field_type == float:
                value = float(value)
            elif field_type == datetime:
                value = str_to_datetime(value)
            kwargs[field_name] = value
        return cls(**kwargs)

    def to_dict(self) -> dict:
        return asdict(self)
