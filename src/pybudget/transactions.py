import csv
import sys
import json
import re
from enum import Enum
from typing import Literal
from pathlib import Path
from pybudget import csv_tools
from pybudget.utils import (
    str_to_datetime,
    datetime_to_str,
    safe_file_update_context,
    load_config,
)
from pybudget.types import Transaction
from pybudget.filtering import construct_filters_query
from pybudget import suggestions
import difflib

from tinydb import TinyDB, Query

DATA_FILE_COLUMNS = ['id', 'date', 'description', 'amount', 'account', 'category']


def list_transactions(
    db_path: Path,
    config_path: Path,
    filters: list[str] = None,
    only_uncategorized=False,
    suggest_categories: bool = False,
    ids: list[int] = None,
) -> list[Transaction]:
    db = TinyDB(db_path)
    transactions = db.table('transactions')
    ids = ids or []
    all_txns = []
    if suggest_categories:
        all_txns = list(Transaction.from_tinydb_dict(t) for t in transactions.all())

    filters = filters or []
    if only_uncategorized:
        filters.append('category=')
    if ids:
        for t in transactions.get(doc_ids=ids):
            yield Transaction.from_tinydb_dict(t)

    else:
        filter_query = construct_filters_query(filters)
        for t in (
            transactions.search(filter_query) if filter_query else transactions.all()
        ):
            doc_id = t.doc_id
            t = Transaction.from_tinydb_dict(t)
            if suggest_categories and (not t.category or t.category == 'uncategorized'):
                results = suggestions.suggest_categories(t.description, all_txns)
                if results:
                    t.suggested_category = results[0][0]
                else:
                    t.suggested_category = None
            yield t


def find_importer(p: Path, importers: list) -> dict:
    """Find an importer for the given csv path"""
    matching_importer = None
    for importer in importers:
        if not importer.get('matcher'):
            print(f'Importer named "{importer["name"]}" has no matcher criteria')
            continue
        passed_matcher = True
        for criteria, value in importer.get('matcher', {}).items():
            if criteria == 'filenameContains':
                if value not in p.name:
                    passed_matcher = False
                    break
            elif criteria == 'headers':
                # TODO handle custom delimiter
                with open(p) as f:
                    header_line = f.readline()
                for col in value:
                    if col not in header_line:
                        passed_matcher = False
                        break
            else:
                raise ValueError(f'Unrecognized matcher criteria: {criteria}')
        if passed_matcher:
            matching_importer = importer
            break
    return matching_importer


def import_transactions(
    db_path: Path,
    config_path: Path,
    csv_paths: list[Path],
    importer_name: str = None,
) -> list[Transaction]:
    # open db
    db = TinyDB(db_path)
    transactions = db.table('transactions')

    # load config
    config = load_config(config_path)
    importers = config.get('importers')
    named_importer = None
    if importer_name:
        named_importer = next(
            (x for x in importers if x['name'] == importer_name), None
        )
        if not named_importer:
            raise ValueError(f'Failed to find importer by name "{importer_name}"')
    added_transactions = []
    added_ids = []
    for p in csv_paths:
        # find matching importer or use named one
        matching_importer = (
            named_importer if named_importer else find_importer(p, importers)
        )
        if matching_importer:
            print(f'Using "{matching_importer["name"]}" importer')
        else:
            raise ValueError(
                'Failed to find a matching importer. Please check your importers conditions and try again.'
            )

        # get column name mapping for importer
        column_names = {
            'date': matching_importer.get('dateColumn', 'Transaction Date'),
            'description': matching_importer.get('descriptionColumn', 'Description'),
            'amount': matching_importer.get('amountColumn', 'Amount'),
            'account': matching_importer.get('accountColumn', 'Account'),
            'category': matching_importer.get('categoryColumn', None),
        }
        # get default value mapping for importer
        default_values = {
            'date': matching_importer.get('dateValue', ''),
            'description': matching_importer.get('descriptionValue', ''),
            'amount': matching_importer.get('amountValue', ''),
            'account': matching_importer.get('accountValue', ''),
            'category': matching_importer.get('categoryValue', ''),
        }
        transactions_in_file = []
        for txn_dict in csv_tools.read_dicts_from_csv(
            p, column_names_mapping=column_names, default_values=default_values
        ):
            transaction = Transaction.from_csv_dict(txn_dict)
            validate_transaction(transaction)
            # flip sign for something like a credit card
            # where transactions "add" to the credit
            if matching_importer.get('flipSign'):
                transaction.amount = -1 * transaction.amount
            transactions_in_file.append(transaction)

        # insert all transactions from file
        if transactions_in_file:
            json_txns_to_insert = [t.to_tinydb_dict() for t in transactions_in_file]
            added_ids += transactions.insert_multiple(json_txns_to_insert)

        print(f'Finished importing {p}')

    return (
        Transaction.from_tinydb_dict(t) for t in transactions.get(doc_ids=added_ids)
    )


def delete_transactions(db_path, config, ids: list[id]):
    db = TinyDB(db_path)
    transactions = db.table('transactions')
    ids = set(ids)
    transactions.remove(doc_ids=ids)


def validate_transaction(txn: Transaction):
    if (
        txn.date is None
        or not txn.description
        or txn.amount is None
        or txn.account is None
    ):
        raise ValueError(
            'Transaction must have a valid date, description, amount, and account value. Invalid transaction: {txn}'
        )


def edit_transactions(
    db_path: Path,
    config_path: Path,
    from_path: Path | Literal['-'],
    ids: list[int] = None,
    filters: list[str] = None,
    new_date: str = None,
    new_description: str = None,
    new_amount: float = None,
    new_account: str = None,
    new_category: str = None,
) -> list[Transaction]:
    """Update transactions with new values for each field. Either a specific one by id or multiple from a csv file
    Note: to empty out a field, pass the empty string '' for that value
    """
    # open db
    db = TinyDB(db_path)
    transactions = db.table('transactions')

    filters = filters or []
    ids = ids or []
    column_names = {c: c for c in DATA_FILE_COLUMNS}
    updated = []
    update_delete_pairs = []
    updated_ids = []
    if from_path:
        # read in rows from the csv
        # converts to the right data types then converts it back to a dict
        csv_dicts = csv_tools.read_dicts_from_csv(
            from_path, column_names_mapping=column_names
        )
        for csv_dict in csv_dicts:
            # rows with empty values will be treating as removing/reseting that field
            # otherwise use the value
            keys_to_delete = {k for k, v in csv_dict.items() if v in ('',)}
            updates_dict = {
                k: v for k, v in csv_dict.items() if k not in keys_to_delete
            }
            update_delete_pairs.append((updates_dict, keys_to_delete))
    elif ids or filters:
        results = list(
            list_transactions(
                db_path,
                config_path,
                filters=filters,
                ids=ids,
            )
        )
        for res in results:
            updates_dict = {
                'id': res.id,
                'date': new_date,
                'description': new_description,
                'amount': new_amount,
                'account': new_account,
                'category': new_category,
            }
            # filter out None since None is used when caller does not pass a value
            updates_dict = {k: v for k, v in updates_dict.items() if v is not None}
            keys_to_delete = {k for k, v in updates_dict.items() if v in ('',)}
            updates_dict = {
                k: v for k, v in updates_dict.items() if k not in keys_to_delete
            }
            update_delete_pairs.append((updates_dict, keys_to_delete))
    else:
        raise ValueError('No transactions specified to edit')
    for updates_dict, keys_to_delete in update_delete_pairs:
        txn_id_to_update = updates_dict.get('id', None)
        if txn_id_to_update is None:
            raise ValueError(
                f'Column named "id" must be present for updated to take place'
            )
        txn_id_to_update = int(txn_id_to_update)

        def update_fields(updates: dict = None, deletes: set = None):
            updates = updates or {}
            deletes = deletes or set()

            def transform(doc):
                for k, v in updates.items():
                    doc[k] = v
                for k in deletes:
                    if k in doc:
                        del doc[k]

            return transform

        transactions.update(
            update_fields(updates=updates_dict, deletes=keys_to_delete),
            doc_ids=[txn_id_to_update],
        )
        updated_ids.append(txn_id_to_update)

    return (
        Transaction.from_tinydb_dict(t) for t in transactions.get(doc_ids=updated_ids)
    )
