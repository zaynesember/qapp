"""
data_summary.py — Dataset summaries and unique-value exports (v2.4)

Original QA engine by sbaltz.
Refactored and extended by Zayne (2025).
"""

from __future__ import annotations
import pandas as pd
import numpy as np
import pathlib
from typing import Dict, Any

MISSING_TOKENS = ["NULL", "NA", "NaN", "NAN", "None", "null", "na"]


def summarize_missingness(df: pd.DataFrame) -> Dict[str, Any]:
    """Summarize percent empty and alternate missing-value tokens per column."""
    summary = {}
    n_rows = len(df)
    for col in df.columns:
        empty_count = int(df[col].astype(str).eq("").sum())
        empty_pct = (empty_count / n_rows) * 100 if n_rows > 0 else 0.0
        alt_missing = int(df[col].astype(str).isin(MISSING_TOKENS).sum())
        summary[col] = {
            "missing_count": empty_count,
            "percent_empty": round(empty_pct, 2),
            "alt_missing_values": alt_missing,
        }
    return summary


def compute_statewide_totals(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate vote totals for major statewide offices and filter invalid rows."""
    required_cols = {"office", "candidate", "votes"}
    if not required_cols.issubset(df.columns):
        return pd.DataFrame()

    subset = df.copy()
    subset["office_norm"] = subset["office"].astype(str).str.strip().str.upper()
    subset = subset.loc[subset["office_norm"].isin({"US PRESIDENT", "GOVERNOR", "US SENATE", "US HOUSE"})]
    if subset.empty:
        return pd.DataFrame()

    if "writein" in subset.columns:
        subset = subset.loc[~subset["writein"].astype(str).str.strip().str.upper().eq("TRUE")]

    # Also exclude obvious write-in candidates (e.g., WRITE-IN, WRITE IN, SCATTERING)
    subset = subset.loc[~subset["candidate"].astype(str).str.strip().str.upper().str.contains(r"WRITE[- ]?IN|SCATTER", na=False)]

    bad_candidates = {
        "UNDERVOTES", "UNDERVOTE", "UNDER VOTE", "OVER VOTE", "OVERVOTE", "OVER VOTES", "OVERVOTES",
        "TOTAL", "VOTE TOTAL", "BLANKS", "TOTAL VOTES CAST", "TOTAL CAST VOTES", "BLANK BALLOTS",
        "BLANK BALLOT", "NO CANDIDATE", "CONTEST TOTAL"
    }
    subset = subset.loc[~subset["candidate"].astype(str).str.strip().str.upper().isin(bad_candidates)]

    subset["votes"] = pd.to_numeric(subset["votes"], errors="coerce")
    office_order = ["US PRESIDENT", "GOVERNOR", "US SENATE", "US HOUSE"]
    party_order = ["DEMOCRAT", "REPUBLICAN", "LIBERTARIAN"]

    results = []
    for office in office_order:
        office_subset = subset.loc[subset["office_norm"] == office]
        if office_subset.empty:
            continue
        group_cols = ["office", "candidate", "party_simplified"]
        if office == "US HOUSE" and "district" in office_subset.columns:
            group_cols.append("district")
        grouped = (
            office_subset.groupby(group_cols, dropna=False)["votes"]
            .sum(min_count=1)
            .reset_index()
        )
        grouped["office_order"] = office_order.index(office)
        results.append(grouped)

    if not results:
        return pd.DataFrame()

    totals = pd.concat(results, ignore_index=True)
    totals["party_norm"] = totals["party_simplified"].astype(str).str.strip().str.upper()
    totals["party_order"] = totals["party_norm"].apply(
        lambda p: party_order.index(p) if p in party_order else len(party_order)
    )

    sort_cols = ["office_order"]
    if "district" in totals.columns:
        sort_cols.append("district")
    sort_cols.extend(["party_order", "candidate"])
    totals = totals.sort_values(sort_cols).reset_index(drop=True)
    totals = totals.drop(columns=["office_order", "party_order", "party_norm"])
    return totals



from pathlib import Path
import pandas as pd
import warnings

def export_unique_values(df: pd.DataFrame, output_dir: Path) -> None:
    """
    Export a strict summary of unique jurisdiction, county, and precinct counts.
    All expected columns from the schema must be present.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "unique_values_summary.txt"

    expected_cols = {
        "state_po", "jurisdiction_name", "jurisdiction_fips",
        "county_name", "county_fips", "precinct"
    }

    missing = expected_cols - set(df.columns)
    if missing:
        warnings.warn(
            f"[QAPP] Missing expected columns in export_unique_values: {', '.join(sorted(missing))}"
        )

    with open(out_path, "w") as f:
        f.write("Unique Values Summary\n")
        f.write("=====================\n\n")

        # Global unique counts
        for col in df.columns:
            n_unique = df[col].nunique(dropna=True)
            f.write(f"{col}: {n_unique}\n")

        f.write("\nDetailed Breakdown by State (Strict Schema)\n")
        f.write("-------------------------------------------\n")

        if "state_po" not in df.columns:
            f.write("ERROR: Missing required column 'state_po'.\n")
            return

        # Compute strict per-state breakdown
        counts = (
            df.groupby("state_po", dropna=False)
            .agg(
                jurisdiction_count=("jurisdiction_name", lambda x: x.nunique(dropna=True)),
                county_count=("county_name", lambda x: x.nunique(dropna=True)),
                precinct_count=("precinct", lambda x: x.nunique(dropna=True))
            )
            .reset_index()
        )

        for _, row in counts.iterrows():
            state_po = str(row["state_po"]) if pd.notna(row["state_po"]) else "<EMPTY>"
            jurisdiction_count = int(row["jurisdiction_count"]) if pd.notna(row["jurisdiction_count"]) else 0
            county_count = int(row["county_count"]) if pd.notna(row["county_count"]) else 0
            precinct_count = int(row["precinct_count"]) if pd.notna(row["precinct_count"]) else 0

            f.write(f"State: {state_po}\n")
            f.write(f"    Jurisdictions: {jurisdiction_count}\n")
            f.write(f"    Counties: {county_count}\n")
            f.write(f"    Precincts: {precinct_count}\n\n")

    print(f"Unique values summary written to {out_path}")


