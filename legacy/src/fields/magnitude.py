"""
Module for magnitude cleaning tools.
"""
import pathlib
import pandas as pd

from .. import field, fileio

DataFrame = pd.core.frame.DataFrame
Series = pd.core.series.Series


class Magnitude(field.Field):
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

    def check_special(self, data: DataFrame,
                      filename: str = None,
                      overwrite: bool = True,
                      verbose: bool = True):
        if filename is None:
            filename = self._default_output_file
        if verbose:
            print('------', flush=True)
            print('*Starting candidate with multiple offices check...', flush=True)

        fileio.make_dir_if_needed(filename)

        issues = False

        output = list()
        output.append('------------\n')
        output.append('SPECIAL CHECK\n\n')

        if 'office' not in data:
            output.append('Unable to report special checks: office field '
                          'missing.\n')
        else:
            output.append('------\n')
            output.append('OFFICES WITH MULTIPLE MAGNITUDES:\n')

            office_magnitudes = data.groupby(['office'])['magnitude'].unique()
            bad_offices = dict()
            for (office, magnitudes) in office_magnitudes.items():
                if len(magnitudes) > 1:
                    bad_offices[office] = magnitudes

            if not bad_offices:
                output.append('   No Problems Found :) \n')
            else:
                for (office, magnitudes) in bad_offices.items():
                    output.append(f'    {office}: {magnitudes}\n')
                issues = True
            output.append('------\n\n')

            if verbose:
                print('\nCompleted office with multiple magnitudes query.', flush=True)
                print('------\n', flush=True)
                print('*Building magnitude to offices map...')

            output.append('------\n')
            output.append('MAGNITUDE TO OFFICES MAP\n')
            magnitude_offices = data.groupby(['magnitude'])['office'].unique()
            for (magnitude, offices) in magnitude_offices.items():
                output.append(f'    {magnitude}: {offices}\n')
            output.append('------\n\n')

            if verbose:
                print('*Built magnitude to offices map.')

        with open(filename, 'a+', encoding='utf-8') as f:
            f.writelines(output)
        
        if issues:
            summary_file = str(pathlib.Path(rf'{self._base}/SUMMARY.txt'))
            name_to_print = filename.replace(self._base+'/','')
            with open(summary_file, 'a+', encoding='utf-8') as f:
                f.writelines("SPECIAL CHECK found potential issues in "+\
                             name_to_print+"\n")
