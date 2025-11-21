"""
Module that contains precinct cleaning tools.
"""

import pandas as pd

from .. import miscellaneous, field

DataFrame = pd.core.frame.DataFrame
Series = pd.core.series.Series

class Precinct(field.Field):
    DEFAULT_SIMILARITIES = miscellaneous.GENERAL_SIMILARITIES
    DEFAULT_TEXT_CHECKS = {
        # Precincts have less text checks as they are meant to be kept as
        # close as possible to the original values.

        # Only allow values such that for spaces:
        # It is not the first or last character, nor followed by a space
        'EXTRANEOUS SPACES':
            r'(^ )|( $)',
        }
    SEARCH_DUPLICATES_IN_VALUES = False
    SEARCH_SIMILAR_IN_COLUMN = False
