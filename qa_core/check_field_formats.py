"""
check_field_formats.py — Field-format validation for MEDSL Precinct QA Engine (v2.9)

Distinguishes between missing and invalid values according to the codebook.
Original QA engine by sbaltz.
Refactored and extended by Zayne (2025).
"""

from __future__ import annotations
import pandas as pd
from typing import Dict, Any


def validate_field_patterns(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Validate discrete-value columns (from codebook) for invalid or missing values.
    Differentiates between missing and invalid entries.
    Returns a nested dictionary compatible with QA report formatting.
    """
    results: Dict[str, Any] = {}
    if df.empty:
        return results

    # ------------------------------------------------------------------
    # 1. Enumerated valid sets per the codebook
    # ------------------------------------------------------------------
    valid_sets = {
        "party_simplified": {"DEMOCRAT", "REPUBLICAN", "LIBERTARIAN", "OTHER", "NONPARTISAN", ""},
        "mode": {"TOTAL", "ELECTION DAY", "PROVISIONAL", "ABSENTEE", "ONE-STOP"},
        "stage": {"PRI", "GEN", "RUNOFF"},
        "special": {"TRUE", "FALSE"},
        "writein": {"TRUE", "FALSE"},
        "dataverse": {"PRESIDENT", "SENATE", "HOUSE", "STATE", "LOCAL", ""},
    }

    # Tokens treated as missing
    missing_tokens = {"", " ", "NA", "NULL", "N/A", "NONE", "NAN"}

    # ------------------------------------------------------------------
    # 2. Validate columns that have enumerated sets
    # ------------------------------------------------------------------
    for col, valid_values in valid_sets.items():
        if col not in df.columns:
            continue

        col_data = df[col].astype(str).str.strip().str.upper()

        # Identify missing and invalid
        missing_mask = col_data.isin(missing_tokens)
        invalid_mask = ~col_data.isin(valid_values | missing_tokens)

        missing_count = int(missing_mask.sum())
        invalid_count = int(invalid_mask.sum())

        # Get sample values + row indices for context
        miss_vals = col_data[missing_mask].head(10).tolist()
        miss_rows = (col_data[missing_mask].index + 1).tolist()
        inv_vals = col_data[invalid_mask].head(10).tolist()
        inv_rows = (col_data[invalid_mask].index + 1).tolist()

        if missing_count > 10:
            miss_vals.append("...")
            miss_rows.append("...")
        if invalid_count > 10:
            inv_vals.append("...")
            inv_rows.append("...")

        results[f"{col}_missing"] = {
            "issues": missing_count,
            "issue_values": miss_vals,
            "issue_row_numbers": miss_rows,
        }

        results[f"{col}_invalid"] = {
            "issues": invalid_count,
            "issue_values": inv_vals,
            "issue_row_numbers": inv_rows,
        }

    # ------------------------------------------------------------------
    # 3. Pass-through for non-enumerated columns
    # (no fixed valid set, only missingness tracked)
    # ------------------------------------------------------------------
    other_cols = [
        c
        for c in df.columns
        if c not in valid_sets and c not in ["votes", "candidate", "precinct", "office"]
    ]
    for col in other_cols:
        col_data = df[col].astype(str).str.strip()
        missing_mask = col_data.isin(missing_tokens)
        missing_count = int(missing_mask.sum())
        if missing_count > 0:
            miss_vals = col_data[missing_mask].head(10).tolist()
            miss_rows = (col_data[missing_mask].index + 1).tolist()
            if missing_count > 10:
                miss_vals.append("...")
                miss_rows.append("...")
            results[f"{col}_missing"] = {
                "issues": missing_count,
                "issue_values": miss_vals,
                "issue_row_numbers": miss_rows,
            }

    return results
