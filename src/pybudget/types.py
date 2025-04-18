from dataclasses import dataclass, fields
from typing import Optional
from datetime import datetime

from .utils import str_to_datetime, datetime_to_str


@dataclass
class Transaction:
    date: datetime
    description: str
    amount: float
    id: Optional[str] = None
    account: Optional[str] = None
    category: Optional[str] = None

    @classmethod
    def from_csv(cls, row: dict) -> 'Transaction':
        kwargs = {}
        for f in fields(cls):
            field_name = f.name
            field_type = f.type
            value = row.get(field_name)
            if field_type == datetime:
                kwargs[field_name] = str_to_datetime(value) if value else None
            elif field_type == float:
                kwargs[field_name] = float(value) if value else 0.0
            elif field_type == Optional[str] or field_type == str:
                kwargs[field_name] = (
                    value.strip() if value is not None and value.strip() else None
                )

            else:
                raise ValueError(f'Unsupported field type: {field_type}')
        return cls(**kwargs)

    def to_row(self) -> dict:
        row = {}
        for f in fields(self):
            field_name = f.name
            val = getattr(self, f.name)
            if isinstance(val, datetime):
                row[field_name] = datetime_to_str(val)
            elif val is None:
                row[field_name] = ''
            else:
                row[field_name] = str(val)
        return row
