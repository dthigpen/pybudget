# pybudget

A command line application to track expenses and manage a budget.

Example usage:
```
$ pybudget import transactions my-card-jan-2025.csv
| ID | Date         | Description        | Amount  |   Account   | Category |
|----|--------------|--------------------|---------|-------------|----------|
| 92 | 2025-01-02   | JOB COMPANY        |  811.95 | WF Checking |          |
| 93 | 2025-01-03   | CITY WATER UTILITY |  -34.11 | WF Checking |          |
| 94 | 2025-01-07   | AMAZON MKPLC       |  -28.34 | Chase Card  |          |
| 95 | 2025-01-17   | BEST BUY           | -100.45 | Chase Card  |          |
| 96 | 2025-01-19   | MUSEUM OF N&S      |  -12.81 | Chase Card  |          |
| 97 | 2025-01-19   | AMAZON.COM*ZQWRH78 |  -78.75 | Chase Card  |          |
Imported 6 Transactions

$ pybudget list transactions --filter 'description~AMAZ'
| ID | Date         | Description        | Amount  |   Account   | Category |
|----|--------------|--------------------|---------|-------------|----------|
| 94 | 2025-01-07   | AMAZON MKPLC       |  -28.34 | Chase Card  |          |
| 97 | 2025-01-19   | AMAZON.COM*ZQWRH78 |  -78.75 | Chase Card  |          |

$ pybudget report --period 2024-07
...
```

## Installation

```bash
pip install git+ssh://git@github.com:dthigpen/pybudget.git
```

## Usage

1. Setup a folder where you would like to store your budget and transaction data, and navigate to it.
   ```
   $ mkdir ~/budget && cd ~/budget
   ```
2. Download a CSV of transactions from your bank. E.g. `my-bank-export-2025-02.csv`
3. In your budget directory, run `pybudget init`. You should see a file called `pybudget.json` with some of its contents looking like:
   ```json
   {
       "importers": [
           {
               "name": "My Bank Checking",
               "descriptionColumn": "Description",
               "amountColumn": "Amount",
               "accountValue": "My Bank Checking",
               "dateColumn": "Date",
               "dateFormat": "%Y-%m-%d",
           }
       ]
   }
   ```
4. Check the columns in your bank's CSV and make any changes to the column names or date format that pybudget will look for.
5. Import the transactions.
```
$ pybudget import transactions --importer 'My Bank Checking' my-bank-export-2025-02.csv
```

## Features

For now, there is zero interactivity with pybudget. No prompts or inputs, keeping it simple, deterministic, and easy to use in personal automation. See the below features for command line usage.

### Import Transactions

Import transactions with a CSV export from your financial institution. Configure the mapping of the colmumn names once in your `pyb_config.json` like in the example below. The `descriptionColumn`, `amountColumn`, other fields ending in `Column` should have values that match what is in your bank's CSV output. The `accountValue` and other fields ending in `Value` will use the given value for all transactions. This is useful for the Account where this is usually not encoded as a column. The `dateFormat` is the format of the date in the CSV file. `"%Y-%m-%d"` will accept something like `2025-04-28`.
```json
{
    "importers": [
        {
            "name": "My Bank Checking",
            "descriptionColumn": "Description",
            "amountColumn": "Amount",
            "accountValue": "My Bank Checking",
            "dateColumn": "Date",
            "dateFormat": "%Y-%m-%d",
        }
    ]
}
 ```

Optionally, add criteria for `pybudget` to automatically match this importer to the CSV its reading. You can use one or more criteria like in the example below. The `filenameContains` criteria will match if the CSV file has this substring in the file name. The `headers` criteria will match if the CSV file contains exactly these headers in the first line. When all listed criteria in your importer match, `pybudget` will use that importer. You can always use `--importer` to override this behavior.
```json
{
    "importers": [
        {
            "name": "My Bank Checking",
            "matcher": {
              "filenameContains": "sofi-card",
              "headers": ["Transaction Date","Post Date","Description","Category","Type","Amount"]
            }
            ...
        }
    ]
}
```
Finally import the transactions with:
```
$ pybudget import transactions my-card-jan-2025.csv
```

Note, you can also pass `--dry-run` to see what it would look like to import the transactions without actually modifying anything.

### List Transactions

List recorded transactions and optionally filter by some criteria.
```
$ pybudget list transactions --filter description~AMAZ
...

$ pybudget list transactions --filter description~JOB --filter 'amount>850'
...
```

Output to a file in CSV format by passing `--output-file <path>`. This can be useful if you have multiple transactions to modify. See the edit command for more details.
```
$ pybudget list transactions --filter description~AMAZ --output-file out.csv
...
```
### Edit Transactions

Edit one off transactions by passing in the `id` of the transactions and an argument for the new values
```
$ pybudget edit txn --id 94 --category Groceries
```

Or to perform a batch edit of multiple transactions using an input file. This is typically the output from something like `list transactions --output-file out.csv` that is then edited as desired.

```
$ pybudget edit txn --from out.csv
```

### New Transactions (Planned)

### Split Transactions (Planned)

### Generate reports (Planned)

