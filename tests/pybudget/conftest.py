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


@pytest.fixture
def imported_csv_transaction_data():
    # intentionally out of order
    return """id,date,description,amount,account,category
1,2025-01-01,Description 1,-101.00,My Institution,
2,2025-01-02,Description 2,-102.00,My Institution,
3,2025-01-03,Description 3,-103.00,My Institution,
6,2025-01-06,Description 6,-106.00,My Institution,Category2
7,2025-01-07,Description 7,-107.00,My Institution,
8,2025-01-08,Description 8,-108.00,My Institution,
4,2025-01-04,Description 4,-104.00,My Institution,Category1
5,2025-01-05,Description 5,-105.00,My Institution,
"""
