"""
Module for year cleaning tools.
"""

import pandas as pd

from .. import field, miscellaneous, fileio

DataFrame = pd.core.frame.DataFrame
Series = pd.core.series.Series

class Year(field.Field):
    DEFAULT_TEXT_CHECKS = {
        # Only allow 0-9
        'UNRECOGNIZED CHARACTERS': r'[^0-9\-]+',
        # Only allow values exactly 4 digits long
        'WRONG YEAR LENGTH': r'(^.{1,3}$)|(^.{4}.)',
        # Only allow numbers that do not start with digit 0
        'UNRECOGNIZED LEADING ZEROS': r'^0',
        }

    SEARCH_DUPLICATES_IN_VALUES = False
    SEARCH_SIMILAR_IN_COLUMN = False
    
    
    # Edit by Kirsi: For fields where full check is excessive,
    # check_all is rewritten in the child class to only include
    # special checks.
    
    def check_all(self, data: DataFrame = None,
                  column: str = None,
                  sensitivity: int = 90,
                  filename: str = None,
                  overwrite: bool = True,
                  verbose: bool = True,):
        
        if filename is None:
            filename = self._default_output_file
        if column is None:
            column = self._name

        if column not in data:
            raise KeyError(f'{column} is not a column in the dataset.')

        if verbose:
            print(f'*Checking {self._name}. Results will be saved to {filename}...',
                  flush=True)
        fileio.make_dir_if_needed(filename)
        if overwrite:
            fileio.remove_file_if_present(filename)

        with open(filename, 'a+', encoding='utf-8') as f:
            f.write('---------------------------\n')
            f.write('---------------------------\n')
            f.write(f'{self._name.upper()} CHECK\n')
            f.write('---------------------------\n')
            f.write('---------------------------\n\n')

        filtered_values = miscellaneous.obtain(column=data[column], intended_type=str)
        
        try:
            self.check_special(data,
                               filename=filename,
                               overwrite=False)
        except KeyboardInterrupt:
            print('Aborted special query.')
            
        
        with open(filename, 'a+', encoding='utf-8') as f:
            f.write('---------\n')
            f.write('------\n')
            f.write('ALL VALUES:\n')
            for value in filtered_values:
                f.write(f'    {value}\n')
            f.write('------\n\n')

        if verbose:
            print(f'All checks for {self._name} done. Results were saved to {filename}.',
                  flush=True)
    

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
