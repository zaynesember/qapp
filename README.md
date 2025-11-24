# Quality Assurance for the Precinct Project (QAPP)

Original QA engine by sbaltz. Refactored and extended by Zayne (2025).

This repository contains a modular, PEP‑8–compliant QA engine for precinct‑level
election results. It runs a sequence of structural, field, numeric, and FIPS
validation checks and emits human‑readable text/csv summaries plus a single
Excel workbook per run.

## Quick start

Create a virtual environment, install dependencies, and run a sample file:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python qapp.py tests/nh_test.csv
```

Or run the module directly:

```bash
python -m qa_core.runner path/to/STATE_file.csv
```

## What it does (high level)

- Structural checks: validates required columns and reports missing/extra columns.
- Field checks: detects duplicate rows, duplicate precinct identifiers, empty
   candidate names, zero or negative vote counts.
- Numerical checks: coerces `votes` to numeric and reports non-numeric or
   implausible values (MAD outlier detection in `stats_utils`).
- FIPS & state validation: cross-checks `state_*` and `county_fips` values
   against canonical reference CSVs (in `help_files/`).
- Reporting: produces a single Excel workbook (`report_<inputstem>.xlsx`) and
   flat CSV/text summaries. Unique-values are written into the Excel report
   on the `Unique` sheet (the previous per-column `unique_values/` text
   exports are deprecated).

## Checks

Below are the checks that `qapp` produces in its QA report, with a brief explanation of what each check represents. Keep this list updated whenever new checks are added.

- `columns`: Validates the presence and count of required columns in the dataset (compares to `qa_core.config.REQUIRED_COLUMNS`).
- `fields`: High-level per-field checks that summarize issues for individual columns (missing required values, invalid categories, etc.). Each field entry contains `issues`, optional `issue_values`, and `issue_row_numbers`.
- `field_formats`: Checks that column values match expected enumerated formats or allowed value lists (e.g., `party_simplified`, `mode`).
- `field_regex_checks`: Regex-based validations for fields where pattern matching is helpful (implemented in `qa_core/field_checks.py`). Example checks include `votes`, `candidate`, and `magnitude` patterns. Note: the `Field Regex Checks` sheet only lists checks that have one or more issues to improve readability.

   New text-format checks added (2025): checks for extraneous leading/trailing whitespace, embedded newlines, multiple consecutive spaces, accented/Latin-extended letters, nonstandard symbols (outside a conservative ASCII punctuation set), and squished-initials in `candidate` values (e.g., `J.D.Vance`). These appear under per-column `*_format` checks and the `field_regex_checks` section when they have issues.
- `missingness`: Per-column missingness summary. For each column returns `missing_count`, `percent_empty`, and `alt_missing_values` discovered during scanning. This data is written to a separate `Missingness` sheet in the Excel report.
- `duplicates`: Identifies duplicated or conflicting rows (exact duplicates or rows that conflict on key identifiers). The detailed DataFrame lists the duplicated rows.
- `zero_vote_precincts`: Groups by precinct/office (using available grouping columns such as `county_fips`, `jurisdiction_fips`, `precinct`, `office`, `district`) and reports precinct-office groups whose total `votes` sums to zero. Returned as a DataFrame and summarized in `fields` as `zero_vote_precinct_groups`.
- `state_codes` / `check_fips`: Validates `state_po`, `state_fips`, and related geographic codes against `help_files/` reference tables. Issues indicate mismatched or unrecognized state/county codes.
- `numerical` / `stats_utils` checks: Numeric sanity checks (outlier detection, MAD-based checks) applied to numeric fields such as `votes` or `magnitude`.
- `distribution`: Distributional sanity checks (e.g., vote share distributions that look anomalous across groups).
- `statewide_totals`: Aggregated vote totals across the dataset (excluding write-ins when applicable). Used for sanity checks of precinct-to-state aggregations and reported in the `Vote Aggregation` sheet.

- `duplicates_summary`: A compact summary (counts) of duplicate/conflict types found; complements the `duplicates` DataFrame which contains full row details.
- `zero_vote_precinct_groups`: A short `fields`-level summary key that records the number of precinct-office groups whose aggregated `votes` sum to zero and example group identifiers.
- `detected_state`: Metadata about the detected state for the input file (derived from the filename and/or content). Includes `state_po`, `state_name`, `state_fips`, etc.
- `fips_checks` (aka `state_codes` in reports): Lower‑level FIPS/state validation outputs produced by `qa_core/check_fips.py`; includes specific mismatches and unrecognized codes.
- `dataset_info`: Small metadata dict containing `rows`, `columns`, `unique_counties`, and `unique_jurisdictions` used to populate the QA banner.
- `magnitude_offices_map`: A detail DataFrame mapping observed magnitude values to offices (useful when magnitude is inconsistent across rows for the same office).
- `offices_multiple_magnitudes`: A DataFrame listing offices that appear with more than one `magnitude` value (usually a data-quality signal).
- `stage_invalid_rows`: A DataFrame of rows whose `stage` value did not match expected/recognized stages (helps find malformed stage entries).

Notes:
- Many checks return serializable dicts (scalars, lists, DataFrames) so that `qa_core.report.write_excel_report` can turn them into human-readable Excel worksheets. When adding a new check, return either a small dict with keys `issues`, `issue_values`, and/or `issue_row_numbers`, or a DataFrame for larger detail outputs.
- For regex- and field-specific checks add implementations in `qa_core/field_checks.py` and register their outputs in `qa_core/runner.py` so they appear in `all_results` and the final report.
- Keep the `README` list updated: when you add a check, append its snake_case name and a one-line definition here so the QA summary remains discoverable.

## Repository layout (relevant files)

- `qapp.py` — thin CLI wrapper that calls `qa_core.runner.run_qa`.
- `qa_core/runner.py` — main orchestrator: load → checks → summarize → write
   a single Excel workbook.
- `qa_core/checks.py` — structural and field checks + duplicate detection.
- `qa_core/stats_utils.py` — numeric and distributional checks (MAD‑based).
- `qa_core/io_utils.py` — data loading utilities (CSV/TSV normalization).
-- `qa_core/data_summary.py` — missingness summary and `compute_statewide_totals`.
   Unique-values exports are now generated in the runner and written to the
   `Unique` sheet in the Excel report; the old `export_unique_values` helper
   and per-column txt exports are deprecated and have been removed.
- `qa_core/report.py` — serializes `all_results` into text/csv and the Excel
   workbook.
- `qa_core/config.py` — canonical `REQUIRED_COLUMNS`, thresholds, and
   `QA_OUTPUT_DIR`.
- `help_files/` — canonical `merge_on_statecodes.csv` and
   `county-fips-codes.csv` used for state/county validation (top-level
   directory). If missing, FIPS checks are skipped.

## Important conventions and integration points

- Input file state detection: the runner uses the input filename stem and
   takes the token before the first underscore as the state code (uppercased),
   e.g., `NH_2024_precincts.csv` → state `NH`. See
   `runner.run_qa` for the exact behavior.
- Output layout: run outputs go to `output/<STATE>/` (determined by
   `config.QA_OUTPUT_DIR`). Files produced include `qa_run.log`,
   `report_<inputstem>.xlsx`, and a `unique_values/` folder with per‑column
   exports.
- `all_results` shape: `runner.py` collects check outputs into an
   `all_results` dict which `report.write_excel_report` expects to serialize.
   Keep outputs as scalars, dicts, DataFrames, or lists to maintain
   compatibility with report generation.

## How to add a new check (concrete steps)

1. Implement the check in `qa_core/checks.py` (for structural/field checks)
    or `qa_core/stats_utils.py` (for numeric/distributional checks). Signature:

```python
def new_check(df: pd.DataFrame) -> dict[str, Any]:
      # return a small dict, DataFrame, or list that can be added to all_results
      return {"my_check": {...}}
```

2. Register the check in `qa_core/runner.py` by assigning to `all_results`, e.g.

```py
all_results['my_check'] = checks.new_check(df)
```

3. Run locally against `tests/nh_test.csv` and inspect `output/NH/` to confirm
    the check appears in the Excel workbook and text summary.

## Logging & diagnostics

- Logging: `runner._setup_logging` writes `qa_run.log` to the state output
   folder and also streams logs to the console.
- Load failures: `io_utils.load_data` exceptions are logged and the run
   returns early — examine `qa_run.log` for stack traces.

## Configuration

Edit `qa_core/config.py` for repo‑wide constants:

- `REQUIRED_COLUMNS`: canonical column set used by column checks.
- `OUTLIER_THRESHOLD`: MAD threshold for distributional checks.
- `QA_OUTPUT_DIR`: top-level output folder (default `output/`).
 - `AGGREGATE_MARKERS`: list of tokens that identify rows which are totals,
    statistical adjustments, or other non‑candidate rows that should be
    excluded from duplicate and mismatch detection. These markers typically
    appear in the `candidate` column (e.g., `"COUNTY TOTALS"`,
    `"MACHINE COUNT"`, `"OVERVOTES"`, `"UNDERVOTES"`, `"VOID"`,
    `"BLANK"`) and are matched case-insensitively. Edit `qa_core/config.py`
    to customize this list for your datasets.

## Samples & tests

- Sample CSVs are in `tests/` (e.g., `nh_test.csv`, `nj_test.csv`). Use them
   for quick verification; there is no formal unit test harness by default.

## Contributing notes

- Make minimal, localized changes — prefer adding checks and registering them
   in `runner.py` rather than modifying the orchestration flow.
- Follow PEP‑8 and keep outputs serializable for reporting.

---
