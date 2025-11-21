"""
field_checks.py — Per-field regex-based validation rules ported from legacy engine

Provides `validate_field_regexes(df)` which returns a nested dict compatible
with `report.write_excel_report` (keys -> {issues, issue_values, issue_row_numbers}).
"""
from __future__ import annotations
import re
from typing import Dict, Any
import pandas as pd


def _sample_list(series: pd.Series, mask: pd.Series, n: int = 10):
    vals = series[mask].head(n).astype(str).tolist()
    rows = (series[mask].index.to_series().add(1).head(n).tolist())
    return vals, rows


def validate_field_regexes(df: pd.DataFrame) -> tuple[Dict[str, Any], Dict[str, pd.DataFrame]]:
    """
    Run a small set of regex-based validations for selected fields.

    Returns a dict where keys are check names and values are dicts with
    `issues`, `issue_values`, and `issue_row_numbers`.
    """
    results: Dict[str, Any] = {}
    if df.empty:
        return results, {}

    # --- votes and magnitude checks (numeric formatting rules) ---
    votes_checks = {
        "UNRECOGNIZED CHARACTERS": r"[^0-9\-]+",
        "UNRECOGNIZED NEGATIVE SIGNS": r"(?:(?<!^)\-)|(?:\-[^1-9])",
        "UNRECOGNIZED LEADING ZEROS": r"^0[^$]",
        "(POSSIBLY) INVALID NEGATIVE VALUES": r"^-[1-9]",
    }

    for col in ("votes", "magnitude"):
        if col not in df.columns:
            continue
        series = df[col].astype(str).str.strip()
        section = f"{col}_regex"
        results_section = {}
        for name, pattern in votes_checks.items():
            try:
                mask = series.str.contains(pattern, regex=True, na=False)
            except re.error:
                mask = pd.Series([False] * len(series), index=series.index)
            issues = int(mask.sum())
            vals, rows = _sample_list(series, mask)
            results_section[name] = {"issues": issues, "issue_values": vals, "issue_row_numbers": rows}
        results[section] = results_section

    # --- candidate checks (character/punctuation rules) ---
    if "candidate" in df.columns:
        # Patterns ported (subset) from legacy Candidate.DEFAULT_TEXT_CHECKS
        candidate_checks = {
            "UNRECOGNIZED CHARACTERS": r"[^A-Z0-9\"\-\'\/\% ]+",
            "INVALID BEGINNING CHARACTERS": r'^\"(?:$|[^\"]|\".+$)|^[^A-Z0-9\"]',
            "INVALID ENDING CHARACTERS": r'(?:^|[^\"]|.+\")\"$|[^A-Z0-9\"]$',
            "EXTRANEOUS CONSECUTIVE SYMBOLS": r'\"\".+|.+\"\"|\-\-|\'\'|  |\\/\\/',
            "EXTRANEOUS SPACES": r'(?: -(?! ))|(?:- (?!(?:YES$|NO$|BLANK|OVERVOTES$|UNDERVOTES$|TOTAL)))',
            "EXTRANEOUS QUOTATION MARKS": r'^[^\"]*\"(?:[^\"]*\"[^\"]*\")*[^\"]*$',
            "(POSSIBLY) EXTRANEOUS SINGLE QUOTATION MARKS": r".*'.*'.*",
        }
        series = df["candidate"].astype(str).str.strip().str.upper()
        results_section = {}
        for name, pattern in candidate_checks.items():
            try:
                mask = series.str.contains(pattern, regex=True, na=False)
            except re.error:
                mask = pd.Series([False] * len(series), index=series.index)
            issues = int(mask.sum())
            vals, rows = _sample_list(series, mask)
            results_section[name] = {"issues": issues, "issue_values": vals, "issue_row_numbers": rows}
        results["candidate_regex"] = results_section

    # --- stage special check: detect unrecognized stage values ---
    details: Dict[str, pd.DataFrame] = {}
    if "stage" in df.columns:
        series = df["stage"].astype(str).str.strip()
        valid_names = [
            "GEN",
            "PRI",
            "GEN RUNOFF",
            "PRI RUNOFF",
            "GEN RECOUNT",
            "PRI RECOUNT",
            "GEN RUNOFF RECOUNT",
            "PRI RUNOFF RECOUNT",
        ]
        invalid_mask = ~series.isin(valid_names)
        invalid_vals = series[invalid_mask]
        results["stage_unrecognized"] = {
            "issues": int(invalid_mask.sum()),
            "issue_values": invalid_vals.unique().tolist()[:10],
            "issue_row_numbers": (invalid_vals.index.to_series().add(1).head(10).tolist()),
        }
        if not invalid_vals.empty:
            # Provide a small DataFrame of invalid rows for context
            details["stage_invalid_rows"] = df.loc[invalid_mask, [c for c in ["precinct", "office", "candidate", "stage"] if c in df.columns]].head(500).reset_index(drop=True)

    # --- magnitude checks: produce a single 'Magnitude' sheet mapping magnitude -> offices ---
    if "magnitude" in df.columns and "office" in df.columns:
        mag_map = df.groupby("office")["magnitude"].unique().reset_index()
        mag_map["magnitude"] = mag_map["magnitude"].apply(lambda x: list(x))

        # magnitude -> offices map: pivot so each detected magnitude is a column
        mag_series = df.groupby("magnitude")["office"].unique()
        mag_to_offices = {str(mag): list(offices) for mag, offices in mag_series.items()}

        # Sort magnitude columns numerically when possible, otherwise lexicographically
        def _mag_sort_key(k):
            try:
                return (0, int(k))
            except Exception:
                return (1, k)

        sorted_mags = sorted(mag_to_offices.keys(), key=_mag_sort_key)

        # Pad lists so we can create a rectangular DataFrame where each column is a magnitude
        max_len = max((len(v) for v in mag_to_offices.values()), default=0)
        padded = {mag: (mag_to_offices.get(mag, []) + [""] * (max_len - len(mag_to_offices.get(mag, [])))) for mag in sorted_mags}
        # Create DataFrame with one column per magnitude; column names show the magnitude value
        mag_df = pd.DataFrame(padded)
        # Export as a single, user-facing sheet named 'Magnitude'
        details["Magnitude"] = mag_df

    return results, details
