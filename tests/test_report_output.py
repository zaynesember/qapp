import pandas as pd
import numpy as np
from qa_core import report


def make_sample_results(tmp_path):
    # Minimal results dict matching report expectations
    results = {}
    results["detected_state"] = {"state_po": "NH", "state_name": "New Hampshire", "state_fips": "33"}
    results["dataset_info"] = {"rows": 10, "columns": 5, "unique_counties": 2, "unique_jurisdictions": 1}

    # Field-level checks (will be merged into Field Checks)
    results["fields"] = {
        "negative_votes": {"issues": 1, "issue_values": ["-5"], "issue_row_numbers": [3]},
        "zero_vote_rows": {"issues": 2, "issue_values": ["0", "0"], "issue_row_numbers": [4, 5]},
        "exact_duplicates": {"issues": 2, "issue_values": [], "issue_row_numbers": [1, 2]},
    }

    # field_formats with a missingness check (should be skipped if missingness present)
    results["field_formats"] = {
        "party_simplified_missing": {"issues": 1, "issue_values": ["<EMPTY>"], "issue_row_numbers": [6]}
    }

    # Duplicates DataFrame: two identical rows -> exact_duplicate
    dup = pd.DataFrame([
        {"precinct": "P1", "office": "O1", "votes": 10, "dup_type": "exact_duplicate"},
        {"precinct": "P1", "office": "O1", "votes": 10, "dup_type": "exact_duplicate"},
    ])
    results["duplicates"] = dup

    # Unique values DataFrame with <EMPTY> marker first row for col 'foo'
    uniq = pd.DataFrame({"foo": ["<EMPTY>", "A", "B"], "bar": ["x", "y", ""]})
    results["unique_values"] = uniq

    # Vote Aggregation: a simple DataFrame that will be written to Vote Aggregation
    totals = pd.DataFrame([
        {"office": "US PRESIDENT", "candidate": "DONALD TRUMP", "party_simplified": "REPUBLICAN", "district": np.nan, "dataset_votes": 1000, "state_candidate": "Donald J Trump", "state_votes": 1010, "diff": -10, "present_in": "both"},
        {"office": "US PRESIDENT", "candidate": "JILL STEIN", "party_simplified": "OTHER", "district": np.nan, "dataset_votes": 50, "state_candidate": "Jill Stein", "state_votes": 50, "diff": 0, "present_in": "both"},
    ])
    results["statewide_totals"] = totals

    return results


def test_report_writes_expected_sheets_and_headers(tmp_path):
    results = make_sample_results(tmp_path)
    out = tmp_path / "report_test.xlsx"
    report.write_excel_report(results, out)

    xls = pd.ExcelFile(out)
    # Expected sheets
    expected = {"QA Summary", "Field Checks", "Vote Aggregation", "Duplicates", "Unique"}
    assert expected.issubset(set(xls.sheet_names))

    # Field Checks header order: Check, Variables first
    fc = pd.read_excel(out, sheet_name="Field Checks")
    assert list(fc.columns[:2]) == ["Check", "Variables"]

    # QA Summary contains failed-checks table columns 'Check Failed' and 'Failures'
    qs = pd.read_excel(out, sheet_name="QA Summary")
    cols = [c for c in qs.columns if str(c).strip() in ("Section", "Check Failed", "Failures")]
    assert set(cols) >= {"Section", "Check Failed", "Failures"}

    # Vote Aggregation headers may be provided either in human-friendly form
    # (when produced by the runner) or in raw snake_case form. Accept either.
    va = pd.read_excel(out, sheet_name="Vote Aggregation")
    header_options = {
        "Office": "office",
        "Candidate": "candidate",
        "Dataset Votes": "dataset_votes",
        "State Candidate": "state_candidate",
        "State Votes": "state_votes",
        "Difference": "diff",
    }
    for friendly, raw in header_options.items():
        assert (friendly in va.columns) or (raw in va.columns)

    # Unique sheet preserves <EMPTY> marker in first row of 'foo'
    uq = pd.read_excel(out, sheet_name="Unique")
    # Cell A1 (first column header row 0) contains '<EMPTY>' as first data row value
    assert uq.iloc[0, 0] == "<EMPTY>"

    # Duplicates sheet: first column should be 'duplicate_group', second 'dup_type'
    dup = pd.read_excel(out, sheet_name="Duplicates")
    assert dup.columns[0] == "duplicate_group"
    # second column may be 'dup_type'
    assert dup.columns[1] == "dup_type"
