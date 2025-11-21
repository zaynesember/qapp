"""
Module that contains state cleaning tools.
"""

import pandas as pd

DataFrame = pd.core.frame.DataFrame

from .. import field

class State(field.Field):
    DEFAULT_TEXT_CHECKS = field.Field.DEFAULT_TEXT_CHECKS
    SEARCH_DUPLICATES_IN_VALUES = False
    SEARCH_SIMILAR_IN_COLUMN = False

    def check_special(self, data: DataFrame,
                      filename: str = None,
                      overwrite: bool = True,
                      verbose: bool = True):
        output = list()
        output.append('------------\n')
        output.append('SPECIAL CHECK\n\n')

        unique = self.check_unique(data=data, verbose=verbose)
        output.extend(unique)

        with open(filename, 'a+', encoding='utf-8') as f:
            f.writelines(output)

    @staticmethod
    def get_state_code(file: str, state: str, code: str) -> str:
        """
        Get a particular state code for a state.

        Parameters
        ----------
        file : str
            Location of `merge_on_statecodes.csv`.
        state : str
            Name of the state.
        code : str
            One of `state`, `state_po`, `state_fips`, `state_cen`, `state_ic`.

        Raises
        ------
        KeyError
            If `state` is not a state in the file.

        Returns
        -------
        str
            State code.

        """
        all_codes = pd.read_csv(file, sep=",", header=0)
        state_codes = (all_codes.loc[all_codes['state'].str.upper() == state.upper()].copy()
                       .reset_index(drop=True))
        if state_codes.empty:
            raise KeyError(f'Unrecognized state: {state}')
        value = state_codes[code][0]
        if isinstance(value, str):
            return value.upper()
        return value

    @staticmethod
    def add_state_codes(data: DataFrame, file: str = '../../help-files/merge_on_statecodes.csv',
                        state: str = '') -> DataFrame:
        """
        Return a copy of the dataframe with 5 new columns: `state`, `state_po`, `state_fips`,
        `state_cen`, `state_ic`. The last four are obtained by finding the codes associated with
        `state` in the file `file`.

        This does not mutate the original dataframe.

        Parameters
        ----------
        data : DataFrame
            Original dataframe.
        file : str, optional
            Location of the file containing all state codes.
            The default is '..\\..\\help-files\\merge_on_statecodes.csv'.
        state : str, optional
            Name of state. The default is ''.

        Returns
        -------
        DataFrame
            Dataframe with additional columns.

        """

        new_data = data.copy()
        for code in ['state', 'state_po', 'state_fips', 'state_cen', 'state_ic']:
            new_data[code] = State.get_state_code(file, state, code)

        return new_data
