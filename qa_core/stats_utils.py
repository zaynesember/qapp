"""
stats_utils.py — Quantitative and distributional QA checks

Original QA engine by sbaltz.
Refactored and extended by Zayne (2025).
"""

from __future__ import annotations
import pandas as pd
import numpy as np
import logging
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
