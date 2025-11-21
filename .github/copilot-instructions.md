<!-- Copilot / AI agent instructions for the QAPP repository -->
# QAPP — AI Agent Guidance

This file contains concise, actionable guidance to help an AI coding agent be immediately productive in this repository.

- **Project purpose:** `qapp` is MEDSL's precinct-level QA engine. The main entry point is `qapp.py` which calls `qa_core.runner.run_qa` to execute checks and emit a single Excel report plus auxiliary outputs.

- **Entrypoints & commands:**
  - Run via wrapper: `python qapp.py <path/to/STATE_file.csv>`
  - Run module directly: `python -m qa_core.runner <path/to/file.csv>`
  - Recommended quick setup:
    ```bash
    python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    python qapp.py tests/nh_test.csv
    ```

- **Where to look first:**
  - `qa_core/runner.py` — orchestrates load → checks → summarize → `report.write_excel_report`
  - `qapp.py` — thin CLI shim used by developers/scripts
  - `qa_core/config.py` — canonical `REQUIRED_COLUMNS`, thresholds, and `QA_OUTPUT_DIR`
  - `qa_core/checks.py` — structural and field checks and duplicate logic
  - `qa_core/stats_utils.py` — numeric and distributional checks
  - `qa_core/io_utils.py` and `qa_core/data_summary.py` — loading, missingness, and `export_unique_values`
  - `qa_core/report.py` — Excel/text output formatting

- **Important data & conventions (explicit & discoverable):**
  - Input file state detection: runner takes the file stem, splits on `_`, and uses the first token as the state code (uppercased). See `runner.run_qa` (`state_name = file_path.stem.split("_")[0].upper()`).
  - Output layout: reports and logs are written to `output/<STATE>/` (controlled by `config.QA_OUTPUT_DIR`). Excel filename pattern: `report_<inputstem>.xlsx`.
  - `help_files/` contains canonical references used for FIPS/state checks; runner looks there at runtime (`merge_on_statecodes.csv`, `county-fips-codes.csv`). If `help_files/` is missing, FIPS checks are skipped.
  - Unique-value exports are placed in a `unique_values/` subfolder per state (see `data_summary.export_unique_values`).
  - Required columns are defined in `qa_core/config.py -> REQUIRED_COLUMNS`. Use this list when adding or validating checks.

- **How to add a new check (concrete example):**
  1. Implement `def my_check(df: pd.DataFrame) -> dict[str, Any]:` in `qa_core/checks.py` (or `stats_utils.py` for numeric checks).
  2. Return a small dictionary or DataFrame representing the check result.
  3. Register the check in `qa_core/runner.py` by assigning into `all_results` (e.g., `all_results['my_check'] = checks.my_check(df)`) so it gets reported and written to Excel.

- **Logging & diagnostics:**
  - Runner initializes logging to `qa_run.log` inside the state output folder. Log lines also stream to console.
  - When loading fails, `io_utils.load_data` exceptions are logged and the run returns early.

- **Tests & sample data:**
  - There are sample CSVs in `tests/` (e.g., `nh_test.csv`, `nj_test.csv`) useful for quick runs. There is no unit test harness in the repo by default; run the runner against these files to validate behavior.

- **Styles & patterns the agent should follow:**
  - Keep changes minimal and localized: prefer adding a new check function and registering it in `runner.py` rather than changing runner control flow.
  - Follow PEP‑8 and the repository's docstring style (module header comments found in each `qa_core` file).
  - Prefer using `qa_core/config.py` constants (e.g., `REQUIRED_COLUMNS`, `OUTLIER_THRESHOLD`) rather than hard-coded values.

- **Integration points to be careful with:**
  - `runner.py` composes results into `all_results` and expects values to be serializable by `report.write_excel_report` (pandas DataFrames and dictionaries). Returning exotic objects may break report generation.
  - File-path conventions (state detection via filename) are fragile — avoid changing that behavior without updating calls that depend on the derived `state_name` and output folder.

- **If in doubt:**
  - Run the engine on `tests/nh_test.csv` and inspect `output/NH*` to see exact output files and formats.
  - Look at `qa_core/report.py` to understand how results are serialized into Excel and text; match expected shapes (dicts of scalars, DataFrames, lists).

- **Feedback:** Please tell me which sections need more detail (examples, check template, or PR checklist).
