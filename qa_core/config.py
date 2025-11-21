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
