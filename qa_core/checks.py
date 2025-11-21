"""
checks.py — Structural, field-level, and duplicate QA checks (v2.9 streamlined)

Original QA engine by sbaltz.
Refactored and extended by Zayne (2025).
"""

from __future__ import annotations
import pandas as pd
import logging
from typing import Dict, Any
from qa_core import config


# ------------------------------------------------------------------
# Helper Function
# ------------------------------------------------------------------

def sample_issues(df, condition, col=None, n=10):
    """Return up to n issue values and row numbers where condition is True."""
    matches = df.loc[condition]
    rows = matches.index.to_series().add(1).head(n).tolist()
    vals = matches[col].head(n).astype(str).tolist() if col and col in df.columns else ["(n/a)"] * len(rows)
    if condition.sum() > n:
        vals.append("...")
        rows.append("...")
    return vals, rows


# ------------------------------------------------------------------
# Column & Field-Level Checks
# ------------------------------------------------------------------

def check_columns(df: pd.DataFrame) -> Dict[str, Any]:
    """Verify presence of required columns."""
    missing = [col for col in config.REQUIRED_COLUMNS if col not in df.columns]
    extra = [col for col in df.columns if col not in config.REQUIRED_COLUMNS]
    result = {
        "missing_columns": {
            "issues": len(missing),
            "issue_values": missing[:10] + (["..."] if len(missing) > 10 else []),
            "issue_row_numbers": []
        },
        "extra_columns": {
            "issues": len(extra),
            "issue_values": extra[:10] + (["..."] if len(extra) > 10 else []),
            "issue_row_numbers": []
        },
        "column_count": {
            "issues": 0,
            "issue_values": [len(df.columns)],
            "issue_row_numbers": []
        }
    }
    if missing:
        logging.warning(f"Missing columns: {', '.join(missing)}")
    return result


def check_fields(df: pd.DataFrame) -> Dict[str, Any]:
    """Detect field-level issues (duplicates, empties, or malformed entries)."""
    issues = {}

    # --- Exact duplicate rows ---
    dup_exact_mask = df.duplicated(keep=False)
    vals, rows = sample_issues(df, dup_exact_mask)
    issues["exact_duplicates"] = {
        "issues": int(dup_exact_mask.sum()),
        "issue_values": [],
        "issue_row_numbers": rows
    }

    # --- Duplicate precinct identifiers ---
    if {"state", "county", "precinct"}.issubset(df.columns):
        dup_key_mask = df.duplicated(subset=["state", "county", "precinct"], keep=False)
        vals, rows = sample_issues(df, dup_key_mask, col="precinct")
        issues["duplicate_precincts"] = {
            "issues": int(dup_key_mask.sum()),
            "issue_values": vals,
            "issue_row_numbers": rows
        }

    # --- Negative or zero votes ---
    if "votes" in df.columns:
        votes_numeric = pd.to_numeric(df["votes"], errors="coerce")
        neg_mask = votes_numeric < 0
        vals, rows = sample_issues(df, neg_mask, col="votes")
        issues["negative_votes"] = {
            "issues": int(neg_mask.sum()),
            "issue_values": vals,
            "issue_row_numbers": rows
        }
        zero_mask = votes_numeric.eq(0)
        vals, rows = sample_issues(df, zero_mask, col="votes")
        issues["zero_vote_rows"] = {
            "issues": int(zero_mask.sum()),
            "issue_values": vals,
            "issue_row_numbers": rows
        }

    # --- Empty candidate names ---
    if "candidate" in df.columns:
        empty_mask = df["candidate"].astype(str).str.strip().eq("")
        vals, rows = sample_issues(df, empty_mask, col="candidate")
        issues["empty_candidates"] = {
            "issues": int(empty_mask.sum()),
            "issue_values": vals,
            "issue_row_numbers": rows
        }

    return issues


# ------------------------------------------------------------------
# Duplicate and Near-Duplicate Detection
# ------------------------------------------------------------------

def find_duplicate_rows(df: pd.DataFrame) -> pd.DataFrame:
    """
    Detect only two duplicate cases:
      1) exact_duplicate — all columns identical
      2) all_but_votes_duplicate — all columns identical except 'votes'

    Returns a DataFrame of flagged rows with 'dup_type' column.
    """
    if df.empty:
        return pd.DataFrame()

    out = []

    # 1) Exact duplicates
    exact_mask = df.duplicated(keep=False)
    exact_dups = df.loc[exact_mask].copy()
    if not exact_dups.empty:
        exact_dups["dup_type"] = "exact_duplicate"
        out.append(exact_dups)

    # 2) All-but-votes duplicates
    if "votes" in df.columns and len(df.columns) > 1:
        cols_no_votes = [c for c in df.columns if c != "votes"]
        no_votes_mask = df.duplicated(subset=cols_no_votes, keep=False)
        only_no_votes_mask = no_votes_mask & ~exact_mask
        if only_no_votes_mask.any():
            no_votes_dups = df.loc[only_no_votes_mask].copy()
            # Ensure same precinct across group
            if "precinct" in df.columns:
                g = no_votes_dups.groupby(cols_no_votes, dropna=False)
                keep_idx = g.filter(lambda x: x["precinct"].astype(str).fillna("").nunique() == 1).index
                no_votes_dups = no_votes_dups.loc[keep_idx]
            if not no_votes_dups.empty:
                no_votes_dups["dup_type"] = "all_but_votes_duplicate"
                out.append(no_votes_dups)

    if not out:
        return pd.DataFrame()

    result = pd.concat(out, ignore_index=True)
    result = result.sort_values(by=list(df.columns)).reset_index(drop=True)
    return result


def find_zero_vote_precincts(df: pd.DataFrame) -> pd.DataFrame:
    """
    Identify precinct-office (and related jurisdiction) groups whose aggregated
    vote totals are exactly zero. Groups by the following columns when present:
      ['county_fips','jurisdiction_fips','precinct','office','district']

    Returns a DataFrame with the grouping columns and a `votes_sum` column for
    groups where the sum of `votes` == 0. If required columns are missing,
    returns an empty DataFrame.
    """
    if df.empty:
        return pd.DataFrame()

    # Ensure votes column exists
    if "votes" not in df.columns:
        return pd.DataFrame()

    # Choose grouping columns that exist in the dataframe
    possible_groups = [
        "county_fips",
        "jurisdiction_fips",
        "precinct",
        "office",
        "district",
    ]
    group_cols = [c for c in possible_groups if c in df.columns]
    if not group_cols:
        return pd.DataFrame()

    # Coerce votes to numeric (non-numeric -> NaN -> treated as 0 for aggregation)
    votes = pd.to_numeric(df["votes"], errors="coerce").fillna(0)
    tmp = df.loc[:, group_cols].copy()
    tmp = tmp.assign(__votes_numeric=votes.values)

    grouped = tmp.groupby(group_cols, dropna=False)["__votes_numeric"].sum().reset_index()
    zero_groups = grouped[grouped["__votes_numeric"] == 0].copy()
    if zero_groups.empty:
        return pd.DataFrame()

    zero_groups = zero_groups.rename(columns={"__votes_numeric": "votes_sum"})
    return zero_groups
