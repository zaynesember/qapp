"""
office_checks.py — validate `office` values against canonical mappings

This module provides a lightweight office-mapping validator. It attempts to
load an optional canonical office list from `help_files/office_mappings.csv`
(if present) otherwise falls back to a small heuristic canonical set.

Functions:
- validate_office_mappings(df, help_dir=None) -> dict
    Returns a dict with:
      - issues: count of distinct unmatched office strings
      - issue_values: list of top unmatched office strings (sample)
      - issue_rows: DataFrame of sample rows where office is unmatched
      - mapping_suggestions: dict of unmatched -> suggested canonical (if available)

"""
from __future__ import annotations
import pandas as pd
import pathlib
from typing import Dict, Any

DEFAULT_CANONICAL = [
    "US PRESIDENT",
    "GOVERNOR",
    "US SENATE",
    "US HOUSE",
    "STATE SENATE",
    "STATE HOUSE",
    "ATTORNEY GENERAL",
    "SECRETARY OF STATE",
    "TREASURER",
]


def _load_canonical(help_dir: pathlib.Path | None) -> pd.Series:
    """Return the built-in canonical office list.

    Per current project policy we only use the internal canonical set and
    do not load an external `help_files` list.
    """
    return pd.Series(DEFAULT_CANONICAL)


def _normalize_office(s: Any) -> str:
    try:
        return str(s).strip().upper()
    except Exception:
        return ""


def validate_office_mappings(df: pd.DataFrame, help_dir: pathlib.Path | None = None) -> Dict[str, Any]:
    """Validate office strings in `df`.

    Returns a dict summarizing unmatched office tokens and sample rows.
    """
    res: Dict[str, Any] = {"issues": 0, "issue_values": [], "issue_rows": pd.DataFrame(), "mapping_suggestions": {}}
    if "office" not in df.columns:
        return res

    canonical = _load_canonical(help_dir)
    canonical_set = set(canonical.dropna().tolist())

    offices = df["office"].fillna("").astype(str).str.strip()
    norm = offices.apply(_normalize_office)

    # Identify distinct observed office strings
    observed = pd.Series(norm.unique()).astype(str)
    unmatched = [o for o in observed if o and o not in canonical_set]

    if not unmatched:
        return res

    # Count frequency of unmatched
    counts = norm.value_counts().to_dict()
    unmatched_counts = {o: counts.get(o, 0) for o in unmatched}
    # Prepare issue_values as top N unmatched strings
    top_unmatched = sorted(unmatched_counts.items(), key=lambda kv: -kv[1])[:10]
    res["issues"] = sum(unmatched_counts.values())
    res["issue_values"] = [f"{k} × {v}" for k, v in top_unmatched]

    # Build sample rows for the top unmatched values
    samples = []
    for office_name, _ in top_unmatched:
        sample_rows = df[norm == office_name].head(5)
        if not sample_rows.empty:
            samples.append(sample_rows)

    if samples:
        res["issue_rows"] = pd.concat(samples, ignore_index=False)

    # Suggest mappings: first use light heuristics (startswith/contains),
    # then fall back to stdlib fuzzy matching (difflib) for near-misses. We
    # return the suggested canonical and the match score when available.
    import difflib
    suggestions = {}
    # small set of stopwords to ignore when doing token-based matching
    STOPWORDS = {"THE", "FOR", "OF", "AND", "TO", "A", "AN"}

    def _tokens(s: str) -> list[str]:
        parts = [p.strip() for p in s.split() if p.strip()]
        # remove common stopwords
        return [p for p in parts if p not in STOPWORDS]

    for o in unmatched:
        best = None
        # quick exact/startswith/contains heuristics (existing behavior)
        for c in canonical_set:
            if o == c:
                best = (c, 1.0)
                break
            if o.startswith(c) or c.startswith(o):
                best = (c, 0.95)
                break
            if c in o or o in c:
                best = (c, 0.9)
                break

        # If still not matched, try token-based overlap: prefer canonical
        # whose token set intersects observed tokens (ignoring stopwords).
        if not best:
            o_toks = set(_tokens(o))
            if o_toks:
                # compute token overlap ratios with each canonical
                best_tok = None
                best_overlap = 0.0
                for c in canonical_set:
                    c_toks = set(_tokens(c))
                    if not c_toks:
                        continue
                    inter = o_toks.intersection(c_toks)
                    # overlap score: 2*|intersection| / (|o_toks|+|c_toks|)
                    overlap_score = (2.0 * len(inter)) / (len(o_toks) + len(c_toks))
                    if overlap_score > best_overlap:
                        best_overlap = overlap_score
                        best_tok = c
                # if token overlap is substantial, accept as suggestion
                if best_tok and best_overlap >= 0.4:
                    # scale token score to be in a similar range to other heuristics
                    best = (best_tok, round(0.8 + best_overlap * 0.2, 2))

        # difflib fallback (keep conservative cutoff)
        if not best:
            close = difflib.get_close_matches(o, list(canonical_set), n=1, cutoff=0.7)
            if close:
                ratio = difflib.SequenceMatcher(None, o, close[0]).ratio()
                best = (close[0], round(ratio, 2))

        if best:
            suggestions[o] = {"suggested": best[0], "score": best[1]}
    res["mapping_suggestions"] = suggestions
    # expose raw unmatched counts for downstream reporting
    res["unmatched_counts"] = unmatched_counts

    return res
