# Quality Assurance for the Precinct Project (QAPP)

Original QA engine by sbaltz.  
Refactored and extended by Zayne (2025).

This repository contains a modular, PEP 8–compliant rewrite of the automated QA engine for the Precinct Project. It performs checks for precinct-level election results datasets, flagging potential issues in data structure, formatting, and vote totals.

## Overview

QAPP validates and summarizes precinct-level election results data
using a sequence of reproducible, transparent checks:

1. Structural QA – verifies required columns, detects duplicates and empties.  
2. Field QA – flags zero-vote races, empty candidate names, and malformed values.  
3. Numerical QA – tests for negative or non-numeric vote totals.  
4. Distributional QA [UNDER DEVELOPMENT] – identifies states or precincts with implausible vote
   distributions using median absolute deviation (MAD) outlier detection.  
5. FIPS and State Code Validation – verifies state and county identifiers against
   canonical reference tables.  
6. Reporting – produces clear `.txt`, `.csv`, and `.xlsx` summaries of all results.

## Directory Structure

```
qa_engine/
│
├── qa_core/
│   ├── runner.py         # main orchestrator
│   ├── checks.py         # column + field checks
│   ├── stats_utils.py    # quantitative and distributional checks
│   ├── io_utils.py       # data loading utilities
│   ├── report.py         # human-readable report output
│   ├── check_fips.py     # validates FIPS and state codes
│   ├── config.py         # global constants and thresholds
│   └── __init__.py
│
├── qa_core/help_files/   # reference tables for FIPS and state codes
│   ├── merge_on_statecodes.csv
│   └── county-fips-codes.csv
│
├── output/
│   └── qa/               # auto-generated QA results
└── README.md
```

## Installation

# Install dependencies
pip install -r requirements.txt
```

Requirements: Python ≥ 3.8, pandas, numpy

## Usage

Run the engine directly on a precinct-level dataset (CSV or TSV):

```bash
python -m qa_core.runner path/to/STATE_precincts.csv
```

Example output structure:

```
output/qa/STATE_precincts/
├── QA_Report_IL24.txt
├── QA_Report_IL24.csv
├── QA_Report_IL24.xlsx
└── qa_run.log
```

## Example Checks Performed

| Category | Check | Description |
|-----------|--------|-------------|
| Columns | Missing/extra | Verifies all required fields exist |
| Fields | Duplicates | Detects duplicate (state, county, precinct) rows |
|  | Zero-vote rows | Flags precincts with all-zero vote counts |
| Numerical | Negative/non-numeric votes | Identifies invalid totals |
| Distributional | Outlier detection | Uses MAD to flag abnormal vote totals within states |
| FIPS / State Codes | State and county validation | Verifies `state_fips`, `state_po`, `state_name`, `state_ic`, `census_fips`, and `county_fips` against canonical reference files |

## Report Format

### Text Summary (.txt)

Readable sectioned output, with each QA category reported in sequence:

```
================================================================================
MEDSL PRECINCT QA REPORT
Rows: 52,738  Columns: 12
================================================================================

================================================================================
COLUMNS
================================================================================
missing_columns          : []
extra_columns            : ['notes']
column_count             : 12

================================================================================
FIELDS
================================================================================
duplicate_precincts      : 3
zero_vote_rows           : 42
empty_candidates         : 7

================================================================================
FIPS VALIDATION
================================================================================
Invalid state_fips: []
Invalid county_fips: []
```

### CSV Summary (.csv)
Flat key-value summary for spreadsheet filtering:

| section | check | value |
|----------|--------|-------|
| columns | missing_columns | [] |
| fields | duplicate_precincts | 3 |
| numerical | negative_votes | 0 |
| fips_checks | invalid_state_fields | 0 |
| fips_checks | invalid_county_fips | 0 |

### Excel Report (.xlsx)
The Excel workbook includes:
- `QA_Summary`: all check results in tabular form  
- `Missingness`: percent and count of missing values per column  
- `Statewide_Totals`: aggregated vote totals for statewide offices  
- `FIPS_Validation`: list of invalid or mismatched FIPS/state code entries  

## FIPS and State Code Validation (added in v2.5)

The QA engine cross-verifies **state and county codes** against canonical reference files located in `qa_core/help_files/`:

| Field | Description | Source |
|--------|--------------|--------|
| `state_fips` | 2-digit state code | merge_on_statecodes.csv |
| `state_po` | 2-letter postal abbreviation | merge_on_statecodes.csv |
| `state_name` | Full state name | merge_on_statecodes.csv |
| `state_ic` | Internal code used in election datasets | merge_on_statecodes.csv |
| `census_fips` | Census Bureau state code | merge_on_statecodes.csv |
| `county_fips` | 5-digit county code (including state prefix) | county-fips-codes.csv |

The validation module checks that:

* All values appear in the appropriate reference file.  
* Each `county_fips` matches its `state_fips` prefix.  
* All state-level fields (`state_fips`, `state_po`, `state_name`, `state_ic`, `census_fips`) are internally consistent with one another.

Results appear in a `[ FIPS Validation ]` section of the text report and a `FIPS_Validation` sheet in the Excel output.

## Extending QAPP

New checks can be added easily by defining a function in
`qa_core/checks.py` or `qa_core/stats_utils.py` with signature:

```python
def new_check(df: pd.DataFrame) -> dict[str, Any]:
    ...
    return {"description": metric}
```

Then register it in `runner.py` by adding to the call sequence.

## Configuration

Thresholds and constants are set in `qa_core/config.py`:

| Variable | Description | Default |
|-----------|-------------|----------|
| REQUIRED_COLUMNS | Columns expected in all datasets | ['state','county','precinct','office','party','candidate','votes'] |
| OUTLIER_THRESHOLD | MAD outlier threshold | 3.5 |
| MISSING_TOKENS | Values treated as NA | ["", "NA", "N/A", "NULL", "nan"] |

## Contributing

1. Fork this repository.  
2. Create a feature branch (`git checkout -b feature/add-check`).  
3. Follow PEP 8 and include docstrings for all new functions.  
4. Submit a pull request with clear examples or test data.

## License

Released under the MIT License.  
© 2025 MIT Election Data + Science Lab.
