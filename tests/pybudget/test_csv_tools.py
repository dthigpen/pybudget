from pybudget import csv_tools, utils
import csv


def test_large_csv(tmp_path):
    # test creating a new csv
    fieldnames = ['id', 'date', 'description', 'amount', 'account', 'category']
    csv_path = tmp_path / 'data.csv'
    csv_tools.init_large_csv(csv_path, fieldnames)
    expected_header_text = 'id,date,description,amount,account,category\n'
    # check creation and header
    assert csv_path.is_file()
    assert csv_path.read_text() == expected_header_text
    # check first row
    large_csv = csv_tools.LargeCSV(csv_path)
    large_csv.append({'id': '123', 'description': 'first row'})
    assert csv_path.read_text() == expected_header_text + '123,,first row,,,\n'

    # perform more operations
    large_csv.append({'id': '456', 'description': 'another row'})
    large_csv.append({'id': '789', 'description': 'another row'})
    large_csv.batch_update({'456': {'description': 'updated'}})
    large_csv.batch_replace({'123': {}})

    # read back and check lines
    # trim header line and new line
    empty_transaction = {
        'description': '',
        'account': '',
        'amount': '',
        'category': '',
        'date': '',
    }
    expected_dicts = [
        {**empty_transaction, 'id': '123'},
        {**empty_transaction, 'id': '456', 'description': 'updated'},
        {**empty_transaction, 'id': '789', 'description': 'another row'},
    ]
    expected_lines = [
        '123,,,,,',
        '456,,updated,,,',
        '789,,another row,,,',
    ]
    actual_lines = csv_path.read_text().strip().split('\n')[1:]
    # check that the lines, dicts, and read match

    assert (
        list(large_csv.read_many(*(d['id'] for d in expected_dicts))) == expected_dicts
    )
    for i, d in enumerate(expected_dicts):
        assert large_csv.read_one(d['id']) == d
        assert actual_lines[i] == expected_lines[i]

    large_csv.batch_delete(['456'])
    assert large_csv.read_one('456') is None

    large_csv.append({**empty_transaction, 'description': 'append with no id'})
    # next id should be 789 + 1
    large_csv.read_one('790') == {
        **empty_transaction,
        'description': 'append with no id',
    }

    # test rebuilding the index when it does not exist upon initial load
    # save off original index then delete the file
    index_content = large_csv.index_path.read_text()
    large_csv.index_path.unlink()
    assert not large_csv.index_path.exists()
    # reload the large csv so that index gets rebuilt
    large_csv = csv_tools.LargeCSV(csv_path, fieldnames=fieldnames)
    assert large_csv.index_path.exists()
    # check that it got rebuilt the same
    rebuilt_index_content = large_csv.index_path.read_text()
    index_content == rebuilt_index_content


def test_transactions_csv(tmp_path):
    csv_path = tmp_path / 'data.csv'
    transactions_csv = csv_tools.TransactionsCSV(csv_path)
    print('DEBUG actual headers', csv_path.read_text().split('\n')[0])

    transactions = [
        csv_tools.Transaction(
            id=str(i),
            date=utils.str_to_datetime(f'2025-01-0{i}'),
            description=f'desc_{i}',
            amount=12.34 + i,
            account=f'Account {i}',
            category=f'category {i}',
        )
        for i in range(1, 10)
    ]
    # add
    transactions_csv.add(*transactions)
    # read_many
    all_txns = list(transactions_csv.read_many())
    assert all_txns == transactions
    # read_one
    one_txn = transactions_csv.read_one(transactions[2].id)
    assert one_txn == transactions[2]

    # replace and update are basically the same at the txn level but call them anyway
    one_txn.category = ''
    transactions_csv.replace(one_txn)
    new_one_txn = transactions_csv.read_one(one_txn.id)
    one_txn == new_one_txn

    one_txn.category = 'foo'
    transactions_csv.update(one_txn)
    new_one_txn = transactions_csv.read_one(one_txn.id)
    one_txn == new_one_txn


def test_read_transactions_from_csv(tmp_path):
    # first create a fake transactions csv to read transactions from
    # e.g. one that one would be imported from a bank
    csv_path = tmp_path / 'transactions-to-import.csv'
    with open(csv_path, 'w') as f:
        # Intentionally use different columns
        writer = csv.DictWriter(
            f,
            fieldnames=[
                'Transaction Date',
                'ID',
                'Short Description',
                'Something Else',
                'Amount',
            ],
        )
        writer.writeheader()
        expected_transactions = []
        for i in range(1, 9):
            expected_transaction = csv_tools.Transaction(
                date=utils.str_to_datetime(f'2025-01-0{i}'),
                description=f'Description {i}',
                amount=100.0 + i,
                account='My Institution',
            )
            expected_transactions.append(expected_transaction)
            data = {
                'ID': f'Other ID {i}',
                'Transaction Date': utils.datetime_to_str(expected_transaction.date),
                'Something Else': f'data{i}',
                'Short Description': expected_transaction.description,
                'Amount': expected_transaction.amount,
            }
            writer.writerow(data)
    actual_transactions = list(
        csv_tools.read_transactions_from_csv(
            csv_path,
            column_names={
                'date': 'Transaction Date',
                'description': 'Short Description',
                'amount': 'Amount',
            },
            default_values={'account': 'My Institution'},
        )
    )
    assert actual_transactions == expected_transactions
