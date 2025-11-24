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
    details: Dict[str, pd.DataFrame] = {}
    if df.empty:
        return results, {}

    # --- Generic per-text-field checks (apply to all object/string columns) ---
    # These checks flag: newlines, extraneous/multiple spaces, accented letters,
    # and nonstandard symbols (outside a conservative set of allowed ASCII punctuation).
    # Results are stored under a section named `<col>_format` for each column.
    allowed_symbol_re = re.compile(r"[^A-Za-z0-9\s\.,;:\'\"\-\/\&\(\)\?\!%$@#]")
    accented_re = re.compile(r"[\u00C0-\u017F]")
    newline_re = re.compile(r"[\r\n]")
    multi_space_re = re.compile(r" {2,}")

    for col in df.columns:
        # operate only on non-numeric fields (treat as text)
        try:
            series_raw = df[col].astype(str)
        except Exception:
            continue
        # skip obviously numeric columns
        if pd.api.types.is_numeric_dtype(df[col]):
            continue
        section_name = f"{col}_format"
        section_checks: Dict[str, Any] = {}

        # Build a mask that indicates non-empty, non-null values to avoid
        # flagging empties (they're reported elsewhere in Missingness).
        nonempty_mask = (~df[col].isna()) & (series_raw.str.strip() != "")

        # Leading or trailing whitespace (only consider non-empty values)
        stripped = series_raw.str.strip()
        leading_trailing_mask = (series_raw != stripped) & nonempty_mask
        issues = int(leading_trailing_mask.sum())
        vals, rows = _sample_list(series_raw, leading_trailing_mask)
        section_checks["EXTRANEOUS_LEADING_OR_TRAILING_WHITESPACE"] = {
            "issues": issues,
            "issue_values": vals,
            "issue_row_numbers": rows,
        }

        # Embedded newlines
        try:
            newline_mask = series_raw.str.contains(newline_re, na=False) & nonempty_mask
        except re.error:
            newline_mask = pd.Series([False] * len(series_raw), index=series_raw.index)
        issues = int(newline_mask.sum())
        vals, rows = _sample_list(series_raw, newline_mask)
        section_checks["EMBEDDED_NEWLINES"] = {"issues": issues, "issue_values": vals, "issue_row_numbers": rows}

        # Multiple consecutive spaces
        try:
            multi_space_mask = series_raw.str.contains(multi_space_re, na=False) & nonempty_mask
        except re.error:
            multi_space_mask = pd.Series([False] * len(series_raw), index=series_raw.index)
        issues = int(multi_space_mask.sum())
        vals, rows = _sample_list(series_raw, multi_space_mask)
        section_checks["MULTIPLE_CONSECUTIVE_SPACES"] = {"issues": issues, "issue_values": vals, "issue_row_numbers": rows}

        # Accented / non-ASCII Latin letters
        try:
            accented_mask = series_raw.str.contains(accented_re, na=False) & nonempty_mask
        except re.error:
            accented_mask = pd.Series([False] * len(series_raw), index=series_raw.index)
        issues = int(accented_mask.sum())
        vals, rows = _sample_list(series_raw, accented_mask)
        section_checks["ACCENTED_LETTERS"] = {"issues": issues, "issue_values": vals, "issue_row_numbers": rows}

        # Nonstandard symbols (characters outside allowed ASCII punctuation set)
        try:
            symbol_mask = series_raw.str.contains(allowed_symbol_re, na=False) & nonempty_mask
        except re.error:
            symbol_mask = pd.Series([False] * len(series_raw), index=series_raw.index)
        issues = int(symbol_mask.sum())
        vals, rows = _sample_list(series_raw, symbol_mask)
        section_checks["NONSTANDARD_SYMBOLS"] = {"issues": issues, "issue_values": vals, "issue_row_numbers": rows}

        # LOWERCASE detection: flag any values containing lowercase letters
        try:
            lowercase_mask = series_raw.str.contains(r"[a-z]", regex=True, na=False) & nonempty_mask
        except re.error:
            lowercase_mask = pd.Series([False] * len(series_raw), index=series_raw.index)
        issues = int(lowercase_mask.sum())
        vals, rows = _sample_list(series_raw, lowercase_mask)
        section_checks["LOWERCASE_LETTERS"] = {"issues": issues, "issue_values": vals, "issue_row_numbers": rows}

        # Odd number of quotation marks (double and single)
        try:
            odd_double = (series_raw.str.count('"', flags=0).fillna(0).astype(int) % 2 == 1) & nonempty_mask
        except Exception:
            odd_double = pd.Series([False] * len(series_raw), index=series_raw.index)
        issues = int(odd_double.sum())
        vals, rows = _sample_list(series_raw, odd_double)
        section_checks["ODD_NUMBER_OF_DOUBLE_QUOTES"] = {"issues": issues, "issue_values": vals, "issue_row_numbers": rows}

        try:
            odd_single = (series_raw.str.count("'", flags=0).fillna(0).astype(int) % 2 == 1) & nonempty_mask
        except Exception:
            odd_single = pd.Series([False] * len(series_raw), index=series_raw.index)
        issues = int(odd_single.sum())
        vals, rows = _sample_list(series_raw, odd_single)
        section_checks["ODD_NUMBER_OF_SINGLE_QUOTES"] = {"issues": issues, "issue_values": vals, "issue_row_numbers": rows}

        # Duplicate token detection within a single value (case-insensitive)
        import re as _re
        def _has_duplicate_tokens(s: str) -> bool:
            if s is None:
                return False
            s2 = str(s).strip()
            if not s2:
                return False
            tokens = _re.findall(r"\b[\w']+\b", s2)
            if not tokens:
                return False
            lower = [t.lower() for t in tokens]
            seen = set()
            for t in lower:
                if t in seen:
                    return True
                seen.add(t)
            return False

        try:
            dup_mask = series_raw.where(nonempty_mask, "").apply(_has_duplicate_tokens)
            dup_mask = dup_mask.fillna(False).astype(bool)
        except Exception:
            dup_mask = pd.Series([False] * len(series_raw), index=series_raw.index)
        issues = int(dup_mask.sum())
        vals, rows = _sample_list(series_raw, dup_mask)
        section_checks["DUPLICATE_TOKENS_WITHIN_VALUE"] = {"issues": issues, "issue_values": vals, "issue_row_numbers": rows}

        results[section_name] = section_checks
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
        # Detect squished initials like 'J.D.VANCE' or 'J.D.Vance' (no space after periods)
        # Pattern: one to three initial+period groups immediately followed by an uppercase letter
        candidate_checks["SQUISHED_INITIALS_NO_SPACE"] = r"(?:[A-Z]\.){1,3}[A-Z]"
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

        # --- running-mate detection: look for joined candidate strings like
        # 'SMITH AND JONES', 'SMITH & JONES', 'SMITH / JONES', or 'SMITH - JONES'
        rm_checks = {
            "POSSIBLE RUNNING-MATE (AND)": r"\bAND\b",
            "POSSIBLE RUNNING-MATE (&)": r"&",
            "POSSIBLE RUNNING-MATE (SLASH)": r"\s/\s",
            "POSSIBLE RUNNING-MATE (SPACE-HYPHEN-SPACE)": r"\s-\s",
        }

        rm_section = {}
        rm_mask_any = pd.Series([False] * len(series), index=series.index)
        for name, pattern in rm_checks.items():
            try:
                mask = series.str.contains(pattern, regex=True, na=False)
            except re.error:
                mask = pd.Series([False] * len(series), index=series.index)
            issues = int(mask.sum())
            vals, rows = _sample_list(series, mask)
            rm_section[name] = {"issues": issues, "issue_values": vals, "issue_row_numbers": rows}
            rm_mask_any = rm_mask_any | mask

        results["candidate_running_mates"] = rm_section
        # Provide a small DataFrame of example rows where any running-mate pattern was detected
        if rm_mask_any.any():
            details["Running Mates"] = df.loc[rm_mask_any, [c for c in ["precinct", "office", "candidate", "party_detailed"] if c in df.columns]].head(500).reset_index(drop=True)

    # --- stage special check: detect unrecognized stage values ---
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
