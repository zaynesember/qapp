"""
Module that contains candidate cleaning tools.
"""

import pandas as pd

from .. import miscellaneous, field

DataFrame = pd.core.frame.DataFrame
Series = pd.core.series.Series


class Candidate(field.Field):
    """
    Candidate field.
    """

    DEFAULT_SIMILARITIES = miscellaneous.merge_enums('CANDIDATE_SIMILARITIES',
                                                     miscellaneous.EMPTY_ENUM,)

    _suffixes = '((SR)|(JR)|(II)|(III)|(IV))'
    _valid_characters = r'A-Z0-9"\-\'\/%'
    DEFAULT_TEXT_CHECKS = {
        # Only allow English A-Z, 0-9 (for some numbers), " (for nicknames),
        # - (for double names), ' (for certain last names), spaces and /
        # (for multiple candidates)
        'UNRECOGNIZED CHARACTERS': rf'[^{_valid_characters} ]+',
        # Only allow candidates such that
        # It is either the empty string or a letter or number is the starting character
        # To check the former, if the string starts with a ", then it is invalid if
        # 1. It is the only character, or
        # 2. It is followed by anything other than ", or
        # 3. It is followed by a ", and then any character.
        'INVALID BEGINNING CHARACTERS':
            r'^\"($|[^\"]|\".+$)|^[^A-Z0-9\"]',
        # Only allow candidates such that
        # It is either the empty string or a letter or number is the ending character
        # To check the former, if the string ends with a ", then it is invalid if
        # 1. It is the only character, or
        # 2. It is preceded by anything other than ", or
        # 3. It is preceded by a ", which is then preceded by any character.
        'INVALID ENDING CHARACTERS':
            r'(^|[^\"]|.+\")\"$|[^A-Z0-9\"]$',
        # Only allow candidates such that for symbols:
        # There are no any conseuctive symbols, except the empty string
        'EXTRANEOUS CONSECUTIVE SYMBOLS':
            r'\"\".+|.+\"\"|\-\-|\'\'|  |\/\/',
        # Only allow candidates such that for spaces:
        # A dash does not precede or
        # A dash does not follow it, or if it does, it is not then followed by YES or NO
        'EXTRANEOUS SPACES':
            r'( -(?! ))|(- (?!(YES$|NO$|BLANK|OVERVOTES$|UNDERVOTES$|TOTAL)))',
        # Only allow candidates such that for quotation marks:
        # There is an even number of them
        'EXTRANEOUS QUOTATION MARKS':
            (r'^[^"]*"([^"]*"[^"]*")*[^"]*$'),

        # Possibly only allow candidates such that for single quotation marks:
        # There is only one
        '(POSSIBLY) EXTRANEOUS SINGLE QUOTATION MARKS':
            r".*'.*'.*",
        # Possibly only allow candidates such that for any suffix
        # They are not followed by a space
        '(POSSIBLY) SUFFIX NOT AT THE END':
            (rf'{_suffixes} '),

        '(POSSIBLY) INITIAL/MIDDLE NAME AFTER NICKNAME':
            (rf'" [{_valid_characters}]+'
             rf'( (?!{_suffixes}$)[{_valid_characters}]+)+'
             rf'{_suffixes}?$'),

        '(POSSIBLY) SUFFIX AFTER NICKNAME':
            rf'" {_suffixes}',
    }
