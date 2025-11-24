import pandas as pd
import pytest

from qa_core import checks, config


def test_check_columns_missing_and_extra():
    # Create DataFrame missing several required columns and with an extra column
    df = pd.DataFrame({
        "precinct": ["A"],
        "votes": [10],
        "candidate": ["X"] ,
        "extra_col": [1]
    })
    res = checks.check_columns(df)
    assert isinstance(res, dict)
    assert "missing_columns" in res
    assert "extra_columns" in res
    assert res["extra_columns"]["issues"] >= 1


def test_check_fields_basic_issues():
    # duplicate row, negative vote, zero vote, empty candidate
    df = pd.DataFrame([
        {"state": "X", "county": "C1", "precinct": "P1", "votes": 5, "candidate": "A"},
        {"state": "X", "county": "C1", "precinct": "P1", "votes": 5, "candidate": "A"},
        {"state": "X", "county": "C1", "precinct": "P2", "votes": -3, "candidate": "B"},
        {"state": "X", "county": "C1", "precinct": "P3", "votes": 0, "candidate": ""},
    ])
    res = checks.check_fields(df)
    # Expect keys for exact duplicates, negative_votes, zero_vote_rows, empty_candidates
    assert res.get("exact_duplicates", {}).get("issues", 0) >= 2
    assert res.get("negative_votes", {}).get("issues", 0) >= 1
    assert res.get("zero_vote_rows", {}).get("issues", 0) >= 1
    assert res.get("empty_candidates", {}).get("issues", 0) >= 1


def test_find_duplicate_rows_variants():
    # exact duplicate and all_but_votes_duplicate
    df = pd.DataFrame([
        {"precinct": "P1", "office": "O", "votes": 10},
        {"precinct": "P1", "office": "O", "votes": 10},
        {"precinct": "P2", "office": "O", "votes": 5},
        {"precinct": "P2", "office": "O", "votes": 6},
    ])
    res = checks.find_duplicate_rows(df)
    assert not res.empty
    assert "dup_type" in res.columns
    types = set(res["dup_type"].tolist())
    assert "exact_duplicate" in types
    assert "all_but_votes_duplicate" in types


def test_find_zero_vote_precincts():
    df = pd.DataFrame([
        {"county_fips": "01", "precinct": "P1", "office": "O", "votes": 0},
        {"county_fips": "01", "precinct": "P1", "office": "O", "votes": 0},
        {"county_fips": "01", "precinct": "P2", "office": "O", "votes": 2},
    ])
    res = checks.find_zero_vote_precincts(df)
    assert not res.empty
    assert "votes_sum" in res.columns
