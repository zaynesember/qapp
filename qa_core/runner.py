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
    try:
        df = io_utils.load_data(file_path)
    except Exception as e:
        logging.exception(f"Error loading file {file_path}: {e}")
        return

    logging.info(f"Loaded dataset with {len(df):,} rows and {len(df.columns)} columns.")
    # Prepare original/ordered column lists and enforce canonical ordering when possible
    try:
        original_cols = list(df.columns)
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
        pass

    # ------------------------------------------------------------------
    help_dir = pathlib.Path(__file__).resolve().parent.parent / "help_files"
    # Attempt to detect state from the filename using the reference table
    try:
        state_ref, _ = check_fips.load_reference_files(help_dir)
        detected = check_fips.detect_state_from_filename(file_path, state_ref)
        if detected:
            all_results['detected_state'] = detected
            logging.info(f"Detected state from filename: {detected.get('state_po')} - {detected.get('state_name')}")
        else:
            logging.info("No state detected from filename using reference files.")
    except Exception as e:
        logging.warning(f"Failed to detect state from filename: {e}")

    # Run structural and field-level checks so they appear in the report
    try:
        logging.info("Running column and field checks...")
        all_results["columns"] = checks.check_columns(df)
        all_results["fields"] = checks.check_fields(df)
    except Exception as e:
        logging.warning(f"Column/field checks failed: {e}")

    # Field-format validations (enumerated sets, missing vs invalid)
    try:
        logging.info("Running field-format validations...")
        all_results["field_formats"] = check_field_formats.validate_field_patterns(df)
    except Exception as e:
        logging.warning(f"Field format checks failed: {e}")

    # Run FIPS/state identifier checks (state codes)
    try:
        logging.info("Running state/FIPS checks...")
        fips_res = check_fips.run_fips_checks(df, help_dir, file_path)
        # place under 'state_codes' which the report prefers
        all_results["state_codes"] = fips_res
    except Exception as e:
        logging.warning(f"State/FIPS checks failed: {e}")
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

    # Compare aggregated totals to state-level reference files (president/senate)
    try:
        if (help_dir.exists() and 'statewide_totals' in all_results):
            # Ensure the specific state-level reference files exist; if none are present,
            # warn and skip the president/senate comparisons entirely.
            required_files = ["2024-president-state.csv", "2024-senate-state.csv"]
            missing = [f for f in required_files if not (help_dir / f).exists()]
            if len(missing) == len(required_files):
                logging.warning("State-level totals files not found in help_files; skipping President and Senate comparisons.")
            else:
                if missing:
                    logging.warning(f"State-level totals missing for: {', '.join(missing)}; will skip those files.")
                logging.info("Comparing aggregated statewide totals to help_files references...")
                try:
                    compare_results = stats_utils.compare_with_state_level(all_results['statewide_totals'], help_dir, all_results.get('detected_state'))
                    # Place the summary of these checks into a single section for the report
                    all_results['statewide_totals_checks'] = {}
                    for k, v in compare_results.items():
                        # v is expected to be a dict with 'issues', 'issue_values', maybe 'details_df'
                        if isinstance(v, dict):
                            # Copy summary fields into the existing 'fields' section so
                            # it appears in the QA Summary but does not create a new sheet.
                            summary = {
                                'issues': int(v.get('issues', 0) or 0),
                                'issue_values': v.get('issue_values', []),
                                'issue_row_numbers': v.get('issue_row_numbers', []),
                                'note': v.get('note', None),
                            }
                            all_results.setdefault('fields', {})[k] = summary
                            # If a details DataFrame was returned, collect it to merge
                            if isinstance(v.get('details_df'), pd.DataFrame):
                                # collect all office comparison details to merge
                                all_results.setdefault('_statewide_comparisons_tmp', []).append(v.get('details_df'))
                        else:
                            # Non-dict result: log as a note under 'fields'
                            all_results.setdefault('fields', {})[k] = {'issues': 0, 'note': str(v)}
                except Exception as e:
                    logging.warning(f"State-level totals comparison failed: {e}")
            # If we collected any comparison details, concatenate and merge
            try:
                comp_list = all_results.pop('_statewide_comparisons_tmp', [])
                if comp_list:
                    comp_df = pd.concat(comp_list, ignore_index=True, sort=False)
                    # Ensure we have the main totals DataFrame to merge into
                    totals_df = all_results.get('statewide_totals')
                    try:
                        if isinstance(totals_df, pd.DataFrame) and not totals_df.empty:
                            # Make a defensive copy
                            totals_df = totals_df.copy()

                            # Ensure aggregated dataset vote column exists for merging/inspection
                            if 'dataset_votes' not in totals_df.columns and 'votes' in totals_df.columns:
                                try:
                                    totals_df['dataset_votes'] = pd.to_numeric(totals_df['votes'], errors='coerce').fillna(0).astype(int)
                                except Exception:
                                    totals_df['dataset_votes'] = totals_df['votes']

                            # Local name-normalization to match stats_utils behavior: remove parentheses,
                            # strip periods, split on conjunctions (&, AND, /), handle 'LAST, FIRST' ordering,
                            # and produce 'FIRST LAST' key (uppercased). This mirrors the compare helper.
                            import re
                            def _name_key(s):
                                try:
                                    s0 = str(s).strip()
                                    if not s0:
                                        return ""
                                    s0 = re.sub(r"\(.*?\)", "", s0)
                                    s0 = s0.replace('.', '')
                                    s0 = re.split(r"\s*(?:&|AND|/)\s*", s0, flags=re.IGNORECASE)[0].strip()
                                    if "," in s0:
                                        parts = [p.strip() for p in s0.split(",")]
                                        last = parts[0]
                                        first_parts = parts[1].split()
                                        first = first_parts[0] if first_parts else ""
                                        return (first + " " + last).strip().upper()
                                    tokens = [t for t in s0.split() if t]
                                    if len(tokens) == 1:
                                        return tokens[0].upper()
                                    return (tokens[0] + " " + tokens[-1]).upper()
                                except Exception:
                                    return str(s).strip().upper()

                            # Compute normalized keys on totals
                            totals_df['candidate_norm'] = totals_df.get('candidate_norm', totals_df.get('candidate', '')).apply(_name_key)
                            totals_df['office_norm'] = totals_df.get('office_norm', totals_df.get('office', '')).astype(str).str.strip().str.upper()

                            # Aggregate totals by normalized keys so variants like 'KAMALA D HARRIS' and
                            # 'KAMALA HARRIS' collapse into a single canonical row per candidate_norm
                            group_cols = ['office_norm', 'candidate_norm']
                            agg_fields = {}
                            # keep a representative office string
                            agg_fields['office'] = 'first'
                            # sum votes/dataset_votes
                            agg_fields['votes'] = 'sum'
                            agg_fields['dataset_votes'] = 'sum'
                            # preserve a representative candidate and party
                            agg_fields['candidate'] = 'first'
                            if 'party_simplified' in totals_df.columns:
                                agg_fields['party_simplified'] = 'first'
                            if 'district' in totals_df.columns:
                                agg_fields['district'] = 'first'

                            totals_agg = totals_df.groupby(group_cols, dropna=False).agg(agg_fields).reset_index()
                            # Ensure dataset_votes is integer-like
                            try:
                                totals_agg['dataset_votes'] = pd.to_numeric(totals_agg['dataset_votes'], errors='coerce').fillna(0).astype(int)
                            except Exception:
                                pass

                            # Ensure comp_df has normalized keys too; if not present, compute from the candidate column
                            if 'candidate_norm' not in comp_df.columns or comp_df['candidate_norm'].isnull().all():
                                comp_df['candidate_norm'] = comp_df.get('candidate', '').apply(_name_key)
                            else:
                                comp_df['candidate_norm'] = comp_df['candidate_norm'].astype(str).str.strip().str.upper()

                            # Compute or infer office_norm for comp_df. If the details DataFrame
                            # omitted the 'office' column, try to infer office_norm by mapping
                            # candidate_norm → office_norm from the aggregated totals.
                            if 'office' in comp_df.columns:
                                comp_df['office_norm'] = comp_df.get('office_norm', comp_df.get('office', '')).astype(str).str.strip().str.upper()
                            else:
                                # build mapping from totals_agg (computed below) after we have it
                                comp_df['office_norm'] = ''

                            # Merge comparison columns into the aggregated totals
                            # Include state_candidate (display name from help file) when present
                            comp_cols = [c for c in ['office_norm', 'candidate_norm', 'state_candidate', 'state_votes', 'diff', 'present_in', 'suggested_match', 'match_score'] if c in comp_df.columns]
                            # If comp_df lacks office_norm values, infer them from totals_agg mapping
                            if comp_df['office_norm'].isnull().all() or (comp_df['office_norm'] == '').all():
                                mapping = {k: v for k, v in totals_agg.set_index('candidate_norm')['office_norm'].to_dict().items()}
                                comp_df['office_norm'] = comp_df['candidate_norm'].map(mapping).fillna(comp_df['office_norm'])

                            merged_totals = pd.merge(
                                totals_agg,
                                comp_df[comp_cols].drop_duplicates(subset=['office_norm', 'candidate_norm']),
                                on=['office_norm', 'candidate_norm'],
                                how='left',
                            )
                            # Drop helper office_norm. We prefer showing the state-side
                            # candidate display name (state_candidate) instead of the
                            # internal 'candidate_norm' helper in the final sheet.
                            merged_totals = merged_totals.drop(columns=['office_norm'], errors='ignore')
                            # If a 'state_candidate' column exists, prefer it for display
                            # and drop the internal 'candidate_norm' helper to avoid
                            # confusing users. Keep it only if 'state_candidate' absent.
                            if 'state_candidate' in merged_totals.columns and 'candidate_norm' in merged_totals.columns:
                                try:
                                    merged_totals = merged_totals.drop(columns=['candidate_norm'])
                                except Exception:
                                    pass
                            # Drop redundant raw 'votes' column (we use 'dataset_votes' as canonical)
                            if 'votes' in merged_totals.columns and 'dataset_votes' in merged_totals.columns:
                                try:
                                    merged_totals = merged_totals.drop(columns=['votes'])
                                except Exception:
                                    pass
                            # Reorder columns to put office first for the Vote Aggregation sheet
                            desired_order = [
                                'office', 'candidate', 'party_simplified', 'district',
                                'dataset_votes', 'state_candidate', 'state_votes', 'diff', 'present_in',
                                'suggested_match', 'match_score'
                            ]
                            cols_present = [c for c in desired_order if c in merged_totals.columns]
                            # append any other columns at the end to avoid dropping data
                            other_cols = [c for c in merged_totals.columns if c not in cols_present]
                            merged_totals = merged_totals[cols_present + other_cols]
                            # Remove internal suggestion columns that are not needed in the
                            # primary Vote Aggregation sheet for readability.
                            for _c in ['suggested_match', 'match_score']:
                                if _c in merged_totals.columns:
                                    try:
                                        merged_totals = merged_totals.drop(columns=[_c])
                                    except Exception:
                                        pass

                            # Human-friendly header renames for Excel output
                            rename_map = {
                                'office': 'Office',
                                'candidate': 'Candidate',
                                'party_simplified': 'Party',
                                'district': 'District',
                                'dataset_votes': 'Dataset Votes',
                                'state_candidate': 'State Candidate',
                                'state_votes': 'State Votes',
                                'diff': 'Difference',
                                'present_in': 'Present In'
                            }
                            cols_to_rename = {k: v for k, v in rename_map.items() if k in merged_totals.columns}
                            if cols_to_rename:
                                try:
                                    merged_totals = merged_totals.rename(columns=cols_to_rename)
                                except Exception:
                                    pass

                            all_results['statewide_totals'] = merged_totals
                        else:
                            # No existing totals: use comp_df as the statewide_totals sheet
                            # but clean up column names to match expected output
                            comp_df = comp_df.copy()
                            if 'candidate_norm' in comp_df.columns:
                                comp_df = comp_df.rename(columns={'candidate_norm': 'candidate'})
                            all_results['statewide_totals'] = comp_df
                    except Exception:
                        # As a final fallback, append comp_df rows to any existing totals
                        try:
                            if isinstance(totals_df, pd.DataFrame) and not totals_df.empty:
                                appended = pd.concat([totals_df, comp_df], ignore_index=True, sort=False)
                                all_results['statewide_totals'] = appended
                            else:
                                all_results['statewide_totals'] = comp_df
                        except Exception:
                            # If all else fails, still attach comp_df but under the standard key
                            all_results['statewide_totals'] = comp_df
            except Exception:
                logging.exception('Failed to merge state-level comparison details into statewide_totals')
    except Exception:
        # ensure any unexpected error here doesn't stop report generation
        logging.exception("Unexpected error during state-level totals comparison")

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
