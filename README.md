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

Subcommands include normalize, split, merge, and report.

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

```bash
Here’s a minimal flow to get started:

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
Requires one or more importer configs (.ini) describing column mappings.

Example:

```bash
pybudget normalize bank.csv --importers importers/bank.ini -o normalized.csv
```

---

### `split`

Split a transaction file into multiple files by month (or other criteria).
Useful for keeping transactions organized by period.

Example:

```bash
pybudget split normalized.csv -o monthly/
```

### `merge`

- **Apply** updates to a base transaction file. Updates can:
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
