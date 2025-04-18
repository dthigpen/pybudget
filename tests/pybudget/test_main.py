from pybudget import main, csv_tools
from pybudget.types import Transaction
import csv
import json
from pathlib import Path


def test_import_transactions(
    tmp_path: Path,
    unimported_csv: Path,
    config_file: Path,
    dummy_transactions: list[Transaction],
):
    # destination file where imported transactions go
    data_path = tmp_path / 'pyb_transactions.csv'
    # run the import
    main.import_transactions(data_path, config_file, [unimported_csv])
    # check that all expected transactions are in the data file
    actual_transactions = list(
        csv_tools.read_transactions_from_csv(
            data_path,
            column_names={
                'id': 'id',
                'date': 'date',
                'description': 'description',
                'amount': 'amount',
                'account': 'account',
                'category': 'category',
            },
        )
    )
    # have to remove the ids since the dummy transactions would not have them
    ids = set()
    for t in actual_transactions:
        assert bool(t.id) and t.id not in ids
        ids.add(t.id)
        t.id = None
    # flip signs since the importer should have fipped them too
    for t in dummy_transactions:
        t.amount *= -1
    assert actual_transactions == dummy_transactions
