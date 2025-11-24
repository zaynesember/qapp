"""
stats_utils.py — Quantitative and distributional QA checks

Original QA engine by sbaltz.
Refactored and extended by Zayne (2025).
"""

from __future__ import annotations
import pandas as pd
import numpy as np
import logging
import pathlib
import difflib
from difflib import SequenceMatcher
from typing import Dict, Any
from qa_core import config


def run_numerical_checks(df: pd.DataFrame) -> Dict[str, Any]:
    """Basic numeric sanity checks on vote counts."""
    results = {}
    if "votes" not in df.columns:
        return {"error": "votes column missing"}

    votes = pd.to_numeric(df["votes"], errors="coerce")
    results["non_numeric_votes"] = int(votes.isna().sum())
    results["negative_votes"] = int((votes < 0).sum())
    results["max_votes"] = float(votes.max(skipna=True))
    results["min_votes"] = float(votes.min(skipna=True))
    return results


def vote_distribution_check(df: pd.DataFrame) -> Dict[str, Any]:
    """Identify precincts with implausible vote totals within each state."""
    if not {"state", "precinct", "votes"}.issubset(df.columns):
        return {"error": "required columns missing"}

    outliers = []
    for state, group in df.groupby("state"):
        votes = pd.to_numeric(group["votes"], errors="coerce").dropna()
        if len(votes) < config.MIN_EXPECTED_ROWS:
            continue

        median = np.median(votes)
        mad = np.median(np.abs(votes - median))
        if mad == 0:
            continue
        z_scores = np.abs((votes - median) / mad)
        n_out = int((z_scores > config.OUTLIER_THRESHOLD).sum())
        if n_out > 0:
            outliers.append({"state": state, "outlier_precincts": n_out})

    if not outliers:
        logging.info("No anomalous vote distributions detected.")
        return {"outlier_states": []}

    logging.warning(f"Vote-distribution anomalies detected in {len(outliers)} states.")
    return {"outlier_states": outliers}


def compare_with_state_level(totals_df: pd.DataFrame, help_dir: pathlib.Path, detected_state: dict | None = None, year_prefix: str | None = None) -> Dict[str, Any]:
    """Compare aggregated precinct totals (from `totals_df`) against state-level files in `help_dir`.

    Expects `totals_df` to contain rows for `US PRESIDENT` and `US SENATE` with columns
    including at least `office`, `candidate`, and `votes`.

    Returns a dict of checks keyed by office like `president_totals_match` and
    `senate_totals_match` where each check is a dict with `issues`,
    `issue_values` (list of candidate names with mismatches) and `details_df`
    (a DataFrame with side-by-side comparisons) when available.
    """
    results: Dict[str, Any] = {}
    if totals_df is None or totals_df.empty:
        return {"error": "No statewide totals available to compare"}

    # Helper to normalize candidate strings for matching and display
    def _normalize_candidate(s: str) -> tuple[str, str]:
        """
        Normalize candidate name and return (display_name, name_key).

        - Accepts formats like:
          'LAST, FIRST', 'LAST, FIRST M', 'FIRST LAST', 'FIRST M LAST', 'LAST'
        - display_name: a human-friendly 'First [Middle] Last' (title-cased)
          with original middle initials preserved when present.
        - name_key: uppercase canonical key used for matching: 'FIRST LAST'
          (drops middle names/initials to improve matching robustness).
        """
        try:
            import re
            s_in = str(s).strip()
            if not s_in:
                return "", ""

            # Remove parenthetical annotations and trailing punctuation
            s_in = re.sub(r"\(.*?\)", "", s_in).strip()
            # Remove periods in initials (e.g., 'D.' -> 'D')
            s_in = s_in.replace('.', '')

            # If candidate string contains conjunctions/joiners like '&', 'AND', '/'
            # (running-mates combined), take the left-most component as primary
            parts_join = re.split(r"\s*(?:&|AND|/)\s*", s_in, flags=re.IGNORECASE)
            if parts_join:
                s_in = parts_join[0].strip()

            # If comma present, assume 'LAST, FIRST [MIDDLE]'
            if "," in s_in:
                parts = [p.strip() for p in s_in.split(",")]
                last = parts[0]
                first_parts = parts[1].split()
                first = first_parts[0] if first_parts else ""
                middle = " ".join(first_parts[1:]) if len(first_parts) > 1 else ""
            else:
                tokens = [t for t in s_in.split() if t]
                if len(tokens) == 1:
                    # single token (e.g., 'SANDERS') — treat as last name only
                    first = ""
                    middle = ""
                    last = tokens[0]
                else:
                    first = tokens[0]
                    last = tokens[-1]
                    middle = " ".join(tokens[1:-1]) if len(tokens) > 2 else ""

            # Build display name: prefer First [Middle] Last when first present
            if first:
                display = " ".join([p for p in [first, middle, last] if p]).strip()
            else:
                # No first name detected; use last only
                display = last

            # Build name key for matching: FIRST + LAST (uppercase), drop middles
            key_parts = []
            if first:
                key_parts.append(first.upper())
            if last:
                key_parts.append(last.upper())
            name_key = " ".join(key_parts).strip()

            # Return display (title-cased) and key (upper-case)
            return (display.title(), name_key)
        except Exception:
            return (str(s).strip(), str(s).strip().upper())

    # Determine which state to check: prefer detected_state.state_po if provided
    state_po = None
    if isinstance(detected_state, dict):
        state_po = detected_state.get("state_po") or detected_state.get("state")
    # If not available, we won't filter the help file by state and will attempt
    # to match on any state rows (but prefer exact state match when possible).

    # Map office names to help file basenames; prefer year-specific filenames when provided
    def _choose_helpfile(office_key: str) -> pathlib.Path | None:
        # office_key is 'US PRESIDENT' or 'US SENATE'
        suffix = 'president-state.csv' if 'PRESIDENT' in office_key else 'senate-state.csv'
        # Preferred filename when year_prefix provided
        if year_prefix:
            cand = pathlib.Path(help_dir) / f"{year_prefix}-{suffix}"
            if cand.exists():
                return cand
        # Fallback: try any file matching '*-president-state.csv' or '*-senate-state.csv'
        matches = list(pathlib.Path(help_dir).glob(f"*-{suffix}"))
        if matches:
            # Prefer an exact match containing the year if available
            if year_prefix:
                for m in matches:
                    if str(year_prefix) in m.name:
                        return m
            return matches[0]
        return None

    office_map = {
        "US PRESIDENT": _choose_helpfile("US PRESIDENT"),
        "US SENATE": _choose_helpfile("US SENATE"),
    }

    for office, fname in office_map.items():
        help_path = office_map.get(office)
        check_name = ("president_totals_match" if office == "US PRESIDENT" else "senate_totals_match")
        if help_path is None or not pathlib.Path(help_path).exists():
            results[check_name] = {
                "issues": 0,
                "issue_values": [],
                "note": f"No help file found for {office}; skipping comparison",
            }
            continue

        try:
            hf = pd.read_csv(help_path, dtype=str)
        except Exception as e:
            results[check_name] = {"issues": 0, "issue_values": [], "note": f"Failed to read {fname}: {e}"}
            continue

        # Normalize and filter help file for the state if possible
        if state_po:
            hf_subset = hf.loc[hf['state_po'].astype(str).str.upper() == str(state_po).upper()].copy()
            if hf_subset.empty:
                # fallback to filtering by state name if available in detected_state
                stname = detected_state.get('state_name') if isinstance(detected_state, dict) else None
                if stname:
                    hf_subset = hf.loc[hf['state'].astype(str).str.upper() == str(stname).upper()].copy()
            hf = hf_subset if not hf_subset.empty else hf

        # Select help-file rows for this office and mode=TOTAL (or any mode if missing)
        hf_off = hf.loc[hf['office'].astype(str).str.strip().str.upper() == office].copy()
        if hf_off.empty:
            results[check_name] = {"issues": 0, "issue_values": [], "note": f"No {office} rows in {fname} for state"}
            continue

        # Normalize candidate names and numeric votes
        # Handle varied name orderings and produce a canonical display and key
        hf_off['candidate'] = hf_off['candidate'].fillna("")
        hf_norms = hf_off['candidate'].apply(_normalize_candidate)
        hf_off['candidate_display'] = hf_norms.apply(lambda t: t[0])
        hf_off['candidate_norm'] = hf_norms.apply(lambda t: t[1])
        # Some help files have 'votes' or 'totalvotes' columns; prefer 'votes'
        vote_col = 'votes' if 'votes' in hf_off.columns else ('totalvotes' if 'totalvotes' in hf_off.columns else None)
        if vote_col is None:
            results[check_name] = {"issues": 0, "issue_values": [], "note": f"No vote column found in {fname}"}
            continue
        hf_off['state_votes'] = pd.to_numeric(hf_off[vote_col], errors='coerce').fillna(0).astype(int)

        # Prepare dataset totals for this office
        ds_off = totals_df.loc[totals_df['office'].astype(str).str.strip().str.upper() == office].copy()
        if ds_off.empty:
            results[check_name] = {"issues": 0, "issue_values": [], "note": f"No {office} rows in dataset totals"}
            continue
        ds_off[['candidate_display', 'candidate_norm']] = ds_off['candidate'].fillna("").apply(lambda x: pd.Series(_normalize_candidate(x)))
        ds_off['dataset_votes'] = pd.to_numeric(ds_off['votes'], errors='coerce').fillna(0).astype(int)

        # Merge on normalized candidate keys
        merged = pd.merge(
            ds_off,
            hf_off[['candidate_norm', 'state_votes', 'candidate_display']],
            on='candidate_norm',
            how='outer',
            indicator=True,
        )

        # Fill NaNs with zeros for vote comparison
        merged['dataset_votes'] = merged['dataset_votes'].fillna(0).astype(int)
        merged['state_votes'] = merged['state_votes'].fillna(0).astype(int)
        merged['diff'] = merged['dataset_votes'] - merged['state_votes']

        # Attempt fuzzy matching for unmatched candidates (_merge != 'both')
        try:
            # Lists of candidate_norm on each side
            ds_names = ds_off['candidate_norm'].dropna().unique().tolist()
            hf_names = hf_off['candidate_norm'].dropna().unique().tolist()

            # Work on rows where merge is not 'both'
            unmatched_idx = merged[merged['_merge'] != 'both'].index.tolist()
            merged['suggested_match'] = ""
            merged['match_score'] = 0.0
            for idx in unmatched_idx:
                row = merged.loc[idx]
                cname = str(row.get('candidate_norm', '') or '')
                # If candidate exists in dataset side but not in state side,
                # try to find a close match in hf_names
                if row.get('_merge') == 'left_only' and cname:
                    matches = difflib.get_close_matches(cname, hf_names, n=1, cutoff=0.78)
                    if matches:
                        sug = matches[0]
                        score = SequenceMatcher(None, cname, sug).ratio()
                        merged.at[idx, 'suggested_match'] = sug
                        merged.at[idx, 'match_score'] = float(score)
                        # Pull in the state_votes from hf_off for the suggested match
                        try:
                            mv = int(hf_off.loc[hf_off['candidate_norm'] == sug, 'state_votes'].iloc[0])
                            merged.at[idx, 'state_votes'] = mv
                        except Exception:
                            pass
                # If candidate exists in state side but not dataset, try to find dataset match
                elif row.get('_merge') == 'right_only' and cname:
                    matches = difflib.get_close_matches(cname, ds_names, n=1, cutoff=0.78)
                    if matches:
                        sug = matches[0]
                        score = SequenceMatcher(None, cname, sug).ratio()
                        merged.at[idx, 'suggested_match'] = sug
                        merged.at[idx, 'match_score'] = float(score)
                        try:
                            mv = int(ds_off.loc[ds_off['candidate_norm'] == sug, 'dataset_votes'].iloc[0])
                            merged.at[idx, 'dataset_votes'] = mv
                        except Exception:
                            pass
        except Exception:
            # If fuzzy matching fails for any reason, continue with exact comparisons
            pass

        # Recompute diff after any suggested-match fills
        merged['dataset_votes'] = merged['dataset_votes'].fillna(0).astype(int)
        merged['state_votes'] = merged['state_votes'].fillna(0).astype(int)
        merged['diff'] = merged['dataset_votes'] - merged['state_votes']

        # Identify mismatches: non-zero difference OR candidate present only on one side
        mismatches = merged[(merged['diff'].abs() > 0) | (merged['_merge'] != 'both')]
        issues = len(mismatches)
        issue_vals = mismatches['candidate_norm'].fillna('').astype(str).tolist()[:20]

        # Prepare a friendly details DataFrame
        details_cols = ['candidate', 'dataset_votes', 'state_votes', 'diff', '_merge']
        # Try to choose human-friendly candidate name (from dataset when available)

        try:
            friendly = merged.copy()
            # Ensure an 'office' column exists for clarity in merged outputs
            friendly['office'] = office
            # After merge, dataset-side display will be in 'candidate_display_x' and
            # help-file display in 'candidate_display_y' (pandas suffixes)
            # Provide explicit columns for dataset and state display names so reviewers
            # can compare them side-by-side.
            if 'candidate_display_x' in friendly.columns:
                friendly['dataset_candidate'] = friendly['candidate_display_x']
            else:
                friendly['dataset_candidate'] = friendly.get('candidate_display')
            if 'candidate_display_y' in friendly.columns:
                friendly['state_candidate'] = friendly['candidate_display_y']
            else:
                # If right-side display wasn't present under that name, try to use
                # the merged 'candidate' column from help-file side
                friendly['state_candidate'] = friendly.get('candidate')

            # For backwards compatibility, keep a 'candidate' column (dataset display)
            friendly['candidate'] = friendly['dataset_candidate'].fillna(friendly.get('candidate_norm'))
            # Include candidate_norm, suggested_match, and match_score for review
            details_df = friendly[['office', 'candidate', 'dataset_candidate', 'state_candidate', 'candidate_norm', 'dataset_votes', 'state_votes', 'diff', 'suggested_match', 'match_score', '_merge']].rename(columns={'_merge': 'present_in'})
        except Exception:
            details_df = merged[['candidate_norm', 'dataset_votes', 'state_votes', 'diff', '_merge']].rename(columns={'candidate_norm': 'candidate', '_merge': 'present_in'})

        results[check_name] = {
            "issues": int(issues),
            "issue_values": issue_vals,
            "issue_row_numbers": [],
            "details_df": details_df,
        }

    return results
