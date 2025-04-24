from pybudget import main, csv_tools
from pybudget.types import Transaction
from pathlib import Path


def get_transactions(data_path: Path) -> list[Transaction]:
    return list(
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


def test_import_transactions(
    tmp_path: Path,
    unimported_csv: Path,
    config_file: Path,
    dummy_transactions: list[Transaction],
):
    # destination file where imported transactions go
    data_path = tmp_path / 'pyb_transactions.csv'
    # run the import
    main.import_transactions(
        data_path, config_file, [unimported_csv], importer_name=None, dry_run=False
    )
    # check that all expected transactions are in the data file
    actual_transactions = get_transactions(data_path)

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
    # TODO test passing in importer_name directly


def test_list_transactions(tmp_path, config_file, imported_csv_transaction_data):
    # destination file where imported transactions go
    data_path = tmp_path / 'pyb_transactions.csv'
    output_path = tmp_path / 'output.csv'
    data_path.write_text(imported_csv_transaction_data)
    # Default options, aside from csv output
    # expect all transactions but sorted
    main.list_transactions(
        data_path,
        config_file,
        filters=None,
        only_uncategorized=False,
        output_format=None,
        output_path=output_path,
        suggest_categories=False,
    )
    expected_header, *expected_lines = imported_csv_transaction_data.strip().split('\n')
    expected_lines.sort()
    actual_header, *actual_lines = output_path.read_text().strip().split('\n')

    assert actual_header == expected_header
    assert actual_lines == expected_lines

    # only uncategorized keyword arg
    main.list_transactions(
        data_path,
        config_file,
        filters=None,
        only_uncategorized=True,
        output_format=None,
        output_path=output_path,
        suggest_categories=False,
    )
    expected_header, *expected_lines = imported_csv_transaction_data.strip().split('\n')
    expected_lines = list(filter(lambda x: 'Category' not in x, expected_lines))
    expected_lines.sort()
    actual_header, *actual_lines = output_path.read_text().strip().split('\n')

    assert actual_header == expected_header
    assert actual_lines == expected_lines

    # suggest categories, all transactions
    main.list_transactions(
        data_path,
        config_file,
        filters=None,
        only_uncategorized=False,
        output_format=None,
        output_path=output_path,
        suggest_categories=True,
    )
    expected_header, *expected_lines = imported_csv_transaction_data.strip().split('\n')
    expected_header += ',suggested_category'
    expected_lines = [l + ',' for l in expected_lines]
    expected_lines.sort()
    actual_header, *actual_lines = output_path.read_text().strip().split('\n')

    assert actual_header == expected_header
    assert actual_lines == expected_lines

    # suggest categories, uncategorized
    main.list_transactions(
        data_path,
        config_file,
        filters=None,
        only_uncategorized=True,
        output_format=None,
        output_path=output_path,
        suggest_categories=True,
    )
    expected_header, *expected_lines = imported_csv_transaction_data.strip().split('\n')
    expected_header += ',suggested_category'
    expected_lines = [l + ',' for l in expected_lines if 'Category' not in l]
    expected_lines.sort()
    actual_header, *actual_lines = output_path.read_text().strip().split('\n')

    assert actual_header == expected_header
    assert actual_lines == expected_lines

    # filter date
    main.list_transactions(
        data_path,
        config_file,
        filters=['date>=2025-01-06'],
        only_uncategorized=False,
        output_format=None,
        output_path=output_path,
        suggest_categories=False,
    )
    expected_header, *expected_lines = imported_csv_transaction_data.strip().split('\n')
    expected_lines = [
        l for l in expected_lines if any(d in l for d in ['01-06', '01-07', '01-08'])
    ]
    expected_lines.sort()
    actual_header, *actual_lines = output_path.read_text().strip().split('\n')

    assert actual_header == expected_header
    assert actual_lines == expected_lines

    # uncategorized filter
    main.list_transactions(
        data_path,
        config_file,
        filters=['category='],
        only_uncategorized=False,
        output_format=None,
        output_path=output_path,
        suggest_categories=False,
    )
    expected_header, *expected_lines = imported_csv_transaction_data.strip().split('\n')
    expected_lines = list(filter(lambda x: 'Category' not in x, expected_lines))
    expected_lines.sort()

    actual_header, *actual_lines = output_path.read_text().strip().split('\n')

    assert actual_header == expected_header
    assert actual_lines == expected_lines

    # filter only categorized
    main.list_transactions(
        data_path,
        config_file,
        filters=['category!='],
        only_uncategorized=False,
        output_format=None,
        output_path=output_path,
        suggest_categories=False,
    )
    expected_header, *expected_lines = imported_csv_transaction_data.strip().split('\n')
    expected_lines = list(filter(lambda x: 'Category' in x, expected_lines))
    expected_lines.sort()

    actual_header, *actual_lines = output_path.read_text().strip().split('\n')

    # filter by account
    main.list_transactions(
        data_path,
        config_file,
        filters=['account~Inst'],
        only_uncategorized=False,
        output_format=None,
        output_path=output_path,
        suggest_categories=False,
    )
    expected_header, *expected_lines = imported_csv_transaction_data.strip().split('\n')
    expected_lines.sort()

    actual_header, *actual_lines = output_path.read_text().strip().split('\n')

    # filter by amount
    main.list_transactions(
        data_path,
        config_file,
        filters=['amount>-103.00'],
        only_uncategorized=False,
        output_format=None,
        output_path=output_path,
        suggest_categories=False,
    )
    expected_header, *expected_lines = imported_csv_transaction_data.strip().split('\n')
    expected_lines = [l for l in expected_lines if any(l.startswith(i) for i in '123')]
    expected_lines.sort()

    actual_header, *actual_lines = output_path.read_text().strip().split('\n')
