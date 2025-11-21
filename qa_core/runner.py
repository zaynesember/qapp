"""
runner.py — Main orchestrator for MEDSL Precinct QA Engine (v3.4)
Ensures only one Excel report (report_<inputfile>.xlsx) is produced.
"""

from __future__ import annotations
import logging
import pathlib
import pandas as pd
from typing import Dict, Any
from qa_core import (
    io_utils,
    checks,
    report,
    field_checks,
    stats_utils,
    check_field_formats,
    config,
    data_summary,
    check_fips,
)


# ---------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------
def _setup_logging(log_dir: pathlib.Path) -> None:
    """Initialize logging to both console and file."""
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "qa_run.log"
    logging.basicConfig(
        filename=log_path,
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    logging.getLogger().addHandler(logging.StreamHandler())


# ---------------------------------------------------------------------
# Main QA runner
# ---------------------------------------------------------------------
def run_qa(file_path: str | pathlib.Path) -> None:
    """Run full MEDSL QA checks and generate a single Excel report."""
    file_path = pathlib.Path(file_path)
    state_name = file_path.stem.split("_")[0].upper()
    qa_dir = config.QA_OUTPUT_DIR / state_name
    qa_dir.mkdir(parents=True, exist_ok=True)
    _setup_logging(qa_dir)

    logging.info("==============================================")
    logging.info("Starting MEDSL Precinct QA Engine (v3.4)")
    logging.info(f"File: {file_path}")
    logging.info("==============================================")

    # ------------------------------------------------------------------
    # Load dataset
    # ------------------------------------------------------------------
    try:
        df = io_utils.load_data(file_path)
    except Exception as e:
        logging.exception(f"Error loading file {file_path}: {e}")
        return

    logging.info(f"Loaded dataset with {len(df):,} rows and {len(df.columns)} columns.")
    all_results: Dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Core QA checks
    # ------------------------------------------------------------------
    logging.info("Running structural and field-level checks...")
    all_results["columns"] = checks.check_columns(df)
    all_results["fields"] = checks.check_fields(df)
    all_results["field_formats"] = check_field_formats.validate_field_patterns(df)
    # Extended regex-based field checks (port of core legacy rules)
    try:
        logging.info("Running regex-based field checks...")
        res = field_checks.validate_field_regexes(df)
        if isinstance(res, tuple) and len(res) == 2:
            summary, details = res
            all_results["field_regex_checks"] = summary
            # Add any detail DataFrames as top-level results so report writes them as sheets
            for name, table in (details or {}).items():
                if isinstance(table, pd.DataFrame):
                    all_results[name] = table
        else:
            all_results["field_regex_checks"] = res
    except Exception as e:
        logging.warning(f"Field regex checks failed: {e}")

    # ------------------------------------------------------------------
    # FIPS Validation
    # ------------------------------------------------------------------
    help_dir = pathlib.Path(__file__).resolve().parent.parent / "help_files"
    if help_dir.exists():
        logging.info("Running FIPS/state validation checks...")
        state_ref = pd.read_csv(help_dir / "merge_on_statecodes.csv", dtype=str)
        detected_state = check_fips.detect_state_from_filename(file_path, state_ref)
        all_results["detected_state"] = detected_state
        all_results["fips_checks"] = check_fips.run_fips_checks(df, help_dir, file_path)
    else:
        logging.warning("Help files directory not found; skipping FIPS validation.")

    # ------------------------------------------------------------------
    # Numerical and Distribution Checks
    # ------------------------------------------------------------------
    logging.info("Running numeric consistency checks...")
    all_results["numerical"] = stats_utils.run_numerical_checks(df)

    logging.info("Running vote-distribution sanity checks...")
    all_results["distribution"] = stats_utils.vote_distribution_check(df)

    # ------------------------------------------------------------------
    # Missingness and Statewide Totals
    # ------------------------------------------------------------------
    logging.info("Summarizing missingness and uniques...")
    all_results["missingness"] = data_summary.summarize_missingness(df)
    logging.info("Unique values exported separately to unique_values/ folder.")

    logging.info("Computing statewide totals...")
    totals = data_summary.compute_statewide_totals(df)
    if not totals.empty:
        all_results["statewide_totals"] = totals

    # ------------------------------------------------------------------
    # Duplicate and Near-Duplicate Detection
    # ------------------------------------------------------------------
    try:
        logging.info("Finding duplicate and conflicting rows...")
        duplicates_df = checks.find_duplicate_rows(df)
        all_results["duplicates"] = duplicates_df

        if not duplicates_df.empty:
            summary = duplicates_df["dup_type"].value_counts().to_dict()
            total = len(duplicates_df)
            logging.info(f"Found {total:,} rows with duplication issues.")
            all_results["duplicates_summary"] = (
                pd.DataFrame(
                    [{"Duplication Type": k.replace('_', ' ').title(),
                      "Affected Rows": v} for k, v in summary.items()]
                )
                .sort_values("Affected Rows", ascending=False)
                .reset_index(drop=True)
            )
        else:
            logging.info("No duplicate or conflicting rows detected.")

    except Exception as e:
        logging.warning(f"Duplicate detection failed: {e}")
        all_results["duplicates"] = pd.DataFrame()

    # ------------------------------------------------------------------
    # Zero‑vote precinct groups (aggregated zero totals)
    # ------------------------------------------------------------------
    try:
        logging.info("Checking precinct-office groups with zero total votes...")
        zero_groups_df = checks.find_zero_vote_precincts(df)
        all_results["zero_vote_precincts"] = zero_groups_df

        if not zero_groups_df.empty:
            total = len(zero_groups_df)
            logging.info(f"Found {total:,} precinct-office groups with zero total votes.")

            # Add a concise entry into the main QA summary under 'fields'
            # so the count appears in the 'QA Summary' sheet. Keep the
            # full DataFrame in `zero_vote_precincts` so a detailed sheet
            # with all groups is still written.
            if "fields" not in all_results or not isinstance(all_results.get("fields"), dict):
                all_results["fields"] = {} if not isinstance(all_results.get("fields"), dict) else all_results.get("fields")

            # Prepare sample values (concat grouping columns) for context
            sample_vals = []
            try:
                sample_rows = zero_groups_df.head(10)
                # Prefer to show just precinct names (first 10) to keep summary concise
                if 'precinct' in sample_rows.columns:
                    sample_vals = [str(x) for x in sample_rows['precinct'].head(10).tolist()]
                else:
                    group_cols = [c for c in ['county_fips', 'jurisdiction_fips', 'precinct', 'office', 'district'] if c in sample_rows.columns]
                    for _, r in sample_rows.iterrows():
                        sample_vals.append("|".join([str(r[c]) for c in group_cols]))
            except Exception:
                sample_vals = []

            all_results["fields"]["zero_vote_precinct_groups"] = {
                "issues": int(total),
                "issue_values": sample_vals,
                "issue_row_numbers": [],
            }
        else:
            logging.info("No zero-vote precinct-office groups found.")

    except Exception as e:
        logging.warning(f"Zero-vote precinct detection failed: {e}")
        all_results["zero_vote_precincts"] = pd.DataFrame()

    # ------------------------------------------------------------------
    # Output path — only one Excel report
    # ------------------------------------------------------------------
    xlsx_path = qa_dir / f"report_{file_path.stem}.xlsx"

    # Add dataset-level info for high-level QA summary
    try:
        unique_counties = int(df['county_fips'].nunique(dropna=True)) if 'county_fips' in df.columns else int(df['county_name'].nunique(dropna=True)) if 'county_name' in df.columns else 0
    except Exception:
        unique_counties = 0
    try:
        unique_jurisdictions = int(df['jurisdiction_fips'].nunique(dropna=True)) if 'jurisdiction_fips' in df.columns else int(df['jurisdiction_name'].nunique(dropna=True)) if 'jurisdiction_name' in df.columns else 0
    except Exception:
        unique_jurisdictions = 0

    all_results['dataset_info'] = {
        'rows': len(df),
        'columns': len(df.columns),
        'unique_counties': unique_counties,
        'unique_jurisdictions': unique_jurisdictions,
    }

    # ------------------------------------------------------------------
    # Write single Excel report
    # ------------------------------------------------------------------
    logging.info(f"Writing Excel report to {xlsx_path} ...")
    report.write_excel_report(all_results, xlsx_path)
    data_summary.export_unique_values(df, qa_dir)

    logging.info("==============================================")
    logging.info(f"QA completed successfully for {file_path.name}")
    logging.info(f"Report written to: {xlsx_path}")
    logging.info("==============================================")


# ---------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Run MEDSL Precinct QA checks on a CSV or TSV file."
    )
    parser.add_argument("file", help="Path to the input file (CSV or TSV)")
    args = parser.parse_args()
    run_qa(args.file)
