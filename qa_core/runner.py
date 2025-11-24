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
import subprocess
import platform
import os


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
    # Prepare original/ordered column lists and enforce canonical ordering when possible
    try:
        original_cols = list(df.columns)
        # Desired canonical order: required columns first (in config.REQUIRED_COLUMNS),
        # then any extra columns in their original order.
        canonical_present = [c for c in config.REQUIRED_COLUMNS if c in df.columns]
        extras = [c for c in original_cols if c not in config.REQUIRED_COLUMNS]
        ordered_cols = canonical_present + extras
        if ordered_cols != original_cols:
            logging.info("Reordering columns to match canonical REQUIRED_COLUMNS where present.")
            df = df.loc[:, ordered_cols]
    except Exception as e:
        logging.warning(f"Failed to compute/enforce column ordering: {e}")
    all_results: Dict[str, Any] = {}
    # Expose original/ordered column lists for reporting
    try:
        all_results["original_columns"] = original_cols
        all_results["column_order_enforced"] = {
            "issues": 0,
            "issue_values": [ordered_cols],
            "note": "Columns reordered to place REQUIRED_COLUMNS first"
        }
    except Exception:
        # already logged earlier if computing failed
        pass

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
            # Flatten one level of nested check dicts so that per-column
            # format checks (e.g., 'precinct_format' -> {"EXTRANEOUS...": {...}})
            # appear as individual checks in the 'Field Regex Checks' sheet.
            flat_summary: Dict[str, Any] = {}
            for name, val in (summary or {}).items():
                # If this value is a dict whose values are themselves dicts,
                # promote inner checks to top-level with a compound name.
                if isinstance(val, dict) and any(isinstance(x, dict) for x in val.values()):
                    for inner_name, inner_val in val.items():
                        flat_key = f"{name}::{inner_name}"
                        flat_summary[flat_key] = inner_val
                else:
                    flat_summary[name] = val
            all_results["field_regex_checks"] = flat_summary
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
        # Surface dataset-level state_po mismatch into the top-level dataset_info
        try:
            ds_summary = all_results["fips_checks"].get("state_po_dataset_summary", {})
            if ds_summary.get("dataset_state_mismatch"):
                # Flag for QA Summary and include dominant state for context
                all_results.setdefault("dataset_info", {})["state_po_dataset_mismatch"] = True
                all_results.setdefault("dataset_info", {})["dominant_state_po"] = ds_summary.get("dominant_state_po")
                all_results.setdefault("dataset_info", {})["dominant_share"] = ds_summary.get("dominant_share")
        except Exception:
            pass
    else:
        logging.warning("Help files directory not found; skipping FIPS validation.")

    # ------------------------------------------------------------------
    # Numerical and Distribution Checks
    # ------------------------------------------------------------------
    logging.info("Running numeric consistency checks...")
    all_results["numerical"] = stats_utils.run_numerical_checks(df)

    logging.info("Running vote-distribution sanity checks...")
    all_results["distribution"] = stats_utils.vote_distribution_check(df)

    # Office mapping checks
    try:
        logging.info("Running office mapping checks...")
        from qa_core import office_checks
        # Use the internal canonical set only (do not rely on help_files)
        office_res = office_checks.validate_office_mappings(df)
        # The report writer expects each section to be a dict of checks
        # where each check is itself a dict with keys like 'issues' and
        # 'issue_values'. Wrap the office mapping result under a single
        # check name so it appears in the QA Summary like other checks.
        all_results["office_mappings"] = {
            "office_mapping_check": {
                "issues": int(office_res.get("issues", 0) or 0),
                "issue_values": office_res.get("issue_values", []),
                "mapping_suggestions": office_res.get("mapping_suggestions", {}),
                "unmatched_counts": office_res.get("unmatched_counts", {}),
            }
        }
        # include sample rows as a DataFrame if present — no longer adding
        # a separate `office_mapping_samples` sheet; detailed samples are
        # available in mapping_suggestions and can be requested separately.
    except Exception as e:
        logging.warning(f"Office mapping checks failed: {e}")

    # ------------------------------------------------------------------
    # Missingness and Statewide Totals
    # ------------------------------------------------------------------
    logging.info("Summarizing missingness and uniques...")
    all_results["missingness"] = data_summary.summarize_missingness(df)
    # Build unique-values DataFrame for inclusion in the Excel report.
    # We place a single '<EMPTY>' marker in the first row of a column
    # if that column contains any missing/blank values; subsequent rows
    # list unique non-empty values.
    try:
        uniques = {}
        for col in df.columns:
            # compute unique non-empty values (as strings)
            nonnull = df[col].dropna()
            non_empty_vals = [str(x) for x in pd.Series(nonnull[nonnull.astype(str).str.strip() != ""]).unique().tolist()]
            non_empty_sorted = sorted(non_empty_vals, key=lambda v: str(v))
            has_empty = bool(df[col].isna().any() or df[col].astype(str).str.strip().eq("").any())
            col_values = []
            if has_empty:
                col_values.append("<EMPTY>")
            col_values.extend(non_empty_sorted)
            uniques[col] = col_values

        # Pad columns to same length (pad with empty strings so they appear blank)
        max_len = max((len(v) for v in uniques.values()), default=0)
        padded = {col: (vals + [""] * (max_len - len(vals))) for col, vals in uniques.items()}
        unique_df = pd.DataFrame(padded)
        if not unique_df.empty:
            all_results["unique_values"] = unique_df
    except Exception as e:
        logging.warning(f"Failed to build unique-values sheet: {e}")

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

    # Optionally open the report using the system default application.
    try:
        if getattr(config, "AUTO_OPEN_REPORT", False):
            system = platform.system()
            logging.info("AUTO_OPEN_REPORT enabled — attempting to open report with system default viewer.")
            if system == "Darwin":
                subprocess.Popen(["open", str(xlsx_path)])
            elif system == "Windows":
                try:
                    os.startfile(str(xlsx_path))
                except Exception:
                    # Fallback to start via cmd
                    subprocess.Popen(["cmd", "/c", "start", "", str(xlsx_path)])
            else:
                # Assume Linux/Unix
                subprocess.Popen(["xdg-open", str(xlsx_path)])
    except Exception as e:
        logging.warning(f"Failed to open report automatically: {e}")

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
