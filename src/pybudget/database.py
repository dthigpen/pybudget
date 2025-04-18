import sqlite3
from pathlib import Path
from typing import Generator
from rich import prompt

import csv
import os
import tempfile
import json
from .types import Transaction


class LargeCSV:
    def __init__(self, path, id_column='id', index_path=None):
        self.path = path
        self.id_column = id_column
        self.index_path = index_path or f'{path}.idx.json'
        self.index = {}
        self.fieldnames = []
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
            reader = csv.DictReader(f)
            self.fieldnames = reader.fieldnames
            f.seek(0)
            _ = f.readline()  # header
            offset = f.tell()
            for row in reader:
                self.index[row[self.id_column]] = offset
                offset = f.tell()
        self._save_index()

    def _save_index(self):
        with open(self.index_path, 'w') as f:
            json.dump({'index': self.index, 'fieldnames': self.fieldnames}, f)

    def read(self, row_id):
        offset = self.index.get(row_id)
        if offset is None:
            return None
        with open(self.path, newline='') as f:
            f.seek(offset)
            line = f.readline()
            return dict(zip(self.fieldnames, line.strip().split(',')))

    def _check_and_add_id(self, row_data):
        if not bool(row_data.get(self.id_column, None)):
            row_data[self.id_column] = self.get_next_incremental_id()
        return row_data

    def append(self, row_data):
        with open(self.path, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=self.fieldnames or row_data.keys())
            if not self.fieldnames:
                self.fieldnames = list(row_data.keys())
                writer.writeheader()
            writer.writerow(row_data)
            offset = (
                f.tell()
                - len(','.join(str(row_data.get(k, '')) for k in self.fieldnames))
                + 2
            )
            self.index[row_data[self.id_column]] = offset
        self._save_index()

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


def init_db(db_path: Path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            description TEXT NOT NULL,
            amount REAL NOT NULL,
            account TEXT NOT NULL,
            category TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            name TEXT PRIMARY KEY,
            type TEXT NOT NULL,
            goal REAL
        )
    """)

    cur.execute("""
      CREATE TABLE IF NOT EXISTS imported_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    return conn


def add_transaction(
    conn, date=None, description=None, amount=None, account=None, category=None
):
    conn.execute(
        """
        INSERT INTO transactions (date, description, amount, account, category)
        VALUES (?, ?, ?, ?, ?)
    """,
        (date, description, amount, account, category),
    )
    conn.commit()


def update_transaction_category(conn, transaction_id, new_category):
    conn.execute(
        """
        UPDATE transactions
        SET category = ?
        WHERE id = ?
    """,
        (new_category, transaction_id),
    )
    conn.commit()


def read_transactions(
    conn: sqlite3.Connection,
    uncategorized_only: bool = False,
    has_category: bool | None = None,
    description_like: str | None = None,
    account: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int | None = None,
) -> Generator[sqlite3.Row, None, None]:
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    query = 'SELECT * FROM transactions'
    filters = []
    params = []

    if uncategorized_only:
        filters.append("(category IS NULL OR category = '')")
    elif has_category is True:
        filters.append("category IS NOT NULL AND category != ''")
    elif has_category is False:
        filters.append("category IS NULL OR category = ''")

    if description_like:
        filters.append('description LIKE ?')
        params.append(f'%{description_like}%')

    if account:
        filters.append('account = ?')
        params.append(account)

    if start_date:
        filters.append('date >= ?')
        params.append(start_date)

    if end_date:
        filters.append('date <= ?')
        params.append(end_date)

    if filters:
        query += ' WHERE ' + ' AND '.join(filters)

    query += ' ORDER BY date'

    if limit:
        query += f' LIMIT {limit}'

    for row in cursor.execute(query, params):
        yield row


def read_imported_files(
    conn: sqlite3.Connection,
):
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    files_map = {}
    for row in cursor.execute('SELECT name, timestamp FROM imported_files'):
        row = dict(row)
        files_map[row['name']] = row['timestamp']
    return files_map


def add_imported_file(
    conn: sqlite3.Connection,
    file_path: str,
    timestamp=None,
):
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        INSERT INTO imported_files (name, timestamp)
        VALUES (?, ?)
    """,
        (file_path, timestamp),
    )
    conn.commit()


# TODO update imported_files

from difflib import SequenceMatcher


def suggest_category(conn: sqlite3.Connection, target_description: str) -> str | None:
    best_match = None
    highest_score = 0.0

    for row in read_transactions(conn, has_category=True):
        existing_desc = row['description']
        score = SequenceMatcher(
            None, target_description.lower(), existing_desc.lower()
        ).ratio()

        if score > highest_score:
            highest_score = score
            best_match = row['category']

    return best_match if highest_score > 0.6 else None  # threshold can be tuned


def categorize_uncategorized_transactions(conn: sqlite3.Connection):
    cursor = conn.cursor()
    for tx in read_transactions(conn, has_category=False):
        print('\nTransaction:')
        print(
            f'Date: {tx["date"]}, Description: {tx["description"]}, Amount: {tx["amount"]}, Account: {tx["account"]}'
        )

        category = None
        suggestion = suggest_category(conn, tx['description'])
        if suggestion:
            print(f'Suggested category: {suggestion}')
            use_suggested = prompt.Confirm.ask(
                f'Use suggested category "{suggestion}"'
            ).strip()
            if use_suggested:
                category = suggestion

        if not category:
            # user can type one or leave blank to skip
            # TODO or make a new one
            entered_category = prompt.Prompt.ask(
                'Enter category (or press Enter to skip categorization)'
            ).strip()
            if entered_category:
                category = entered_category

        if category:
            cursor.execute(
                'UPDATE transactions SET category = ? WHERE id = ?',
                (category, tx['id']),
            )
            conn.commit()
            print(f"Transaction categorized as '{category}'")
        else:
            print('Skipped.')


def init_large_csv(path: Path):
    if not path.exists():
        with open(path, 'w') as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    'id',
                    'date',
                    'description',
                    'amount',
                    'account',
                    'category',
                ],
            )
            writer.writeheader()
    LargeCSV(path)


if __name__ == '__main__':
    path = Path('pyb_transactions.csv')
    if not path.exists():
        with open(path, 'w') as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    'id',
                    'date',
                    'description',
                    'amount',
                    'account',
                    'category',
                ],
            )
            writer.writeheader()
            # writer.writerow({'id':123})
    large_csv = LargeCSV(path)
    import random

    for i in range(100 * 1):
        data = {
            'id': str(i),
            'date': f'{random.randint(2020, 2027)}-0{random.randint(1, 9)}-{random.randint(10, 19)}',
            'description': f'description_{random.randint(10000, 99999)}',
            'amount': f'{round(random.randint(100, 100000) / 100, 2):.2f}',
            'account': 'Some Account',
            'category': '',
        }
        transaction = Transaction.from_csv(data)

        # print(transaction)
        large_csv.append(transaction.to_row())
    row = large_csv.read('88')
    row = large_csv.read('92')
    large_csv.batch_update({'88': {'description': 'HELLO!'}})
    row = large_csv.read('92')
    print(row)
    row = large_csv.read('88')
    print(row)
    row = large_csv.read('77')
    print(row)
    large_csv.batch_delete(
        {
            '77',
        }
    )
