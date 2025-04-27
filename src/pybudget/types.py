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

    def to_dict(self) -> dict:
        return asdict(self)
