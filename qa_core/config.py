"""
config.py — Global constants and configuration defaults

Original QA engine by sbaltz.
Refactored and extended by Zayne (2025).
"""

from __future__ import annotations
import pathlib

BASE_DIR = pathlib.Path(__file__).resolve().parents[1]
QA_OUTPUT_DIR = BASE_DIR / "output"

REQUIRED_COLUMNS = [
    "precinct","office","party_detailed","party_simplified",
    "mode","votes","county_name","county_fips","jurisdiction_name",
    "jurisdiction_fips","candidate","district","dataverse","year",
    "stage","state","special","writein","state_po","state_fips",
    "state_cen","state_ic","date","magnitude"
]

EMPTY_RECORD = ""
MISSING_TOKENS = ["", "NA", "N/A", "NULL", "nan"]
OUTLIER_THRESHOLD = 3.5
MIN_EXPECTED_ROWS = 10
REPORT_LINE_WIDTH = 80

VALID_STAGES = ["PRI","GEN","RUNOFF"]
VALID_MODES = ["TOTAL","ELECTION DAY","ABSENTEE","PROVISIONAL","ONE-STOP","EMERGENCY","FEDERAL/OVERSEAS"]
VALID_DATAVERSES = ["PRESIDENT","SENATE","HOUSE","STATE","LOCAL",""]
VALID_PARTY_SIMPLIFIED = ["DEMOCRAT","REPUBLICAN","LIBERTARIAN","OTHER","NONPARTISAN",""]
VALID_SPECIAL = ["TRUE","FALSE",""]

# When a single `state_po` value accounts for at least this fraction
# of non-empty `state_po` rows, consider it the dataset's dominant state
# for the purpose of detecting misfiled datasets. Default: 80%.
STATE_PO_DOMINANCE_THRESHOLD = 0.8

# Configurable markers that identify aggregate/summary rows which should be
# excluded from duplicate/mismatch detection. These are matched case-insensitively
# against text fields like `precinct`, `candidate`, and `office`. You can edit
# this list to add or remove markers specific to your datasets.
#
# Defaults include common markers and the tokens you requested.
AGGREGATE_MARKERS = [
    "COUNTY TOTALS",
    "COUNTY TOTAL",
    "MACHINE COUNT",
    "TOTAL",
    "TOTAL VOTES"
    "OVERVOTES",
    "UNDERVOTES",
    "VOID",
    "BLANK",
    "BLANKS",
]

# If True, attempt to open the generated Excel report using the OS default
# application after the report is written. Default False to avoid surprises
# in CI or headless environments. Set to True in local development if desired.
AUTO_OPEN_REPORT = False

# ---------------------------------------------------------------------
# Check Registry — maps check keys to their associated columns
# Used by the GUI to filter checks by variable and to enumerate available checks.
# Keys should match the keys used in runner.py's all_results dict.
# ---------------------------------------------------------------------
AVAILABLE_CHECKS = {
    # Structural checks
    "columns": {
        "label": "Column validation",
        "columns": [],  # applies to all columns
        "category": "structural",
    },
    # Field-level checks
    "fields": {
        "label": "Field checks (missing values, invalid entries)",
        "columns": [],  # applies to all columns
        "category": "fields",
    },
    "field_formats": {
        "label": "Field format validation (enumerated values)",
        "columns": ["party_simplified", "party_detailed", "mode", "stage", "dataverse", "special", "writein"],
        "category": "fields",
    },
    "field_regex_checks": {
        "label": "Regex/character format checks",
        "columns": [],  # applies to all text columns
        "category": "fields",
    },
    # FIPS/geographic checks
    "state_codes": {
        "label": "State/FIPS code validation",
        "columns": ["state_po", "state_fips", "state_cen", "state_ic", "county_fips", "jurisdiction_fips"],
        "category": "fips",
    },
    # Numeric checks
    "numerical": {
        "label": "Numeric consistency checks",
        "columns": ["votes", "magnitude"],
        "category": "numeric",
    },
    "distribution": {
        "label": "Vote distribution sanity checks",
        "columns": ["votes"],
        "category": "numeric",
    },
    # Duplicate detection
    "duplicates": {
        "label": "Duplicate/conflicting row detection",
        "columns": [],  # applies to all columns
        "category": "duplicates",
    },
    "zero_vote_precincts": {
        "label": "Zero-vote precinct groups",
        "columns": ["votes", "precinct", "office"],
        "category": "duplicates",
    },
    # Office mapping
    "office_mappings": {
        "label": "Office name validation",
        "columns": ["office"],
        "category": "office",
    },
    # Data summary
    "missingness": {
        "label": "Missingness summary",
        "columns": [],  # applies to all columns
        "category": "summary",
    },
    "statewide_totals": {
        "label": "Statewide vote totals",
        "columns": ["votes", "candidate", "office"],
        "category": "summary",
    },
    "unique_values": {
        "label": "Unique values per column",
        "columns": [],  # applies to all columns
        "category": "summary",
    },
}

# Categories for grouping checks in the GUI
CHECK_CATEGORIES = {
    "structural": "Structural Checks",
    "fields": "Field Checks",
    "fips": "FIPS/Geographic Checks",
    "numeric": "Numeric Checks",
    "duplicates": "Duplicate Detection",
    "office": "Office Validation",
    "summary": "Data Summary",
}


def get_checks_for_columns(columns: list[str]) -> list[str]:
    """Return check keys that apply to the given column(s)."""
    if not columns:
        return list(AVAILABLE_CHECKS.keys())
    
    matching = []
    columns_lower = [c.lower() for c in columns]
    for key, info in AVAILABLE_CHECKS.items():
        check_cols = info.get("columns", [])
        # If check has no specific columns, it applies to all
        if not check_cols:
            matching.append(key)
        # If any of the check's columns match the filter
        elif any(c.lower() in columns_lower for c in check_cols):
            matching.append(key)
    return matching
