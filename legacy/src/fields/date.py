"""
Module for date cleaning tools.
"""

import sys
import pandas as pd
import pathlib

from tqdm import tqdm
from .. import field, fileio

DataFrame = pd.core.frame.DataFrame
Series = pd.core.series.Series

class Date(field.Field):
    DEFAULT_TEXT_CHECKS = {
        # Only allow 0-9 and -
        'UNRECOGNIZED CHARACTERS': r'[^0-9\-]+',
        # Only allow values that follow YYYY-MM-DD
        'UNRECOGNIZED YYYY-MM-DD DATES':
            r'^(?!([0-9]{4}\-[0-9]{2}\-[0-9]{2})$).*',
        }

    SEARCH_DUPLICATES_IN_VALUES = False
    SEARCH_SIMILAR_IN_COLUMN = False

    def check_special(self, data: DataFrame,
                      filename: str = None,
                      overwrite: bool = True,
                      verbose: bool = True):
        issues = False
        # Make sure each date is matched to a correct year
        if verbose:
            print('*Checking date to year relations...', flush=True)
        fileio.make_dir_if_needed(filename)

        output = list()
        output.append('------------\n')
        output.append('SPECIAL CHECK\n\n')

        output.append('------\n')
        output.append('IRREGULAR DATE TO YEAR RELATIONS\n')
        if 'year' not in data.columns:
            output.append('year column is not present, so checks could not performed.')
            issues = True
        else:
            df_date_to_years = data.groupby(['date'])['year'].unique()
            date_to_years = dict()

            for (date, years) in df_date_to_years.items():
                date_to_years[date] = years.tolist()

            # Check if a date is associated to two or more years, or a year that does not
            # align with the date
            irregulars_dty = [(date, years) for (date, years) in date_to_years.items()
                              if (len(years) != 1 or
                                  [year for year in years if date[:4] != str(year)])]
            if not irregulars_dty:
                output.append('    No Problems Found :) \n')
            else:
                for bad_date, bad_year in irregulars_dty:
                    output.append(f'    {bad_date}: {bad_year}\n')
                issues = True
        output.append('------\n\n')

        if verbose:
            print('\nChecked jurisdiction name to fips relations...', flush=True)
            print('------\n', flush=True)

        fields = ['precinct', 'office', 'party_detailed', 'county_name', 'candidate', 'mode',
                  'district', 'stage', 'special']
        self.build_attribute_map(data, output, fields, verbose=verbose)

        with open(filename, 'a+', encoding='utf-8') as f:
            f.writelines(output)

        if issues:
            summary_file = str(pathlib.Path(rf'{self._base}/SUMMARY.txt'))
            name_to_print = filename.replace(self._base+'/','')
            with open(summary_file, 'a+', encoding='utf-8') as f:
                f.writelines("SPECIAL CHECK found potential issues in "+\
                             name_to_print+"\n")
