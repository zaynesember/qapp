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
VALID_MODES = ["TOTAL","ELECTION DAY","ABSENTEE","PROVISIONAL","ONE-STOP"]
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
AUTO_OPEN_REPORT = True
