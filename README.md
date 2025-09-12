# pybudget

**pybudget** is a lightweight, Unix-inspired budgeting toolkit written in Python.
It helps you normalize, merge, and report on financial transactions while staying transparent, flexible, and scriptable.

Unlike most budgeting apps, pybudget avoids hidden databases or complicated GUIs.
It works directly on CSV/JSON files, making it easy to audit, customize, and fit into your own workflows.


## Installation

Clone and install directly from GitHub:

```
pip install git+https://github.com/dthigpen/pybudget.git
```

This provides a single command:

```
pybudget <subcommand> [options]
```

Subcommands include `normalize`, `split`, `apply`, and `report`.

## Goals

- **Plain files first**: All inputs/outputs are CSV or JSON. Easy to edit by hand, version-control, or share.
- **Composability**: Each step does one job, and can be piped into the next.
- **Auditability**: You can always inspect intermediate files — no opaque state.
- **Portability**: Works anywhere Python runs, no database required.

## Non-Goals

- Not a personal finance tracker with bank syncs or live dashboards.
- Not a full bookkeeping system.
- Doesn’t try to enforce “one true workflow” — you assemble the steps you need.

## Example Workflow

Here’s a minimal example flow:

```bash

# Normalize raw bank CSVs into a consistent format
pybudget normalize bank-transactions/*.csv --importers importers/*.ini \
    -o normalized-transactions/all.csv

# Split normalized transactions into month files
pybudget split normalized-transactions/all.csv -o monthly/

# Apply manual categorization/notes (via update files), then merge
pybudget merge monthly/2025-05-transactions.csv transaction-updates/2025-05-updates.csv \
    -o final/2025-05.csv

# Run a budget report against a budget file
pybudget report --budget budgets/2025-05.json --transactions final/2025-05.csv
```

## Subcommands

### `normalize`

Convert bank-specific CSVs into a consistent schema (date, description, amount, account, id, ...).
Requires one or more importer configs (.ini) describing column mappings. See the next section for the importer format.

Example:

```bash
pybudget normalize bank.csv --importers importers/bank.ini -o normalized.csv
```

### Importer Format

`normalize` requires one or more importer configs (in `.ini` format) that describe how to read a given bank’s CSV export.
This allows pybudget to support many different institutions and file layouts.

Each importer file has a `[importer]` section with the following keys:

#### Required keys

- `dateColumn`: The header name in the bank CSV that contains the transaction date.
- `descriptionColumn`: The header name containing the transaction description.
- `accountValue`: A fixed string used to identify which account these transactions belong to. (This becomes the account column in normalized output.)
- `amountColumn`: The header name containing the transaction amount.

#### Optional keys

- `flipSign`: (true/false, default: false) If the bank exports credits as negative numbers (or vice versa), enable this to flip the sign.
- `dateFormat`: A strftime-style format string describing how to parse the input date. Example: `%m/%d/%Y` for `05/12/2025`.

Aditionally, matcher fields are used to auto-select this importer when multiple are available.
- `matchHeader`: A string of the exact transactions CSV header row that this importer should match against.
- `matchHeaderPattern`: A regex pattern for the transactions CSV header row to match against.
- `matchFileNamePattern`: A regex pattern for the transactions CSV file name to match against. Note, this cannot be used when reading transactions from `stdin`. Either use a different matcher type or specify the importer directly.

#### Example Importer File

```ini
[importer]
dateColumn = Transaction Date
descriptionColumn = Description
amountColumn = Amount
accountValue = My Credit Card
flipSign = true
dateFormat = %m/%d/%Y
matchHeader = Transaction Date,Description,Amount
```
This importer says:

- Use the Transaction Date column for the normalized date.
- Use Description as the normalized description.
- Use Amount as the normalized amount.
- Mark all transactions from this file as belonging to the My Credit Card account.
- Flip the sign on amounts (bank exports credits as positive, but we want expenses negative).
- Parse dates in MM/DD/YYYY format.
- Auto-match if the header row matches "Transaction Date,Description,Amount".

With this setup, adding support for a new bank or account is as simple as dropping a new .ini file into your importers folder.


### `split`

Split a transaction file into multiple files by month (or other criteria).
Useful for keeping transactions organized by period.

Example:

```bash
pybudget split normalized.csv -o monthly/
```

### `apply`

Apply updates to a base transaction file. Updates can:
- **Update** existing rows by id.
- **Add** new rows (no id).
- **Delete** rows (id only, other fields empty).

Example:

```bash
pybudget merge monthly/2025-05.csv updates/2025-05-updates.csv -o final/2025-05.csv
```

### `report`

Generate budget reports from a budget definition (JSON or CSV) and a set of transactions.
Outputs text (default) or CSV for further processing.

Example:

```bash
pybudget report --budget budgets/2025-05.json --transactions final/2025-05.csv
```
