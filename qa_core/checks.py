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


def check_mode_total_with_other_modes(df: pd.DataFrame) -> Dict[str, Any]:
    """Flag groups where `mode` contains 'TOTAL' plus other mode values.

    Legacy behavior (legacy/src/fields/mode.py): group by election attributes and
    look for mode-tuples where TOTAL co-occurs with other modes.
    """
    if df.empty:
        return {"issues": 0, "issue_values": [], "issue_row_numbers": []}
    if "mode" not in df.columns:
        return {"issues": 0, "issue_values": [], "issue_row_numbers": []}

    # Prefer the legacy grouping columns; use those that actually exist.
    preferred_group_cols = [
        "precinct",
        "office",
        "party_detailed",
        "county_name",
        "candidate",
        "district",
        "stage",
        "special",
        "date",
    ]
    group_cols = [c for c in preferred_group_cols if c in df.columns]
    if not group_cols:
        return {"issues": 0, "issue_values": [], "issue_row_numbers": []}

    mode_norm = df["mode"].astype(str).str.strip().str.upper()
    tmp = df.loc[:, group_cols].copy()
    tmp["__mode"] = mode_norm

    # Aggregate the set of modes per group.
    modes_by_group = tmp.groupby(group_cols, dropna=False)["__mode"].agg(lambda s: sorted({m for m in s if str(m).strip() != ""}))

    irregular = []
    row_numbers = []
    for attrs, modes in modes_by_group.items():
        # modes is a sorted list
        if "TOTAL" in modes and len(modes) > 1:
            irregular.append((attrs, modes))

    if not irregular:
        return {"issues": 0, "issue_values": [], "issue_row_numbers": []}

    # Sample up to 10 groups; record the first row number for each group for context.
    issue_values = []
    for attrs, modes in irregular[:10]:
        # attrs may be scalar if group_cols length==1
        if len(group_cols) == 1:
            attrs_tuple = (attrs,)
        else:
            attrs_tuple = tuple(attrs)
        attrs_dict = {group_cols[i]: attrs_tuple[i] for i in range(len(group_cols))}
        issue_values.append(f"modes={tuple(modes)} attrs={attrs_dict}")
        # Find first matching row index for this group
        mask = pd.Series(True, index=df.index)
        for c, v in attrs_dict.items():
            mask = mask & (df[c].astype(str) == str(v))
        if mask.any():
            row_numbers.append(int(df.index[mask][0]) + 1)

    return {
        "issues": int(len(irregular)),
        "issue_values": issue_values,
        "issue_row_numbers": row_numbers,
    }


def check_date_year_consistency(df: pd.DataFrame) -> Dict[str, Any]:
    """Check date↔year consistency.

    Legacy behavior (legacy/src/fields/date.py):
      - flag a date associated with multiple years
      - flag rows where date[:4] != year
    """
    if df.empty:
        return {"issues": 0, "issue_values": [], "issue_row_numbers": []}
    if "date" not in df.columns or "year" not in df.columns:
        return {"issues": 0, "issue_values": [], "issue_row_numbers": []}

    date_series = df["date"].astype(str).str.strip()
    year_series = df["year"].astype(str).str.strip()

    # Ignore empty dates/years
    nonempty = (date_series != "") & (year_series != "")
    if not nonempty.any():
        return {"issues": 0, "issue_values": [], "issue_row_numbers": []}

    # Build mapping date -> set(years)
    date_to_years: Dict[str, set[str]] = {}
    for d, y in zip(date_series[nonempty].tolist(), year_series[nonempty].tolist()):
        date_to_years.setdefault(d, set()).add(y)

    irregular_dates = []
    for d, years in date_to_years.items():
        # multiple years for one date
        if len(years) != 1:
            irregular_dates.append((d, sorted(years)))
            continue
        y = next(iter(years))
        # if date doesn't look like YYYY-..., still treat as irregular
        if len(d) < 4 or d[:4] != str(y):
            irregular_dates.append((d, [y]))

    if not irregular_dates:
        return {"issues": 0, "issue_values": [], "issue_row_numbers": []}

    issue_values = []
    issue_rows = []
    for d, years in irregular_dates[:10]:
        issue_values.append(f"{d}: {years}")
        # first row for this date
        mask = (date_series == d) & nonempty
        if mask.any():
            issue_rows.append(int(df.index[mask][0]) + 1)

    return {
        "issues": int(len(irregular_dates)),
        "issue_values": issue_values,
        "issue_row_numbers": issue_rows,
    }


def check_dataverse_office_relationships(df: pd.DataFrame) -> tuple[Dict[str, Any], Dict[str, pd.DataFrame]]:
    """Legacy-equivalent dataverse↔office diagnostics.

    Mirrors the core intent of legacy/src/fields/dataverse.py:
      - offices with an unexpected dataverse (for a small trusted mapping)
      - offices associated with multiple dataverses
      - list of court-related offices and their dataverse sets
      - (diagnostic) office -> number of associated counties

    Returns (summary_checks, detail_dfs).
    """
    summary: Dict[str, Any] = {}
    details: Dict[str, pd.DataFrame] = {}

    if df.empty or "office" not in df.columns or "dataverse" not in df.columns:
        return summary, details

    office_norm = df["office"].fillna("").astype(str).str.strip().str.upper()
    dataverse_norm = df["dataverse"].fillna("").astype(str).str.strip().str.upper()

    # Legacy's trusted mapping for a subset of offices.
    expected_office_to_dataverse = {
        "US PRESIDENT": "PRESIDENT",
        "US SENATE": "SENATE",
        "US HOUSE": "HOUSE",
        "STATE SENATE": "STATE",
        "STATE HOUSE": "STATE",
        "GOVERNOR": "STATE",
        "LIEUTENANT GOVERNOR": "STATE",
        "SECRETARY OF STATE": "STATE",
    }

    # (1) Unexpected dataverse for a trusted office
    trusted_mask = office_norm.isin(set(expected_office_to_dataverse.keys()))
    mismatch_mask = trusted_mask & dataverse_norm.ne(office_norm.map(expected_office_to_dataverse))
    mismatch_rows = df.index[mismatch_mask].to_series().add(1).tolist()
    mismatch_vals = []
    for idx in df.index[mismatch_mask][:10]:
        o = office_norm.loc[idx]
        d = dataverse_norm.loc[idx]
        mismatch_vals.append(f"{o}: expected {expected_office_to_dataverse.get(o,'')} got {d}")
    if mismatch_mask.any():
        summary["dataverse_office_mismatch"] = {
            "issues": int(mismatch_mask.sum()),
            "issue_values": mismatch_vals + (["..."] if int(mismatch_mask.sum()) > 10 else []),
            "issue_row_numbers": mismatch_rows[:10] + (["..."] if len(mismatch_rows) > 10 else []),
        }
    else:
        summary["dataverse_office_mismatch"] = {"issues": 0, "issue_values": [], "issue_row_numbers": []}

    # (2) Offices with multiple dataverses
    office_to_dv = pd.DataFrame({"office": office_norm, "dataverse": dataverse_norm}).groupby("office", dropna=False)["dataverse"].unique()
    multi = office_to_dv[office_to_dv.apply(lambda xs: len([x for x in xs if str(x).strip() != ""]) > 1)]
    if not multi.empty:
        issue_values = [f"{office}: {sorted([str(x) for x in dverses])}" for office, dverses in multi.head(10).items()]
        # First row for each office
        issue_rows = []
        for office in multi.index.tolist()[:10]:
            m = office_norm.eq(office)
            if m.any():
                issue_rows.append(int(df.index[m][0]) + 1)
        summary["office_multiple_dataverses"] = {
            "issues": int(len(multi)),
            "issue_values": issue_values + (["..."] if int(len(multi)) > 10 else []),
            "issue_row_numbers": issue_rows + (["..."] if int(len(multi)) > 10 else []),
        }

        # Detail sheet: full mapping
        details["Office to Dataverses"] = (
            multi.reset_index().rename(columns={"office": "Office", "dataverse": "Dataverses"})
        )
    else:
        summary["office_multiple_dataverses"] = {"issues": 0, "issue_values": [], "issue_row_numbers": []}

    # (3) Court-related offices
    court_tokens = {"COURT", "JUSTICE", "JUDGE"}
    court_mask = office_norm.apply(lambda s: any(t in s for t in court_tokens))
    if court_mask.any():
        court_map = (
            pd.DataFrame({"office": office_norm[court_mask], "dataverse": dataverse_norm[court_mask]})
            .groupby("office", dropna=False)["dataverse"].unique()
        )
        summary["court_offices_present"] = {
            "issues": int(len(court_map)),
            "issue_values": [f"{o}: {sorted([str(x) for x in dvs])}" for o, dvs in court_map.head(10).items()],
            "issue_row_numbers": [],
        }
        details["Court Offices"] = court_map.reset_index().rename(columns={"office": "Office", "dataverse": "Dataverses"})
    else:
        summary["court_offices_present"] = {"issues": 0, "issue_values": [], "issue_row_numbers": []}

    # (4) Office -> number of associated counties (diagnostic)
    if "county_name" in df.columns:
        county_norm = df["county_name"].fillna("").astype(str).str.strip()
        office_to_counties = (
            pd.DataFrame({"office": office_norm, "county_name": county_norm})
            .groupby("office", dropna=False)["county_name"]
            .nunique(dropna=True)
            .reset_index()
            .rename(columns={"office": "Office", "county_name": "Unique Counties"})
            .sort_values("Unique Counties", ascending=False)
            .reset_index(drop=True)
        )
        details["Office Counties"] = office_to_counties

    # Also provide a general dataverse -> offices sheet for browsing.
    dv_to_off = (
        pd.DataFrame({"dataverse": dataverse_norm, "office": office_norm})
        .groupby("dataverse", dropna=False)["office"]
        .unique()
        .reset_index()
        .rename(columns={"dataverse": "Dataverse", "office": "Offices"})
    )
    details["Dataverse to Offices"] = dv_to_off

    return summary, details


def check_similar_values_in_column(
    df: pd.DataFrame,
    column: str,
    cutoff: float = 0.92,
    max_unique: int = 300,
) -> Dict[str, Any]:
    """Find near-duplicate values within a single column.

    This approximates the legacy engine's fuzzy 'SIMILAR VALUES IN COLUMN'
    behavior. To keep runtime bounded on large files, it only runs when the
    column has <= max_unique unique non-empty values.
    """
    if df.empty or column not in df.columns:
        return {"issues": 0, "issue_values": [], "issue_row_numbers": []}

    import difflib

    s = df[column].fillna("").astype(str).str.strip()
    vals = sorted({v for v in s.tolist() if v != ""}, key=lambda x: (len(x), x))
    if len(vals) <= 1:
        return {"issues": 0, "issue_values": [], "issue_row_numbers": []}
    if len(vals) > max_unique:
        return {
            "issues": 0,
            "issue_values": [f"Skipped: {len(vals)} unique values (limit {max_unique})"],
            "issue_row_numbers": [],
        }

    seen_pairs = set()
    examples = []
    example_rows = []

    # Use difflib to find closest matches; keep deterministic ordering.
    for v in vals:
        matches = difflib.get_close_matches(v, vals, n=3, cutoff=cutoff)
        for m in matches:
            if m == v:
                continue
            a, b = (v, m) if v < m else (m, v)
            if (a, b) in seen_pairs:
                continue
            ratio = difflib.SequenceMatcher(None, a, b).ratio()
            if ratio < cutoff:
                continue
            seen_pairs.add((a, b))
            if len(examples) < 10:
                examples.append(f"{a} ~ {b} (score={ratio:.2f})")
                # First row for 'a'
                mask = s.eq(a)
                if mask.any():
                    example_rows.append(int(df.index[mask][0]) + 1)

    if not seen_pairs:
        return {"issues": 0, "issue_values": [], "issue_row_numbers": []}

    return {
        "issues": int(len(seen_pairs)),
        "issue_values": examples + (["..."] if len(seen_pairs) > 10 else []),
        "issue_row_numbers": example_rows + (["..."] if len(seen_pairs) > 10 else []),
    }


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

    # Exclude obvious aggregate/summary rows from duplicate detection. These
    # often contain markers like 'COUNTY TOTALS' or 'MACHINE COUNT' in key
    # text fields and should not be treated as duplicates.
    # Use configurable aggregate markers from config. Normalize to uppercase
    # for case-insensitive matching.
    markers = set([str(m).strip().upper() for m in getattr(config, "AGGREGATE_MARKERS", [])])
    def _is_aggregate_row(df):
        # These markers typically appear in the `candidate` column to indicate
        # that a row is an aggregated total or statistical adjustment. Use the
        # `candidate` column by default; if it's missing, fall back to `office`.
        cols_to_check = [c for c in ("candidate", "office") if c in df.columns]
        if not cols_to_check:
            return pd.Series([False] * len(df), index=df.index)
        masks = []
        for c in cols_to_check:
            # normalize cell values to uppercase and strip before membership test
            masks.append(df[c].astype(str).str.strip().str.upper().isin(markers))
        combined = masks[0]
        for m in masks[1:]:
            combined = combined | m
        return combined

    agg_mask = _is_aggregate_row(df)
    df_work = df.loc[~agg_mask].copy()

    # 1) Exact duplicates (excluding aggregate rows)
    exact_mask = df_work.duplicated(keep=False)
    exact_dups = df_work.loc[exact_mask].copy()
    if not exact_dups.empty:
        exact_dups["dup_type"] = "exact_duplicate"
        out.append(exact_dups)

    # 2) All-but-votes duplicates
    if "votes" in df.columns and len(df.columns) > 1:
        cols_no_votes = [c for c in df.columns if c != "votes"]
        no_votes_mask = df_work.duplicated(subset=cols_no_votes, keep=False)
        only_no_votes_mask = no_votes_mask & ~exact_mask
        if only_no_votes_mask.any():
            no_votes_dups = df_work.loc[only_no_votes_mask].copy()
            # Ensure same precinct across group
            if "precinct" in df_work.columns:
                g = no_votes_dups.groupby(cols_no_votes, dropna=False)
                keep_idx = g.filter(lambda x: x["precinct"].astype(str).fillna("").nunique() == 1).index
                no_votes_dups = no_votes_dups.loc[keep_idx]
            if not no_votes_dups.empty:
                no_votes_dups["dup_type"] = "all_but_votes_duplicate"
                out.append(no_votes_dups)

    # 3) Precincts with conflicting county identifiers (same precinct+county, different county_fips or county_name)
    if "precinct" in df_work.columns and ("county_fips" in df_work.columns or "county_name" in df_work.columns):
        # Group by precinct AND county to find actual conflicts (not just duplicate precinct names across counties)
        if "county_fips" in df_work.columns:
            group_cols = ["precinct", "county_fips"]
        else:
            group_cols = ["precinct", "county_name"]
        g = df_work.groupby(group_cols, dropna=False)
        conflict_idx = []
        for name, grp in g:
            # Within the same precinct+county, check if county_name varies (when grouping by fips)
            # or if county_fips varies (when grouping by name)
            if "county_fips" in group_cols and "county_name" in grp.columns:
                if grp["county_name"].astype(str).nunique(dropna=True) > 1:
                    conflict_idx.extend(grp.index.tolist())
            elif "county_name" in group_cols and "county_fips" in grp.columns:
                if grp["county_fips"].astype(str).nunique(dropna=True) > 1:
                    conflict_idx.extend(grp.index.tolist())
        if conflict_idx:
            pc_conf = df_work.loc[sorted(set(conflict_idx))].copy()
            pc_conf["dup_type"] = "precinct_county_mismatch"
            out.append(pc_conf)

    # 4) Same candidate appearing under multiple office/dataverse combinations
    if "candidate" in df_work.columns and ("office" in df_work.columns or "dataverse" in df_work.columns):
        cg = df_work.groupby("candidate", dropna=False)
        cand_conf_idx = []
        for name, grp in cg:
            # skip empty candidate labels
            if str(name).strip() == "":
                continue
            if "office" in grp.columns and grp["office"].astype(str).nunique(dropna=True) > 1:
                cand_conf_idx.extend(grp.index.tolist())
            elif "dataverse" in grp.columns and grp["dataverse"].astype(str).nunique(dropna=True) > 1:
                cand_conf_idx.extend(grp.index.tolist())
        if cand_conf_idx:
            cand_conf = df_work.loc[sorted(set(cand_conf_idx))].copy()
            cand_conf["dup_type"] = "candidate_office_dataverse_mismatch"
            out.append(cand_conf)

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
