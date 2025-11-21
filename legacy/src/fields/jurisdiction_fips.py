"""
Module for jurisdiction_fips cleaning tools.
"""

import numpy as np
import pandas as pd
import configparser
import os

from typing import Dict

from .. import field

DataFrame = pd.core.frame.DataFrame
Series = pd.core.series.Series

_config = configparser.ConfigParser()

if not _config.read('config.ini'):
    _config.read(str(pathlib.Path(r'electioncleaner/config.ini')))

class Jurisdiction_fips(field.Field):
    DEFAULT_TEXT_CHECKS = {
        # Only allow 0-9
        'UNRECOGNIZED CHARACTERS': r'[^0-9\-]+',
        }

    SEARCH_DUPLICATES_IN_VALUES = False
    SEARCH_SIMILAR_IN_COLUMN = False

    @staticmethod
    def parse_fips_from_name(data: DataFrame,
                             fips_file: str = os.path.join(_config['Paths']['precinct_base'], 'help-files/jurisdiction-fips-codes.csv'),
                             additional: Dict[str, int] = None) -> Series:
        """
        Return a series containing the jurisdiction fips codes associated with each row of `data`
        based on its `jurisdiction_name` column. If some fips codes are not present in the fips
        code file, they can be included in `additional` for consideration. If some jurisdiction
        name is included in both the fips code file and additional, the one in the fips file takes
        priority.

        This does not mutate the original dataframe.


        Parameters
        ----------
        data : DataFrame
            Original dataframe.
        fips_file : str, optional
            Location of the jurisdiction-fips-codes file. Defaults to
            '../../help-files/jurisdiction-fips-codes.csv'.
        additional : Dict[str, int], optional
            Additional jurisdiction names-fips pairs to consider *only if* the jurisdiction name
            is not present in the fips file or has the wrong value. The default is None, and
            converted to an empty dictionary.

        Raises
        ------
        ValueError
            If any of the following is true:\n
            * The dataframe does not contain a `state` or `jurisdiction_name` column.\n
            * The dataframe already contains a `jurisdiction_fips` column.\n
            * Some jurisdiction names could not be matched to some fips code, in which case a list \
            of such jurisdiction will be included with the error message.\n

        Returns
        -------
        Series
            Jurisdiction fips series.

        """

        if additional is None:
            additional = dict()
        fips = pd.read_csv(fips_file)
        fips['state'] = fips['state'].str.upper()

        if 'state' not in data.columns:
            err = ('Expected `state` column be in the dataframe columns, found it was not.')
            raise ValueError(err)
        if 'jurisdiction_name' not in data.columns:
            err = ('Expected `jurisdiction_name` column be in the dataframe columns, found it was '
                   'not.')
            raise ValueError(err)
        if 'jurisdiction_fips' in data.columns:
            err = ('Expected `jurisdiction_fips` column not be in the dataframe columns, found it '
                   'was already a column.')
            raise ValueError(err)

        new_data = data.join(fips.set_index(['state', 'jurisdiction_name']),
                             on=['state', 'jurisdiction_name'], how='left')
        new_data['jurisdiction_fips'] = new_data['jurisdiction_fips'].mask(
            new_data['jurisdiction_fips'].isna(),
            new_data['jurisdiction_name'].replace(additional, regex=False)
            )
        try:
            new_data['jurisdiction_fips'] = new_data['jurisdiction_fips'].astype(np.int64,
                                                                                 errors='raise')
        except ValueError:
            invalid_fips = -pd.to_numeric(new_data['jurisdiction_fips'], errors='coerce').notnull()
            invalid_data = (new_data[invalid_fips][['jurisdiction_name', 'jurisdiction_fips']]
                            .drop_duplicates())
            err = (f'Expected all jurisdiction names be matched with integer values, found the '
                   f'following entries were not numbers:\n{invalid_data}.')
            raise ValueError(err)
        return new_data['jurisdiction_fips']
