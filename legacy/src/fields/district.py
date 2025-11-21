"""
Module for district cleaning tools.
"""

import pandas as pd
import pathlib
from typing import List

from .. import miscellaneous, field, fileio

DataFrame = pd.core.frame.DataFrame
Series = pd.core.series.Series


class District(field.Field):
    DEFAULT_SIMILARITIES = miscellaneous.GENERAL_SIMILARITIES
    DEFAULT_TEXT_CHECKS = {
        **field.Field.DEFAULT_TEXT_CHECKS,
        **{
            # All numerical districts must be at least three digits long
            'UNPADDED NUMERICAL DISTRICTS':
                r'^[0-9]{1,2}$',
            }
        }

    def check_special(self, data: DataFrame,
                      filename: str = None,
                      overwrite: bool = True,
                      verbose: bool = True):
        if filename is None:
            filename = self._default_output_file
        if verbose:
            print('*Checking district attributes.')
        fileio.make_dir_if_needed(filename)

        issues = False

        output = list()
        output.append('------------\n')
        output.append('SPECIAL CHECK\n\n')

        fields = ['precinct', 'office', 'party_detailed', 'county_name', 'candidate', 'mode',
                  'stage', 'special', 'date']
        district_dict = self.build_attribute_map(data, output, fields, verbose=verbose)

        if district_dict:
            output.append('------\n')
            output.append('IRREGULAR DISTRICTS\n')
            irregular_tuples = [districts_tuple for districts_tuple in district_dict
                                if len(districts_tuple) > 1 and
                                ('' in districts_tuple or 'STATEWIDE' in districts_tuple)]
            if not irregular_tuples:
                output.append('   No Problems Found :) \n')
            else:
                for bad_value in irregular_tuples:
                    output.append(f'    {bad_value}: {district_dict[bad_value][0]}\n')
                issues = True
            output.append('------\n\n')

        with open(filename, 'a+', encoding='utf-8') as f:
            f.writelines(output)

        if issues:
            summary_file = str(pathlib.Path(rf'{self._base}/SUMMARY.txt'))
            name_to_print = filename.replace(self._base+'/','')
            with open(summary_file, 'a+', encoding='utf-8') as f:
                f.writelines("SPECIAL CHECK found potential issues in "+\
                             name_to_print+"\n")

    @staticmethod
    def mark_statewide_districts(district_series: Series, office_series: Series,
                                 statewide_offices: List[str]) -> Series:
        """
        Return a copy of `district_series` with the following changes:\n
        * For every index `i` of `district_series`:\n
          * If the value at index `i` of `office_series` regex matches any of the office names
          given in `statewide_office`, replace the `i`-th value of the copy of `district_series`
          with `STATEWIDE`.

        This method does not mutate either of the given series.

        Parameters
        ----------
        district_series : Series
            Original district series.
        office_series : Series
            Original office series.
        statewide_offices : List[str]
            List of offices that should be marked statewide.

        Returns
        -------
        Series
            Copy of the district series modified as described above.

        """

        regex_statewide_offices = '|'.join(statewide_offices)
        matching_offices = office_series.str.contains(regex_statewide_offices)
        return district_series.mask(matching_offices, 'STATEWIDE')

    @staticmethod
    def fix_numerical_districts(series: Series) -> Series:
        """
        Return a copy of `series` with the following changes:\n
        * Replace all integers with zero-padded string versions so they have length at least 3
        (e.g. 1 to "001").
        * Replace all floats that end with ".0" with zeor-padded strings so they have length at
        least three (e.g. 43.0 to "043").
        * Replace every other value with the value cast to a string/.

        This does not mutate the original series.

        Parameters
        ----------
        series : Series
            Original district series.

        Returns
        -------
        Series
            Series with modifications as above.

        """

        def fix_number_districts(district: str) -> str:
            if pd.isna(district):
                return district

            district = str(district)
            # Pad numerical districts with enough zeros so that its length is 3
            if district.isdigit():
                return district.zfill(3)
            # Check if .0 float
            if district.endswith('.0') and district[:-2].isdigit():
                return district[:-2].zfill(3)

            # No further modifications needed for other cases
            return district

        return series.apply(fix_number_districts)
