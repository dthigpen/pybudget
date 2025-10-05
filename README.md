# pybudget

**pybudget** is a lightweight, Unix-inspired budgeting toolkit written in Python.
It helps you normalize, update, and report on financial transactions while staying transparent, flexible, and scriptable.

Unlike most budgeting apps, pybudget avoids hidden databases or complicated GUIs.
It works directly on CSV/JSON files, making it easy to audit, customize, and fit into your own workflows.

Here’s a minimal example flow:

```bash
# 1. Drop you bank and credit card transaction CSVs in a folder. e.g. bank-txns
# 2. Normalize raw bank CSVs into a consistent format
# 3. Split normalized transactions into month files
pybudget normalize bank-txns/*.csv --importers importers/*.ini \
| pybudget split --by month -o normalized-txns/

# 4. Apply updates via changeset files: categories, splitting, add new, etc
# 5. Split back into monthly
pybudget apply normalized-txn/*.csv txn-updates/*.{csv, json} \
| pybudget split --by month -o final-txns/

# 6. Run a budget report against your currenr budget file
pybudget report --budget budgets/2025-05.json --transactions final/2025-05-transactions.csv -o reports/

# 7. Review report for spending deficits, patterns, etc
```

## Goals

- **Plain files first**: All inputs/outputs are CSV or JSON. Easy to edit by hand, version-control, or share.
- **Composability**: Each step does one job, and can be piped into the next.
- **Reproducibility**: Always get the same result when rerunning your budget commands.
- **Auditability**: You can always inspect intermediate files — no opaque state.
- **Portability**: Works anywhere Python runs, no database required.

## Non-Goals

- Not a personal finance tracker with bank syncs or live dashboards.
- Not a full bookkeeping system.
- Doesn’t try to enforce “one true workflow” — you assemble the steps you need.

## Installation

Clone and install directly from GitHub:

```
pip install git+https://github.com/dthigpen/pybudget.git
```

This provides a single command:

```
pybudget <subcommand> [options]
```

Subcommands include `normalize`, `split`, `categorize`, `apply`, and `report`.

## Subcommands

### `normalize`

Convert bank-specific CSVs into a consistent schema (date, description, amount, account, id, ...).
Requires one or more importer configs (.ini or .json) describing column mappings. See the next section for the importer format.

Example:

```bash
pybudget normalize bank_checking.csv --importers importers/bank.ini -o normalized.csv
```

### Importer Format

`normalize` requires one or more importer configs (in `.ini` or `.json` format) that describe how to read a given bank’s CSV export.
This allows pybudget to support many different institutions and file layouts.

#### Required keys

- `dateColumn`: The header name in the bank CSV that contains the transaction date.
- `descriptionColumn`: The header name containing the transaction description.
- `accountValue`: A fixed string used to identify which account these transactions belong to. (This becomes the account column in normalized output.)
- `amountColumn`: The header name containing the transaction amount.

#### Optional keys

- `flipSign`: (true/false, default: false) If the bank exports credits as negative numbers (or vice versa), enable this to flip the sign.
- `dateFormat`: A strftime-style format string describing how to parse the input date. Example: `%m/%d/%Y` for `05/12/2025`.
- `accountColumn`: The account name column. Typically the `accountValue` would be used but some institutions may include multiple accounts in one CSV.

Aditionally, matcher fields are used to auto-select this importer when multiple are available.
- `matchHeader`: A string of the exact transactions CSV header row that this importer should match against.
- `matchHeaderPattern`: A regex pattern for the transactions CSV header row to match against.
- `matchFileNamePattern`: A regex pattern for the transactions CSV file name to match against. Note, this cannot be used when reading transactions from `stdin`. Either use a different matcher type or specify the importer directly.

#### Example Importer Files

In INI format, just they `key = value` lines are required, the `[importer]` section can be omitted, and at will be added at the top of the file at runtime. For example, `my-card-importer.ini`:

```ini
# [importer] section header can be omitted for brevity
[importer]
dateColumn = Transaction Date
descriptionColumn = Description
amountColumn = Amount
accountValue = My Credit Card
flipSign = true
dateFormat = %m/%d/%Y
matchHeader = Transaction Date,Description,Amount
```

Or in JSON format, `my-card-importer.json`:

```json
{
  "dateColumn": "Transaction Date",
  "descriptionColumn": "Description",
  "amountColumn": "Amount",
  "accountValue": "My Credit Card",
  "flipSign": true,
  "dateFormat": "%m/%d/%Y",
  "matchHeader": "Transaction Date,Description,Amount",
}

```
These importers say:

- Read the "Transaction Date", "Description", and "Amount" columns from the input CSV for the normalized date, description, and amount normalized columns.
- Mark all transactions from this file as belonging to the "My Credit Card" account.
- Flip the sign on amounts (card exports credits as positive, but we want expenses negative).
- Parse dates in MM/DD/YYYY format.
- Auto-match if the header row matches "Transaction Date,Description,Amount".

With this setup, adding support for a new bank or account is as simple as dropping a new .ini file into your importers folder.

See the `pybudget init importer` command for a generating a starter importer file.

### `split`

Split a transaction file into multiple files by month (or other criteria).
Useful for keeping transactions organized by period.

Example:

```bash
pybudget split normalized.csv -o monthly/
```

### `categorize`

An interactive utility to help streamline the tedium of categorizing tasks by providing category suggestions and menu to navigate through transactions.

Example:
```bash
$ pybudget categorize monthly/2025-05-transactions.csv --categorized final-txns/*.csv --output updates/2025-05-updates.csv

Txn 1/98
Date: 2025-07-01
Amount: -30.50
Account: My Credit Card
Description: WM SUPERCENTER #1234 (id=a4e7ab18d8)
Category: 
  Suggestions:
    1. Groceries (1.00)
    2. Household (0.67)
[n]ext, [p]rev, [c]onfirm, [1-9]=pick, [e]dit, [q]uit > 1
```

This will iterate through transactions in the `2025-05-08-transactions.csv` file, prompting the user with suggested categories from the past categorized `final-txns/*.csv`. By the output file `2025-05-08-changes.csv` will be updated with prompt responses, not overwritten.

### `apply`

Apply changes to transactions. Updates can:
- **Update** existing transactions. E.g. add a category or update notes.
- **Add** new transactions. E.g. Cash spending.
- **Delete** transactions.
- **Split** a transaction into multiple. E.g. an Amazon Order into Groceries and Household.

Example:

```bash
pybudget apply monthly/2025-05.csv updates/2025-05-updates.csv -o final/2025-05.csv
```

#### Transaction Changeset Format

Changeset files are used by `apply` to tell what kind of modifications to make to the transaction set before outputing. Changeset files can be in a `.csv` or `.json` format. 

They have a `type` field that can be any of `add`, `update`, `delete`, `split`.

For example in CSV format, `changes/2025-05-changes.csv`:

```csv
type,id,date,description,amount,account,category,note
update,aa3fdae3f21,2025-08-01,GROCERY MART,33.49,My Credit Card, Groceries,Spent extra to make holiday dessert
```
In CSV format it might be considerably easier to edit these in a spreadsheet application to not mix up columns. Plain-text editing is better supported by JSON format. For example, `changes/2025-05-changes.json`:

```json
[
  {
    "type": "update",
    "category: ", "Groceries"
  }
]
```

For `update`, only the `id` and fields you want to change are required. However, you may want either include the description to remind you what the transaction is or automate creating these files.

### `report`

Generate budget reports from a budget definition (JSON or CSV) and a set of transactions.
Outputs text (default) or CSV for further processing.

**Note:** This feature and section are in progress.

Example:

```bash
pybudget report --budget budgets/2025-05.json --transactions final/2025-05.csv
```

## To Do

- Verify importer `dateFormat` functionality.
- Unit tests, unit test, unit tests.
- Add diagram to README showing workflow.
- Add full narrative workflow example, to show how a person would use this tool from start to finish.
- Expand on apply feature.
- Expand on report feature.
- Add output to import command to show summary of imported transactions.
- Improve reporting use case where initial balances are unknown. E.g. user wanting report on categorized transactions.
