"""
Module that contains general purpose cleaning methods.
"""

import re
from enum import Enum
from typing import Any, Callable, List, Set, Union

import numpy as np
import pandas as pd

DataFrame = pd.core.frame.DataFrame
Series = pd.core.series.Series

__all__ = (
    'EMPTY_RECORD',
    'GENERAL_SIMILARITIES',
    'r_bool',
    'series_r_bool',
    'iif',
    'left_merge_series',
    'split_column',
    'merge_columns',
    'adapt_column',
    'fix_ordinals',
    'merge_enums',
    'obtain',
    )

EMPTY_RECORD = '<<<EC: VALUE WAS EMPTY>>>'


class EMPTY_ENUM(Enum):
    EMPTY = {}
    EXACT_EMPTY = {
        EMPTY_RECORD,
        }


class Scalar:
    def __init__(self, value):
        if not pd.api.types.is_scalar(value):
            raise ValueError(f'Expected Pandas scalar, found {value}.')
        self.value = value


class GENERAL_SIMILARITIES(Enum):
    MUNICIPALITY = {
        'CITY',
        'TOWN',
        'TW',
        'CTY',
        'TWNSH',
        'VILLAGE',
        }

    COUNTY = {
        'CO ',
        'COUNTY',
        'CTY',
        }

    REFERENDA = {
        'PROP',
        'QUESTION',
        'REFEREN',
        'ISSUE',
        'LEVY',
        'TAX',
        'AMEND',
        'CONSTITUTION',
        'MEASURE',
        'BOND',
        'CHARTER',
        'BILL',
        }

    REGISTRATION = {
        'REGISTRATION',
        'REGISTERED',
        'TURNOUT',
        'VOTERS',
        }

    BALLOTS = {
        'BALLOTS',
        'VOTES',
        'CARD',
        }

    OVERVOTES = {
        'OVER VOTE',
        'OVERVOTE',
        }

    UNDERVOTES = {
        'UNDER VOTE',
        'UNDERVOTE',
        }

    MAGNITUDE = {
        'VOTE',
        'ELECT',
        'CHOOSE',
        'TO BE ELECTED',
        }

    LENGTH = {
        'YEAR',
        'TERM',
        'YR',
        'EXPIRE',
        'YEAR',
        'Y TERM',
        'EXP',
        'UNEXPIRED',
        }

    VACANCIES = {
        'VACANT',
        'VACANCY',
        }

    RETENTION = {
        'RETENTION',
        'RETAIN',
        }

    RECALL = {
        'RECALL',
    }

    DISTRICT = {
        'DISTRICT',
        'DIST',
        'CD',
        'CG',
        'AT-LARGE',
        'AT LARGE',
        }

    WARD = {
        'WARD',
        'WD',
        }

    AREA = {
        'AREA',
        }

    SEAT = {
        'SEAT',
        }

    DIVISION = {
        'DIV ',
        'DIVISION',
    }

    POSITION = {
        'POS ',
        'POSITION',
    }

    GROUP = {
        'GROUP',
    }

    PRECINCT = {
        'PRECINCT',
        'PCT',
        'WARD',
        'WD',
        }

    PARTY = {
        'DEMOCRAT',
        'DEM',
        'REPUBLICAN',
        'REP',
        'GREEN',
        'GRN',
        'LIBERTARIAN',
        'LIB',
        'INDEPENDENT',
        'IND',
        'NO PARTY',
        'NP',
        'PARTISAN',
        }

    TOTAL = {
        'TOTAL',
        'STATISTICS',
        }

    BLANK = {
        'BLANK',
        }

    EMPTY = {
        'UNAVAIL',
        }

    EXACT_EMPTY = {
        '',
        'NA',
        'NAN',
        ' ',
        '""',
        EMPTY_RECORD,  # Internal id for datasets with empties
        }

    MODE = {
        'ELECTION',
        'ABS',
        'MAIL',
        'EARLY',
        'PROV',
        'POLL',
        'TOTAL',
        'ONE STOP',
        'MACHINE',
        'CENTER',
        }

    ELECTION_TYPE = {
        'SPECIAL',
        'RUN-OFF',
        'PRIM',
        'PRES',
        'RECOUNT',
        'RUNOFF',
        }


def _check_regex(regex: str) -> None:
    """
    Checks if a regex can be compiled and is valid.
    If so, do nothing. Otherwise, raise a ValueError indicating the error.

    Parameters
    ----------
    regex : str
        Regex to test.

    Raises
    ------
    ValueError
        If the regex cannot be compiled or is otherwise invalid.

    Returns
    -------
    None.

    Examples
    --------
    >>> _check_regex(r'')
    >>> _check_regex(r'(')
    ValueError: Invalid regex (: missing ), unterminated subpattern at position 0
    """

    try:
        re.compile(regex)
    except re.error as exc:
        err = f'Invalid regex {regex}: {exc}'
        raise ValueError(err)


def r_bool(boolean: bool) -> str:
    """
    Convert a Python True/False to strings 'TRUE'/'FALSE' supported by R.

    Parameters
    ----------
    boolean : bool
        Boolean to convert.

    Returns
    -------
    str
        Converted boolean.

    Raises
    ------
    ValueError
        If `boolean` is not a Python boolean.

    Examples
    --------
    >>> r_bool(True)
    'TRUE'
    >>> r_bool(False)
    'FALSE'
    >>> r_bool(None)
    ValueError: Unrecognized value None (expected bool, found NoneType).
    >>> r_bool(1)
    ValueError: Unrecognized value 1 (expected bool, found int).
    """

    if boolean is True:
        return 'TRUE'
    if boolean is False:
        return 'FALSE'
    raise ValueError(f'Unrecognized value {boolean} (expected bool, found '
                     f'{type(boolean).__name__}).')


def series_r_bool(series: Series) -> Series:
    """
    Return the original series, but with all Python True and False entries replaced with
    their R equivalents of 'TRUE' and 'FALSE'. Any other entries are left unmodified.

    This method does not mutate the input series.

    Parameters
    ----------
    series : pandas.core.series.Series
        Series.

    Returns
    -------
    pandas.core.series.Series
        Series with R TRUE/FALSE.

    Examples
    --------
    >>> import pandas as pd
    >>> df = pd.DataFrame({
        1: [True, False, 'TRUE', 'FALSE', 'True', 'False'],
        2: [None, 1, False, False, '', True]
        })
    >>> series_r_bool(df[1])
    0     TRUE
    1    FALSE
    2     TRUE
    3    FALSE
    4     True
    5    False
    Name: 1, dtype: object
    >>> series_r_bool(df[2])
    0     None
    1     TRUE
    2    FALSE
    3    FALSE
    4
    5     TRUE
    Name: 2, dtype: object
    >>> df[1]
    0     True
    1    False
    2     TRUE
    3    FALSE
    4     True
    5    False
    Name: 1, dtype: object
    >>> df[2]
    0     None
    1        1
    2    False
    3    False
    4
    5     True
    Name: 2, dtype: object
    """

    return series.replace({
        True: r_bool(True),
        False: r_bool(False),
        })


def iif(series: Series, cond: Callable[[Series, ], Series],
        if_true: Union[Series, Scalar], if_false: Union[Series, Scalar]) -> Series:
    """
    Return a new series with the same index as `series`, such that for every `i` in the index of
    `series`, the entry at index `i` of the output series `output` satisfies the following:\n
    * If `cond(series)[i] == True`, then `output[i]` is equal to `if_true[i]` if `if_true` is
      a Pandas series, and `if_true` if it is a Pandas scalar.\n
    * If `cond(series)[i] == False`, then `output[i]` is equal to if_false[i]` if `if_false` is
      a Pandas series, and `if_false` if it is a Pandas sacalar.

    Output is equivalent to `series.mask(cond(series), if_true).where(cond(series), if_false)`.

    This method does not mutate `series`.

    iif stands for "inline if", which is equivalent to the Python ternary construct
    "a if b else c".

    Parameters
    ----------
    series : Series
        Original series.
    cond : Callable[[Series, ], Series]
        Condition to apply to the series.
    if_true : Union[Series, Scalar]
        Values to use wherever the series operated on returns True.
    if_false : Union[Series, Scalar]
        Values to use wherever the series operated on returns False.

    Returns
    -------
    Series
        Inline if series.

    Examples
    --------
    >>> import pandas as pd
    >>> df = pd.DataFrame({
        'Student': ['Alyssa P. Hacker', 'Ben Bitdiddle', 'Cy D. Fect', 'Eva Lu Ator'],
        'Grade': [90, 40, 60, 59]
        })
    >>> df
                Student  Grade
    0  Alyssa P. Hacker     90
    1     Ben Bitdiddle     40
    2        Cy D. Fect     60
    3       Eva Lu Ator     59
    >>> iif(df['Grade'], lambda value: value >= 60, 'PASS', 'FAIL')
    0    PASS
    1    FAIL
    2    PASS
    3    FAIL
    Name: Grade, dtype: object
    >>> df['Leeway Grade'] = iif(df['Grade'], lambda value: value < 60, df['Grade']+3, df['Grade'])
    >>> df['Leeway Grade']
    0    90
    1    43
    2    60
    3    62
    Name: Leeway Grade, dtype: int64
    >>> df['Final Grade'] = iif(df['Leeway Grade'], lambda value: value >= 60, 'PASS', 'FAIL')
    >>> df
                Student  Grade  Leeway Grade Final Grade
    0  Alyssa P. Hacker     90            90        PASS
    1     Ben Bitdiddle     40            43        FAIL
    2        Cy D. Fect     60            60        PASS
    3       Eva Lu Ator     59            62        PASS
    """

    condition = cond(series)
    output = series.mask(condition, if_true)
    output = output.where(condition, if_false)
    return output


def left_merge_series(to_merge: List[Series] = None,
                      empty_values: Set[Any] = None) -> Series:
    """
    Left merge a list of Panda series as follows: if output_series begins as an
    empty Panda series:\n
    * For every i in 0, ..., len(to_merge)-1:\n
      * For every j in 0, ..., max(len(output_series, to_merge[i])):\n
        * Create output_series[j] if needed and set it to NaN, nan from the numpy library.
        * Set output_series[j] to to_merge[i][j] if to_merge[i][j] is not an empty value as\
        defined in empty_values, otherwise keep it as is.\n
    * Return output_series.

    In particular, for `i, k` such that `0 <= i < len(to_merge)`, the entry at index `k` of
    `output_series` will be `to_merge[i][k]` if:\n
    * `to_merge[i][k]` is not nan from the numpy library and not in the set `empty_values`, and\n
    * `to_merge[j][k]` is nan from the numpy library or in the set `empty_values` for all values\
       of `j` where `i <= j < len(to_merge)`.

    Parameters
    ----------
    to_merge : List of pandas.core.series.Series, optional
        List of series to left merge. The default is None, which is converted
        to an empty list.
    empty_values : Set of any, optional
        Set of values that are considered as empty values. The default is
        None, which is converted to an empty set. Regardless of the original
        value of empty_values, NaN (nan from the numpy library) will always
        be considered an empty value.

    Returns
    -------
    pandas.core.series.Series
        Left merged series as described.

    Examples
    --------
    >>> import numpy as np
    >>> import pandas as pd
    >>> df = pd.DataFrame({
        1: [1, np.nan, 3, np.nan, np.nan],
        2: ["A", "B", np.nan, np.nan, ""],
        3: ["a", "b", "c", "d", "e"]
        })
    >>> df
         1    2  3
    0  1.0    A  a
    1  NaN    B  b
    2  3.0  NaN  c
    3  NaN  NaN  d
    4  NaN       e
    >>> left_merge_series([df[1], df[2]])
    0      A
    1      B
    2    3.0
    3    NaN
    4
    Name: 2, dtype: object
    >>> left_merge_series([df[2], df[1]])
    0      A
    1      B
    2    3.0
    3    NaN
    4
    Name: 2, dtype: object
    >>> left_merge_series([df[3], df[2], df[1]])
    0    1.0
    1      B
    2    3.0
    3      d
    4
    Name: 1, dtype: object
    >>> left_merge_series([df[3], df[2], df[1]], empty_values={''})
    0    1.0
    1      B
    2    3.0
    3      d
    4      e
    Name: 1, dtype: object
    """

    if not to_merge:
        return pd.Series(dtype=object)

    if empty_values is None:
        empty_values = set()
    empty_values = empty_values | {np.nan}  # Do not modify the original set
    merged_series = to_merge[0].copy()

    for series in to_merge[1:]:
        merged_series = series.mask(
            lambda _series: _series.isin(empty_values), merged_series)
    return merged_series


def split_column(data: DataFrame, column_to_split: str, splitting_regex: str,
                 maintaining_columns: List[str] = None,
                 empty_value: Any = np.nan) -> DataFrame:
    """
    Return the original Panda dataframe `data` but with n new columns, where n
    is the number of regex groups in `splitting_regex`, that correspond to
    extracting the contents of column `column_to_split` based on how they fully
    match a regex string `splitting_regex`. The name of the new columns
    correspond to the names of the groups in the regex.

    If one cell value does not match the regex, it will be replicated as is in
    all columns listed in `maintaining_columns`, and as `empty_value`
    in the remaining columns.

    This method does not mutate the original dataframe.

    Parameters
    ----------
    data : pandas.core.frame.DataFrame
        Panda dataframe to inspect.
    column_to_split : str
        Column to split.
    splitting_regex : str
        Regular expression to use to split the column contents.
    maintaining_columns : list of str, optional
        Columns where cell values in `column_to_split` that do not fully match
        the splitting regex will be replicated. Defaults to None and converted
        to an empty list: that is, no columns will replicate unmatched values.
    empty_value: Any, optional
        "Empty" value to put in every column other than the ones in
        `maintaining_columns` when a cell value in `column_to_split` does not
        fully match the splitting regex. Defaults to None and converted to nan,
        the Numpy Not-a-Number.

    Returns
    -------
    pandas.core.frame.DataFrame
        Panda dataframe with split columns.

    Examples
    --------
    >>> import pandas as pd
    >>> df = pd.DataFrame({
        'Username': ['Alice123', 'Bob45', '789Carol', 'Dan'],
        'Password': ['password', '12345', '100', 'admin']
        })
    >>> df
       Username  Password
    0  Alice123  password
    1     Bob45     12345
    2  789Carol       100
    3       Dan     admin
    >>> split_column(df, 'Password', r'(?P<firstFour>.{4})(?P<remaining>.*)')
       Username  Password firstFour remaining
    0  Alice123  password      pass      word
    1     Bob45     12345      1234         5
    2  789Carol       100       NaN       NaN
    3       Dan     admin      admi         n
    >>> split_column(df, 'Username', r'(?P<Username>[A-Za-z]+)(?P<id>\d+)',
                     maintaining_columns=['Username'], empty_value=0)
       Username  Password   id
    0     Alice  password  123
    1       Bob     12345   45
    2  789Carol       100    0
    3       Dan     admin    0
    >>> df
       Username  Password
    0  Alice123  password
    1     Bob45     12345
    2  789Carol       100
    3       Dan     admin

    """

    _check_regex(splitting_regex)
    if maintaining_columns is None:
        maintaining_columns = list()

    new_data = data.copy()
    if column_to_split not in new_data.columns:
        err = f'{column_to_split} is not a column of the dataframe and thus cannot be split.'
        raise ValueError(err)
    for column_name in maintaining_columns:
        if column_name not in new_data.columns:
            err = f'{column_name} is not a column of the dataframe and thus cannot be maintained.'
            raise ValueError(err)

    temp_na = object()
    new_data = new_data.fillna(value=temp_na)

    # Add start and end anchors to enforce full matches.
    # For both need to check if splitting_regex is empty before adding.
    if splitting_regex and splitting_regex[0] != '^':
        splitting_regex = '^' + splitting_regex
    if splitting_regex and splitting_regex[-1] != '$':
        splitting_regex += '$'

    if re.compile(splitting_regex).groups:
        extracted = new_data[column_to_split].str.extract(splitting_regex)
    else:
        extracted = pd.DataFrame()

    for column_name in extracted.columns:
        if column_name in maintaining_columns:
            non_match_replacement = new_data[column_name]
        else:
            non_match_replacement = empty_value
        new_data[column_name] = extracted[column_name].mask(Series.isna,
                                                            other=non_match_replacement)

    new_data = new_data.replace({temp_na: np.nan})
    return new_data


def _find_names_in_braces(string: str) -> List[str]:
    """
    Find all substrings enclosed in braces in a given string and return them
    in order of apparition. If no such substrings are found, return an empty
    list.

    This method does not support strings that escape braces in any way.

    Parameters
    ----------
    string : str
        String to explore.

    Raises
    ------
    ValueError
        If any of the following is true:
        - `string` has a different number of opening and closing braces.
        - `string` has nested braces.
        - `string` has a closing brace that does not close any open braces.

    Returns
    -------
    list of str
        Substrings within braces.

    Examples
    --------
    >>> _find_names_in_braces('spam eggs')
    []
    >>> _find_names_in_braces('spam {eggs} hello')
    ['eggs']
    >>> _find_names_in_braces('{spam eggs} hello {world}')
    ['spam eggs', 'world']
    >>> _find_names_in_braces('{non {matching }number }of }braces')
    ValueError
    >>> _find_names_in_braces('{nested {braces}}')
    ValueError
    >>> _find_names_in_braces('a } that closes nothing! {')
    ValueError

    """

    if string.count('{') != string.count('}'):
        raise ValueError(f'{string} has unmatching number of opening and '
                         f'closing braces.')
    names = list()
    in_braces = False
    current_word = ''
    for (i, char) in enumerate(string):
        if in_braces:
            if char == '{':
                raise ValueError(f'{string} has an unexpected set of nested '
                                 f'braces at index {i}.')
            if char == '}':
                names.append(current_word)
                current_word = ''
                in_braces = False
                continue
            current_word += char
        else:
            if char == '}':
                raise ValueError(f'{string} has an unexpected ending brace at '
                                 f'index {i}.')
            if char == '{':
                in_braces = True
            # Otherwise ignore, char is not within any braces
    return names


def merge_columns(data: DataFrame, column_to_merge_on: str,
                  merging_format: str) -> DataFrame:
    """
    Return the original Panda dataframe `data` but with a new, possibly
    overwriting column `column_to_merge_on`. The contents of this column are
    formed by going row by row in `data`, and building a cell value by Python
    formatting `column_to_merge_on` with appropriate values in the row. If the
    column to merge on is already a column in the dataframe, it will be
    replaced.

    This method does not mutate the original dataframe.

    Parameters
    ----------
    data : pandas.core.frame.DataFrame
        Panda dataframe to inspect.
    column_to_merge_on : str
        Column to build.
    merging_format : str
        Formatting string to use to build the column. Column names must be
        surrounded by braces in this string, have no spaces and cannot be
        nested within other braces.

    Raises
    ------
    ValueError
        If any of the following is true
        * `merging_format` is empty.
        * `merging_format` has a different number of opening and closing
        braces.
        * `merging_format` has nested braces.
        * `merging_format` has a closing brace that does not close any open
        braces.
        * Any column names have spaces in their names.
    KeyError
        If any of the given column names is not a column of the dataframe.

    Returns
    -------
    DataFrame
        Dataframe with the merged column.

    Examples
    --------
    >>> df = pd.DataFrame({
    'First': ['Alyssa P.', 'Ben', 'Cy D'],
    'Last': ['Hacker', 'Bitdiddle', 'Fect']
    })
    >>> df
           First       Last
    0  Alyssa P.     Hacker
    1        Ben  Bitdiddle
    2       Cy D       Fect
    >>> merge_columns(df, 'Full Name', '{First} {Last}')
           First       Last         Full Name
    0  Alyssa P.     Hacker  Alyssa P. Hacker
    1        Ben  Bitdiddle     Ben Bitdiddle
    2       Cy D       Fect         Cy D Fect
    >>> merge_columns(df, 'Super Full Name', '{Last}, {First} {Last}')
           First       Last           Super Full Name
    0  Alyssa P.     Hacker  Hacker, Alyssa P. Hacker
    1        Ben  Bitdiddle  Bitdiddle, Ben Bitdiddle
    2       Cy D       Fect           Fect, Cy D Fect
    >>> merge_columns(df, 'Very Full Name', '{First} {Middle} {Last}')
    KeyError
    >>> df
           First       Last
    0  Alyssa P.     Hacker
    1        Ben  Bitdiddle
    2       Cy D       Fect

    """

    if not merging_format:
        err = 'Expected `merging_format` not be a empty string, found it was empty.'
        raise ValueError(err)

    column_names = _find_names_in_braces(merging_format)
    for name in set(column_names):
        if ' ' in name:
            err = 'Expected column names not have spaces, found column {name} has spaces in it.'
            raise ValueError(err)
        if name not in data:
            err = (f'Expected all columns be in the dataframe, found column {name} is not part of '
                   f'the dataframe.')
            raise KeyError(err)

    new_data = data.copy()
    new_data[column_to_merge_on] = ''

    reading_column_name = False
    buffer = ''
    for char in merging_format:
        if char == '{':
            if reading_column_name:
                raise RuntimeError(merging_format)
            reading_column_name = True
            new_data[column_to_merge_on] += buffer
            buffer = ''
        elif char == '}':
            if not reading_column_name:
                raise RuntimeError(merging_format)
            reading_column_name = False
            new_data[column_to_merge_on] += data[buffer]
            buffer = ''
        else:
            buffer += char

    return new_data


def adapt_column(data: DataFrame, column_to_adapt: str, matching_regex: str,
                 adapted_expression: str) -> DataFrame:
    """
    Return a copy `output` of the original dataframe, but with its `column_to_adapt` column
    modified as follows:\n
    * For each index `k` of `data[column_to_adapt]`:\n
      * If `data[column_to_adapt][k]` does not match ther regex `matching_regex`, then\
      `output[column_to_adapt][k] == data[column_to_adapt][k]`.\n
      * Otherwise, `output[column_to_adapt][k]` is the evaluated f-string `adapted_expression`,\
      where the variable names correspond to the `k`-th entry of the column of `data` with the same\
      names (if such a column exist), or the matched pattern with the same name in `matching_regex`\
      (priority applies to the second if a variable name corresponds to both an existing column of\
      `data` and a named matching pattern).

    This method does not mutate the original dataframe.

    Parameters
    ----------
    data : DataFrame
        Data to adapt.
    column_to_adapt : str
        Column to adapt.
    matching_regex : str
        Regular expression to use to find the column contents to adapt.
    adapted_expression : str
        Formatting string to use to adapt the matched column. Column names must be
        surrounded by braces in this string, have no spaces and cannot be
        nested within other braces.

    Raises
    ------
    ValueError
        If any of the following is true:
            * `matching_regex` is an invalid regex.
            * `column_to_adapt` is not a column of `data`.
            * `adapted_expression` is empty.
            * `adapted_expression` has a different number of opening and closing
            braces.
            * `adapted_expression` has nested braces.
            * `adapted_expression` has a closing brace that does not close any open
            braces.
            * Any column names have spaces in their names.

    Returns
    -------
    DataFrame
        Adapted dataframe.

    Examples
    --------
    >>> import pandas as pd
    >>> df = pd.DataFrame({
        'Student': ['Alyssa P. Hacker', 'Ben Bitdiddle', 'Cy D. Fect', 'Eva Lu Ator'],
        'Grade': [90, 40, 60, 59]
        })
    >>> df
                Student  Grade
    0  Alyssa P. Hacker     90
    1     Ben Bitdiddle     40
    2        Cy D. Fect     60
    3       Eva Lu Ator     59
    >>> re_given_names_last_name = r'(?P<given_names>.*) (?P<last_name>[^ ]+)'
    >>> last_name_comma_given_names = '{last_name}, {given_names}'
    >>> adapt_column(
        df, 'Student',
        re_given_names_last_name,
        last_name_comma_given_names
        )
                 Student  Grade
    0  Hacker, Alyssa P.     90
    1     Bitdiddle, Ben     40
    2        Fect, Cy D.     60
    3       Ator, Eva Lu     59
    >>> re_initial_last_name = r'(?P<initial>.).* (?P<last_name>[^ ]+)'
    >>> initial_last_name = '{initial}. {last_name}'
    >>> adapt_column(
        df, 'Student',
        re_initial_last_name,
        initial_last_name
        )
            Student  Grade
    0     A. Hacker     90
    1  B. Bitdiddle     40
    2       C. Fect     60
    3       E. Ator     59
    >>> re_first_name_last_name = r'(?P<first>[^ ]+) (?P<middle>[^ ]+) (?P<last>[^ ]+)'
    >>> first_name_last_name = '{first} {last}'
    >>> adapt_column(
        df, 'Student',
        re_first_name_last_name,
        first_name_last_name,
        )
             Student  Grade
    0  Alyssa Hacker     90
    1  Ben Bitdiddle     40
    2        Cy Fect     60
    3       Eva Ator     59
    >>> df
                Student  Grade
    0  Alyssa P. Hacker     90
    1     Ben Bitdiddle     40
    2        Cy D. Fect     60
    3       Eva Lu Ator     59
    """

    _check_regex(matching_regex)
    original_columns = data.columns
    if column_to_adapt not in original_columns:
        err = f'{column_to_adapt} is not a column of the dataframe and thus cannot be adapted.'
        raise ValueError(err)

    salt = 'SALT' + str(hash(object()))
    if not re.compile(matching_regex).groups:
        if matching_regex.endswith('$'):
            matching_regex = matching_regex[:-1] + rf'(?P<{salt}>)$'
        else:
            matching_regex += rf'(?P<{salt}>)'
        adapted_expression += f'{{{salt}}}'

    new_data = data.copy()
    temp_data = split_column(data, column_to_adapt, matching_regex,
                             maintaining_columns=[column_to_adapt],
                             empty_value=salt)
    temp_data = merge_columns(temp_data, column_to_adapt, adapted_expression)
    new_data[column_to_adapt] = temp_data[column_to_adapt].mask(
        ~temp_data[column_to_adapt].isna() & temp_data[column_to_adapt].str.contains(salt),
        data[column_to_adapt])

    return new_data


def fix_ordinals(data: DataFrame, column_to_fix: str, pattern: str) -> DataFrame:
    """
    Return a copy `output` of the original dataframe, but with its `column_to_fix` column\
    modified as follows.
    * For each index `k` of `data[column_to_fix]`:\n
      * If `data[column_to_fix][k]` contains no ordinal numbers (e.g. `1ST`, `32ND`), then\
      `output[column_to_fix][k] == data[column_to_fix][k]`.
      * If it does contain an ordinal number but it is not followed by a space and text that\
      matches the regex `pattern`, then `output[column_to_fix][k] == data[column_to_fix][k]`.
      * If it does contain an ordinal number followed by a space and then text that matches the\
      regex `pattern`, and finally the end of the string or a space,\
      then `output[column_to_fix][k]` will be `data[column_to_fix][k]` with the ordinal\
      number stripped of its suffix and moved after the text that matches `pattern`.

    Ordinal numbers must have the suffix capitalized in order to be matched. Thus, it is
    recommended that the user preemptively uppercases the column `column_to_fix` before calling
    this function.

    If several ordinals are present in a cell value, only the first one will be adapted. Thus, it
    is recommended that the user runs this function as many times as ordinals are present in a
    column.

    Parameters
    ----------
    data : DataFrame
        Dataframe to adapt.
    column_to_fix : str
        Column of the dataframe to adapt.
    pattern : str
        Regex such that the matched ordinal will go after the nearest text that matches the pattern.

    Raises
    ------
    ValueError
        If any of the following is true:
            * `pattern` is an invalid regex.
            * `column_to_fix` is not a column of `data`.

    Returns
    -------
    DataFrame
        Dataframe with the fixed column.

    Examples
    --------
    >>> import pandas as pd
    >>> pattern = '|'.join([
        'CIRCUIT',
        'DISTRICT',
        'GROUP'
        ])
    >>> df = pd.DataFrame({
        'district': ['1ST CIRCUIT', '22ND DISTRICT', '103RD DISTRICT AT LARGE', 'UOCAVA 4TH GROUP',
                     'LAST DISTRICT', '5TH WARD', '6TH CIRCUIT, 11TH SUBCIRCUIT',
                     'DISTRICT 7, 10TH GROUP', '8TH GROUPANDSOMEOTHERTEXT']
        })
    >>> df
                           district
    0                   1ST CIRCUIT
    1                 22ND DISTRICT
    2       103RD DISTRICT AT LARGE
    3              UOCAVA 4TH GROUP
    4                 LAST DISTRICT
    5                      5TH WARD
    6  6TH CIRCUIT, 11TH SUBCIRCUIT
    7        DISTRICT 7, 10TH GROUP
    8     8TH GROUPANDSOMEOTHERTEXT
    >>> fix_ordinals(df, 'district', pattern)
                         district
    0                   CIRCUIT 1
    1                 DISTRICT 22
    2       DISTRICT 103 AT LARGE
    3              UOCAVA GROUP 4
    4               LAST DISTRICT
    5                    5TH WARD
    6  CIRCUIT 6, 11TH SUBCIRCUIT
    7        DISTRICT 7, GROUP 10
    8     GROUP 8ANDSOMEOTHERTEXT
    """

    _check_regex(pattern)
    ordinal_endings = '|'.join({
        'ST',
        'ND',
        'RD',
        'TH',
        })

    salt = 'SALT' + str(hash(object()))
    matching_regex = (rf'(?P<{salt}beginning>(|.* ))'  # Empty or space separated beginning
                      rf'(?P<{salt}ordinal>\d+)'
                      rf'({ordinal_endings}) '
                      rf'(?P<{salt}pattern>({pattern}))'
                      rf'(?P<{salt}end>.*)')
    adapted_regex = ('{' + salt + 'beginning}'
                     '{' + salt + 'pattern} '
                     '{' + salt + 'ordinal}'
                     '{' + salt + 'end}')
    return adapt_column(data, column_to_fix, matching_regex, adapted_regex)


def merge_enums(name: str, *enums: Enum) -> Enum:
    """
    Create a Enum `output` with name `name` which satisfies the following condition: assuming the
    Enums passed in `*enums` are `enum_1, enum_2, ..., enum_n` in that order.
    * For each `(member, value)` pair in `output`, it is the case there exists some `i` where
    `enum_i[member] = value`. If several such `i` exist, then consider the largest such `i`.

    Parameters
    ----------
    name : TYPE
        Name of the created Enum.
    *enums : TYPE
        Enums to merge.

    Returns
    -------
    Enum
        Merged enums.

    Examples
    --------
    >>> from enum import Enum
    >>> class PBJSandwich(Enum):
            PEANUT_BUTTER = 1
            JELLY = 2
            BREAD = 3
    >>> class BLTSandwich(Enum):
            BACON = 4
            LETTUCE = 2
            TOMATO = 6
            BREAD = 7
    >>> merged_enum1 = merge_enums('Sandwiches1', PBJSandwich, BLTSandwich)
    >>> merged_enum1
    <enum 'Sandwiches1'>
    >>> for pair in merged_enum1:
            print(pair.name, pair.value)
    PEANUT_BUTTER 1
    JELLY 2
    BREAD 7
    BACON 4
    TOMATO 6
    >>> merged_enum2 = merge_enums('Sandwiches2', BLTSandwich, PBJSandwich)
    >>> merged_enum2
    <enum 'Sandwiches2'>
    >>> for pair in merged_enum2:
            print(pair.name, pair.value)
    BACON 4
    LETTUCE 2
    TOMATO 6
    BREAD 3
    PEANUT_BUTTER 1
    """

    pairs = dict()
    for enum in enums:
        for pair in enum:
            pairs[pair.name] = pair.value

    return Enum(name, pairs)


def obtain(column: Series = None, intended_type: type = None) -> List:
    """
    Obtain a sorted list of all the unique values within a series.
    If any Nump NaN exist within `column`, they are replaced with EMPTY_RECORD beforehand.
    If `intended_type` is not None, all values found in the series are cast to that type.

    This does not mutate the original series.

    Parameters
    ----------
    column : Series, optional
        Series whose values would be obtained. The default is None (and converted to an empty
        series).
    intended_type : type, optional
        Type to cast all values of the series to. The default is None.

    Returns
    -------
    List
        Sorted list of all the unique values within a series.

    """

    if column is None:
        column = pd.Series()

    values = column.fillna(value=EMPTY_RECORD).unique()
    if intended_type:
        values = [intended_type(value) for value in values]
    return sorted(values)
