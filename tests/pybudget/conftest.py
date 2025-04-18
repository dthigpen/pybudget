from pybudget import utils, csv_tools
import csv
import json

import pytest


@pytest.fixture
def config_file(tmp_path):
    config_path = tmp_path / 'pyb_config.json'
    content = {
        'categories': [
            {
                'name': 'Groceries',
                'type': 'expense',
                'goal': '300',
            }
        ],
        'importers': [
            {
                'name': 'My Credit Card',
                'matcher': {
                    'filenameContains': 'card-brand',
                    'headers': [
                        'Transaction Date',
                        'ID',
                        'Short Description',
                        'Something Else',
                        'Amount',
                    ],
                },
                'dateColumn': 'Transaction Date',
                'descriptionColumn': 'Short Description',
                'amountColumn': 'Amount',
                'accountValue': 'My Institution',
                'flipSign': True,
                'dateFormat': '%Y-%m-%d',
            }
        ],
    }
    config_path.write_text(json.dumps(content, indent=2, sort_keys=True))
    yield config_path


@pytest.fixture
def dummy_transactions():
    yield [
        csv_tools.Transaction(
            date=utils.str_to_datetime(f'2025-01-0{i}'),
            description=f'Description {i}',
            amount=100.0 + i,
            account='My Institution',
        )
        for i in range(1, 9)
    ]


@pytest.fixture
def unimported_csv(tmp_path, dummy_transactions):
    csv_path = tmp_path / 'my-card-brand.csv'
    header = [
        'Transaction Date',
        'ID',
        'Short Description',
        'Something Else',
        'Amount',
    ]
    with open(csv_path, 'w') as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        for i, txn in enumerate(dummy_transactions):
            data = {
                'ID': f'Other ID {i}',
                'Transaction Date': utils.datetime_to_str(txn.date),
                'Something Else': f'data{i}',
                'Short Description': txn.description,
                'Amount': txn.amount,
            }
            writer.writerow(data)
    yield csv_path
