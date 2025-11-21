"""
check_fips.py — FIPS and state identifier validation (v3.6)
Ensures internal consistency between detected state and file contents.
"""

import pandas as pd
import logging
from pathlib import Path


def load_reference_files(help_dir: Path):
    """Load state and county reference tables from help_files."""
    state_ref = pd.read_csv(help_dir / "merge_on_statecodes.csv", dtype=str)
    county_ref = pd.read_csv(help_dir / "county-fips-codes.csv", dtype=str)
    state_ref.columns = [c.strip().lower() for c in state_ref.columns]
    county_ref.columns = [c.strip().lower() for c in county_ref.columns]
    return state_ref, county_ref


def detect_state_from_filename(file_path: Path, state_ref: pd.DataFrame) -> dict:
    """Infer state_po and related identifiers from filename prefix."""
    stem = Path(file_path).stem
    prefix = stem[:2].upper()
    match = state_ref[state_ref["state_po"].str.upper() == prefix]
    if match.empty:
        return {}
    row = match.iloc[0]
    return {
        "state_po": row["state_po"],
        "state_name": row.get("state", ""),
        "state_fips": str(row.get("state_fips", "")).zfill(2),
        "state_ic": str(row.get("state_ic", "")),   # may be '04' in ref
        "state_cen": str(row.get("state_cen", ""))  # may be '12' in ref
    }


def _norm_str(s: str) -> str:
    """Generic normalizer for robust comparisons (trim + upper)."""
    return str(s).strip().upper()


def _strip_leading_zeros(s: str) -> str:
    """Normalize numeric code strings by stripping leading zeros."""
    s = str(s).strip()
    # keep '0' as '0'
    return s.lstrip('0') or '0'


def validate_state_identifiers(df: pd.DataFrame, expected: dict) -> dict:
    """
    Validate FIPS/state identifiers against detected state info.

    Rules:
      - state_po: case-insensitive exact match
      - state_fips: exact match to zero-padded 2-char string (strict), plus separate padding check
      - state_ic, state_cen: compare after stripping leading zeros (so '04' == '4')
    """
    out = {}
    if df.empty:
        return out

    def _make_entry(mask, col):
        rows = df.loc[mask].index.to_series().add(1).tolist()
        vals = df.loc[mask, col].astype(str).tolist() if col in df.columns else []
        return {"issues": len(rows), "issue_values": vals, "issue_row_numbers": rows}

    # --- state_po (case-insensitive equality) ---
    exp_po = expected.get("state_po")
    if "state_po" in df.columns and exp_po:
        mask = df["state_po"].astype(str).str.strip().str.upper().ne(_norm_str(exp_po))
        out["state_po_mismatch"] = _make_entry(mask, "state_po")
    else:
        out["state_po_mismatch"] = {"issues": 0, "issue_values": [], "issue_row_numbers": []}

    # --- state_fips (strict equality to zero-padded value) ---
    exp_fips = expected.get("state_fips")
    if "state_fips" in df.columns and exp_fips:
        # strict: must equal the padded expected string (e.g., '09', '33')
        mask = df["state_fips"].astype(str).str.strip().ne(str(exp_fips).zfill(2))
        out["state_fips_mismatch"] = _make_entry(mask, "state_fips")
    else:
        out["state_fips_mismatch"] = {"issues": 0, "issue_values": [], "issue_row_numbers": []}

    # separate padding check for state_fips (length < 2)
    if "state_fips" in df.columns:
        fips_str = df["state_fips"].astype(str).str.strip()
        bad_pad_mask = fips_str.str.len() < 2
        out["state_fips_not_padded"] = _make_entry(bad_pad_mask, "state_fips")
    else:
        out["state_fips_not_padded"] = {"issues": 0, "issue_values": [], "issue_row_numbers": []}

    # --- state_ic (numeric equivalence: strip leading zeros) ---
    exp_ic = expected.get("state_ic")
    if "state_ic" in df.columns and exp_ic not in (None, ""):
        norm_exp_ic = _strip_leading_zeros(exp_ic)
        norm_df_ic = df["state_ic"].astype(str).map(_strip_leading_zeros)
        mask = norm_df_ic.ne(norm_exp_ic)
        out["state_ic_mismatch"] = _make_entry(mask, "state_ic")
    else:
        out["state_ic_mismatch"] = {"issues": 0, "issue_values": [], "issue_row_numbers": []}

    # --- state_cen (numeric equivalence: strip leading zeros) ---
    exp_cen = expected.get("state_cen")
    if "state_cen" in df.columns and exp_cen not in (None, ""):
        norm_exp_cen = _strip_leading_zeros(exp_cen)
        norm_df_cen = df["state_cen"].astype(str).map(_strip_leading_zeros)
        mask = norm_df_cen.ne(norm_exp_cen)
        out["state_cen_mismatch"] = _make_entry(mask, "state_cen")
    else:
        out["state_cen_mismatch"] = {"issues": 0, "issue_values": [], "issue_row_numbers": []}

    return out


def validate_county_fips(df: pd.DataFrame, county_ref: pd.DataFrame) -> dict:
    """Validate county_fips values against reference set."""
    out = {}
    if "county_fips" not in df.columns:
        out["invalid_county_fips"] = {"issues": 0, "issue_values": [], "issue_row_numbers": []}
        return out
    valid = set(county_ref["county_fips"].astype(str))
    mask = ~df["county_fips"].astype(str).isin(valid)
    rows = df.loc[mask].index.to_series().add(1).tolist()
    vals = df.loc[mask, "county_fips"].astype(str).tolist()
    out["invalid_county_fips"] = {"issues": len(rows), "issue_values": vals, "issue_row_numbers": rows}
    return out


def validate_county_state_prefix(df: pd.DataFrame, expected: dict) -> dict:
    """Validate that `county_fips` prefixes match the expected state FIPS.

    Many datasets include 5-digit county FIPS; the leading two digits encode the
    state FIPS. If present, rows whose `county_fips` prefix does not match the
    expected `state_fips` indicate possible cross-state contamination or wrong
    state mapping.
    """
    out = {}
    key = "county_state_mismatch"
    if "county_fips" not in df.columns or not expected.get("state_fips"):
        out[key] = {"issues": 0, "issue_values": [], "issue_row_numbers": []}
        return out

    def _prefix(f):
        s = str(f).strip()
        if len(s) >= 2:
            return s[:2]
        return s.zfill(2)

    expected_prefix = str(expected.get("state_fips", "")).zfill(2)
    prefixes = df["county_fips"].astype(str).map(lambda x: _prefix(x))
    mask = prefixes.ne(expected_prefix)
    rows = df.loc[mask].index.to_series().add(1).tolist()
    vals = df.loc[mask, "county_fips"].astype(str).tolist()
    out[key] = {"issues": len(rows), "issue_values": vals, "issue_row_numbers": rows}
    return out


def run_fips_checks(df: pd.DataFrame, help_dir: Path, file_path: Path | None = None) -> dict:
    """Run all FIPS/state validation checks and return flat dictionary under 'state_codes' key in results."""
    state_ref, county_ref = load_reference_files(help_dir)
    expected = detect_state_from_filename(file_path, state_ref) if file_path else {}

    results = {}
    if expected:
        results.update(validate_state_identifiers(df, expected))
        # extra check: ensure county_fips prefixes align with expected state_fips
        results.update(validate_county_state_prefix(df, expected))
    results.update(validate_county_fips(df, county_ref))

    # Ensure every key exists
    required = [
        "state_po_mismatch", "state_fips_mismatch", "state_fips_not_padded",
        "state_ic_mismatch", "state_cen_mismatch", "invalid_county_fips"
    ]
    # include county->state prefix cross-check
    required.append("county_state_mismatch")
    for k in required:
        results.setdefault(k, {"issues": 0, "issue_values": [], "issue_row_numbers": []})

    total = sum(v["issues"] for v in results.values())
    if total:
        logging.warning(f"State code validation found {total} issues.")
    else:
        logging.info("All state codes validated successfully.")
    return results
