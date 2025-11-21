"""
Module for votes cleaning tools.
"""

import pandas as pd

from .. import field

DataFrame = pd.core.frame.DataFrame
Series = pd.core.series.Series

class Votes(field.Field):
    DEFAULT_TEXT_CHECKS = {
        # Only allow 0-9 (for some numbers) and - (for negative votes, which indicates some
        # sort of problem with the original data)
        'UNRECOGNIZED CHARACTERS': r'[^0-9\-]+',
        # Only allow negative signs in a value such that
        # 1. They are at the start of the number
        # 2. They are followed by a digit other than 0
        'UNRECOGNIZED NEGATIVE SIGNS': r'((?<!^)\-)|(\-[^1-9])',
        # Only allow numbers that start with digit 0 if the number is exactly zero
        'UNRECOGNIZED LEADING ZEROS': r'^0[^$]',
        # Warn the user if negative values are put. Sometimes these are unintended
        '(POSSIBLY) INVALID NEGATIVE VALUES': r'^-[1-9]',
        }
    SEARCH_DUPLICATES_IN_VALUES = False
    SEARCH_SIMILAR_IN_COLUMN = False