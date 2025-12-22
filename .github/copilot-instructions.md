<!-- Copilot / AI agent instructions for the QAPP repository -->
# QAPP — AI Agent Guidance

MEDSL's precinct-level QA engine. Validates election result CSVs, runs structural/field/numeric checks, and outputs a single Excel workbook per run.

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python qapp.py tests/nh_test.csv
# Inspect output/NH/report_nh_test.xlsx
```

## Architecture & Data Flow

**Pipeline:** `qapp.py` → `runner.run_qa()` → load CSV → run checks → aggregate `all_results` → `report.write_excel_report()` → Excel workbook

**Key modules:**
- [qa_core/runner.py](qa_core/runner.py) — orchestrator (load → checks → report)
- [qa_core/checks.py](qa_core/checks.py) — structural/field checks + duplicate detection
- [qa_core/field_checks.py](qa_core/field_checks.py) — regex-based validations (whitespace, accents, symbols)
- [qa_core/check_field_formats.py](qa_core/check_field_formats.py) — enumerated value checks (party, mode, stage)
- [qa_core/check_fips.py](qa_core/check_fips.py) — state/county FIPS validation against `help_files/`
- [qa_core/stats_utils.py](qa_core/stats_utils.py) — numeric checks (MAD outlier detection, vote distributions)
- [qa_core/data_summary.py](qa_core/data_summary.py) — missingness summary & statewide vote totals
- [qa_core/office_checks.py](qa_core/office_checks.py) — office name normalization/validation
- [qa_core/report.py](qa_core/report.py) — Excel generation with formatting/highlighting
- [qa_core/config.py](qa_core/config.py) — constants (`REQUIRED_COLUMNS`, thresholds, `AGGREGATE_MARKERS`)

**Critical conventions:**
- **State detection:** Filename stem before first `_` (e.g., `NH_2024.csv` → state `NH`)
- **Output path:** `output/<STATE>/report_<inputstem>.xlsx` + `qa_run.log`
- **`all_results` contract:** Each check returns `dict[str, Any]` or `pd.DataFrame`. Structure:
  ```python
  {
    "my_check": {
      "issues": int,
      "issue_values": list[str],
      "issue_row_numbers": list[int]
    }
  }
  ```
  Or a DataFrame for detailed outputs (e.g., duplicates, zero-vote groups).
- **Reference files:** `help_files/*.csv` used for FIPS checks; gracefully skipped if missing
- **AGGREGATE_MARKERS:** Rows with `candidate` matching these tokens (e.g., `"COUNTY TOTALS"`, `"OVERVOTES"`) are excluded from duplicate/mismatch detection. Edit in [qa_core/config.py](qa_core/config.py#L40).

## Adding a New Check (Step-by-Step)

1. **Implement** in appropriate module:
   - Structural/field → [qa_core/checks.py](qa_core/checks.py)
   - Numeric/distribution → [qa_core/stats_utils.py](qa_core/stats_utils.py)
   - Regex/format → [qa_core/field_checks.py](qa_core/field_checks.py)
   
   ```python
   def my_new_check(df: pd.DataFrame) -> dict[str, Any]:
       issues_mask = df["votes"].astype(str).str.contains("N/A", na=False)
       vals = df.loc[issues_mask, "votes"].head(10).tolist()
       rows = df.loc[issues_mask].index.to_series().add(1).head(10).tolist()
       return {
           "issues": int(issues_mask.sum()),
           "issue_values": vals,
           "issue_row_numbers": rows
       }
   ```

2. **Register** in [qa_core/runner.py](qa_core/runner.py) (~line 110):
   ```python
   all_results["my_new_check"] = checks.my_new_check(df)
   ```

3. **Test** locally:
   ```bash
   python qapp.py tests/nh_test.csv
   # Inspect output/NH/report_nh_test.xlsx for new check
   ```

4. **Run tests** (if modifying core logic):
   ```bash
   pytest -q tests/
   ```

## Testing & Validation

- **Sample data:** [tests/nh_test.csv](tests/nh_test.csv), [tests/nj_test.csv](tests/nj_test.csv) (~3k rows each)
- **Test suite:** Pytest-based. Run with `pytest -q`. See [tests/test_checks.py](tests/test_checks.py) for patterns.
- **Manual verification:** Compare output Excel sheets to expected check results.

## Common Patterns

**Sample issues helper:**
```python
# In qa_core/checks.py
def sample_issues(df, condition, col=None, n=10):
    matches = df.loc[condition]
    rows = matches.index.to_series().add(1).head(n).tolist()
    vals = matches[col].head(n).astype(str).tolist() if col else []
    if condition.sum() > n:
        vals.append("...")
        rows.append("...")
    return vals, rows
```

**Numeric coercion:**
```python
votes_numeric = pd.to_numeric(df["votes"], errors="coerce")
neg_mask = votes_numeric < 0
```

**Multi-section checks:**
For checks returning multiple sub-checks (e.g., `field_formats`), return a nested dict:
```python
{
  "party_simplified_invalid": {"issues": 5, "issue_values": [...]},
  "mode_missing": {"issues": 12, "issue_values": []}
}
```
Report module auto-flattens these into separate Excel rows.

## Integration Gotchas

- **Don't** return non-serializable objects (sets, custom classes) — `report.py` expects dicts/DataFrames/lists/scalars
- **Don't** mutate `df` in check functions — runner reuses the same DataFrame across all checks
- **Don't** change state detection logic ([runner.py#L50](qa_core/runner.py#L50)) without updating `QA_OUTPUT_DIR` assumptions
- **Do** use `logging.info()` for progress, `logging.warning()` for skipped/failed checks
- **Do** handle missing columns gracefully (`if "votes" not in df.columns: return {...}`)

## Configuration

Edit [qa_core/config.py](qa_core/config.py) for:
- `REQUIRED_COLUMNS` — canonical column set
- `OUTLIER_THRESHOLD` — MAD threshold (default 3.5)
- `AGGREGATE_MARKERS` — tokens identifying summary rows (excluded from duplicate checks)
- `AUTO_OPEN_REPORT` — auto-open Excel report after generation (default `True`)
- `VALID_STAGES`, `VALID_MODES`, `VALID_DATAVERSES` — enumerated values for field validation

## File Loading & Normalization

[qa_core/io_utils.py](qa_core/io_utils.py) auto-detects delimiter (`.csv` vs `.tsv`), loads as `dtype=str`, and replaces `MISSING_TOKENS` with `""` (empty string). All downstream checks treat missing as empty string.

## Legacy Migration Notes

`legacy/` contains original sbaltz QA engine. Current codebase is a complete refactor (v3+). Key differences:
- Single Excel output (not per-check text files)
- Unified `all_results` dict structure
- Modular check modules (`check_fips`, `field_checks`, `office_checks`)
- Auto-open report with `config.AUTO_OPEN_REPORT`
