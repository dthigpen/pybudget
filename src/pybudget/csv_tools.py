from .types import Transaction

from pathlib import Path
import csv
import os
import tempfile
import json
from typing import Literal
import sys


class LargeCSV:
    def __init__(
        self, path: Path, id_column='id', index_path: Path = None, fieldnames=None
    ):
        self.path = Path(path)
        self.id_column = id_column
        # e.g. data.csv to data.idx.json
        self.index_path = index_path or (
            self.path.with_name(self.path.name + '.idx.json')
        )
        self.index = {}
        self.fieldnames = fieldnames if fieldnames is not None else []
        self._load_or_build_index()

    def _load_or_build_index(self):
        try:
            with open(self.index_path, 'r') as f:
                data = json.load(f)
                self.index = data['index']
                self.fieldnames = data['fieldnames']
        except (FileNotFoundError, json.JSONDecodeError):
            self.rebuild_index()

    def rebuild_index(self):
        self.index = {}
        with open(self.path, newline='') as f:
            header = f.readline()
            reader = csv.DictReader([header])
            self.fieldnames = reader.fieldnames

            if self.id_column not in self.fieldnames:
                raise ValueError(
                    f'Missing "{self.id_column}" field in CSV header: {header}'
                )
            while True:
                offset = f.tell()  # Byte offset before reading line
                line = f.readline()
                if not line:
                    break

                # parse line using csv
                row = next(csv.DictReader([line], fieldnames=self.fieldnames))
                self.index[row[self.id_column]] = offset

        self._save_index()

    def _save_index(self):
        with open(self.index_path, 'w') as f:
            json.dump({'index': self.index, 'fieldnames': self.fieldnames}, f)

    def read_one(self, row_id):
        result = list(self.read_many(row_id))
        return result[0] if result else None

    def read_many(self, *row_ids):
        if row_ids:
            for row_id in row_ids:
                offset = self.index.get(row_id)
                if offset is None:
                    return None
                with open(self.path, newline='') as f:
                    f.seek(offset)
                    line = f.readline()
                    yield dict(zip(self.fieldnames, line.strip().split(',')))
        else:
            with open(self.path, newline='') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    yield row

    def _check_and_add_id(self, row_data):
        if not bool(row_data.get(self.id_column, None)):
            row_data[self.id_column] = self.get_next_incremental_id()
        return row_data

    def append(self, *row_datas):
        results = []
        with open(self.path, 'a', newline='') as f:
            writer = None
            for row_data in row_datas:
                if not writer:
                    writer = csv.DictWriter(
                        f, fieldnames=self.fieldnames or row_data.keys()
                    )
                    if not self.fieldnames:
                        self.fieldnames = list(row_data.keys())
                        writer.writeheader()
                self._check_and_add_id(row_data)
                offset = f.tell()
                writer.writerow(row_data)
                self.index[row_data[self.id_column]] = offset
                results.append(row_data)
        self._save_index()
        return results

    def batch_replace(self, updates_dict: dict):
        empty_values = {k: '' for k in self.fieldnames if k != self.id_column}
        if empty_values:
            for k in updates_dict:
                updates_dict[k] = {**empty_values, **updates_dict[k]}
        self.batch_update(updates_dict)

    def batch_update(self, updates_dict):
        updated = set()
        with (
            open(self.path, newline='') as f,
            tempfile.NamedTemporaryFile('w', newline='', delete=False) as temp,
        ):
            reader = csv.DictReader(f)
            writer = csv.DictWriter(temp, fieldnames=self.fieldnames)
            writer.writeheader()

            offset = temp.tell()
            for row in reader:
                row_id = row[self.id_column]
                if row_id in updates_dict:
                    row.update(updates_dict[row_id])
                    updated.add(row_id)
                writer.writerow(row)
                self.index[row[self.id_column]] = offset
                offset = temp.tell()

        os.replace(temp.name, self.path)
        self._save_index()
        return updated

    def batch_delete(self, ids_to_delete):
        deleted = set()
        with (
            open(self.path, newline='') as f,
            tempfile.NamedTemporaryFile('w', newline='', delete=False) as temp,
        ):
            reader = csv.DictReader(f)
            writer = csv.DictWriter(temp, fieldnames=self.fieldnames)
            writer.writeheader()

            offset = temp.tell()
            for row in reader:
                row_id = row[self.id_column]
                if row_id in ids_to_delete:
                    deleted.add(row_id)
                    continue
                writer.writerow(row)
                self.index[row_id] = offset
                offset = temp.tell()

        os.replace(temp.name, self.path)
        for row_id in deleted:
            self.index.pop(row_id, None)
        self._save_index()
        return deleted

    def query(self, **filters):
        """Yield rows matching all given column=value filters."""
        with open(self.path, newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if all(row.get(k) == str(v) for k, v in filters.items()):
                    yield row

    def get_next_incremental_id(self):
        if not self.index:
            return '1'
        try:
            existing_ids = [int(i) for i in self.index.keys()]
            return str(max(existing_ids) + 1)
        except ValueError:
            raise ValueError(
                'Non-integer ID found in index; cannot auto-increment safely.'
            )


class TransactionsCSV:
    def __init__(
        self,
        path: Path,
        csv_column_names: dict[
            Literal['id', 'date', 'description', 'amount', 'account', 'category'], str
        ] = None,
    ):
        """
        Args:
            path: path to a csv file
            csv_column_names: a dict mapping where the key is a transaction field name and the value is a column name
        """
        # order of the transaction fields in the csv
        transaction_field_order = [
            'id',
            'date',
            'description',
            'amount',
            'account',
            'category',
        ]
        # the column names themselves
        # defaults to the same as the field names
        if not csv_column_names:
            csv_column_names = {f: f for f in transaction_field_order}
        ordered_column_names = [csv_column_names[k] for k in transaction_field_order]
        self.path = path
        init_large_csv(
            self.path,
            fieldnames=ordered_column_names,
        )
        self.large_csv = LargeCSV(self.path, fieldnames=ordered_column_names)

    def add(self, *txns: Transaction):
        return [
            Transaction.from_csv(d)
            for d in self.large_csv.append(*[t.to_row() for t in txns])
        ]

    def update(self, *txns: Transaction):
        updates = {t.id: t.to_row() for t in txns}
        self.large_csv.batch_update(updates)

    def replace(self, *txns: Transaction):
        replacements = {t.id: t.to_row() for t in txns}
        self.large_csv.batch_replace(replacements)

    def delete(self, *ids: int):
        self.large_csv.batch_delete(ids)

    def read_many(self, *ids: int):
        for t in self.large_csv.read_many(*ids):
            yield Transaction.from_csv(t)

    def read_one(self, row_id: int):
        t = self.large_csv.read_one(str(row_id))
        return Transaction.from_csv(t) if t else None


def init_large_csv(path: Path, fieldnames: list[str]):
    if not path.exists():
        with open(path, 'w') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
    LargeCSV(path)


def read_transactions_from_csv(
    csv_path: Path, column_names: dict = None, default_values: dict = None
) -> list[Transaction]:
    column_names = column_names or {}
    default_values = default_values or {}
    # TODO find a more robust way of doing this
    if csv_path == '-':
        csvfile = sys.stdin
    else:
        csvfile = open(csv_path, newline='')
    try:
        reader = csv.DictReader(csvfile)
        required_fields = set(('date', 'description', 'amount', 'account'))
        non_required_fields = set(['id', 'category'])
        all_fields = required_fields | non_required_fields
        for row in reader:
            actual_field_values = {}
            for field in all_fields:
                # function was given a specific column name for this field
                if (col_name := column_names.get(field)) and col_name in row:
                    actual_field_values[field] = row[col_name]
                elif field in required_fields:
                    # no specific column name, try directly and title case
                    # e.g look for an "amount" or "Amount" column
                    if row.get(field):
                        actual_field_values[field] = row[field]
                    elif row.get(field.title()):
                        actual_field_values[field] = row[field.title()]

                # use default value if could not get it from file and in defaults
                if (
                    field not in actual_field_values
                    and default_values.get(field) is not None
                ):
                    actual_field_values[field] = default_values[field]

            missing_fields = required_fields - set(actual_field_values.keys())
            if missing_fields:
                raise ValueError(
                    f'Expected to receive column names or defaults for {csv_path}. Missing field {missing_fields}'
                )
            yield Transaction.from_csv(actual_field_values)
    finally:
        if csv_path != '-' and csvfile:
            csvfile.close()
