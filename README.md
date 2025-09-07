# pybudget

**PyBudget** is a collection of small Python scripts for managing personal finances. It uses standard plain-text file formats like CSV, JSON, and INI.

Instead of a monolithic app, it follows the Unix philosophy: each script does one job and you chain them together to build a budgetting process that suites your needs.

## Purpose

- **Your data stays in plain CSVs** that you can open in any editor or spreadsheet.
- **The process is transparent:** every step is just a script that you can read, modify, and re-run
- **It's composable:** use only the parts you want, automate with shell pipelines, or wrap in your own python scripts.

## Budgeting Goals

- Track income & expenses clearly by category.
- Stay flexible: you can adjust categories and notes later without breaking the workflow.
- Reconcile monthly cash flow: see where extra money goes or where deficits are pulled from.
- Build and monitor funds (emergency, travel, etc.) with balances and goals.
- Generate monthly reports in both CSV and TXT.

## Non-Goals

- Double-ledger accounting, as seen in tools like hledger or beancount are very powerful but can also be very complicated and tedious. I find that this level of complexity can discourage long term usage.

## Example Workflow 

Coming Soon

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
