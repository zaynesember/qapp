import pandas as pd
import tempfile
import pathlib
from qa_core import stats_utils


def test_run_numerical_checks_and_vote_distribution():
    # Numerical checks: include non-numeric and negative values
    df = pd.DataFrame({
        "votes": ["10", "-5", "abc", "100", "15", "12", "11", "10", "9", "8", "7", "6"] ,
        "state": ["S"] * 12,
        "precinct": [f"p{i}" for i in range(12)]
    })
    num = stats_utils.run_numerical_checks(df)
    assert isinstance(num, dict)
    assert num.get("non_numeric_votes") >= 1
    assert num.get("negative_votes") >= 1

    # Vote distribution: create an outlier that should be detected (MAD)
    dist_res = stats_utils.vote_distribution_check(df)
    assert isinstance(dist_res, dict)


def test_compare_with_state_level(tmp_path: pathlib.Path):
    # Build totals_df representing aggregated dataset totals
    totals_df = pd.DataFrame([
        {"office": "US PRESIDENT", "candidate": "DONALD TRUMP", "votes": 1000},
        {"office": "US PRESIDENT", "candidate": "JILL STEIN", "votes": 50},
    ])

    # Create a temporary help_files CSV for 2024-president-state.csv
    help_dir = tmp_path
    hf = pd.DataFrame([
        {"state_po": "NH", "office": "US PRESIDENT", "candidate": "Donald J Trump", "votes": "1010"},
        {"state_po": "NH", "office": "US PRESIDENT", "candidate": "Jill Stein", "votes": "50"},
    ])
    hf_path = help_dir / "2024-president-state.csv"
    hf.to_csv(hf_path, index=False)

    detected_state = {"state_po": "NH"}
    res = stats_utils.compare_with_state_level(totals_df, help_dir, detected_state=detected_state, year_prefix="2024")
    assert isinstance(res, dict)
    assert "president_totals_match" in res
    entry = res["president_totals_match"]
    assert "details_df" in entry
    details = entry["details_df"]
    assert "state_candidate" in details.columns
    # There should be at least one mismatch row where diff != 0 (Trump 1000 vs 1010)
    assert any(details["diff"].abs() > 0)
