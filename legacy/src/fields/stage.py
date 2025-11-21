"""
Module for stage cleaning tools.
"""

import pandas as pd

from .. import miscellaneous, field, fileio

DataFrame = pd.core.frame.DataFrame
Series = pd.core.series.Series


class Stage(field.Field):
    _allowed_values = '|'.join([
        'GEN',
        'PRI',
        'GEN RUNOFF',
        'PRI RUNOFF',
        ])
    # DEFAULT_SIMILARITIES comes from field.Field
    DEFAULT_TEXT_CHECKS = {
        # stage can only take a few select values
        'UNRECOGNIZED VALUES':
        rf'^(?!({_allowed_values})$).*',
        }

    def check_special(self, data: DataFrame,
                      filename: str = None,
                      overwrite: bool = True,
                      verbose: bool = True):
        if filename is None:
            filename = self._default_output_file
        if verbose:
            print('*Starting unrecognized value query for stage...', flush=True)
        fileio.make_dir_if_needed(filename)
        values = miscellaneous.obtain(column=data['stage'], intended_type=str)

        valid_names = [
            'GEN',
            'PRI',
            'GEN RUNOFF',
            'PRI RUNOFF',
            'GEN RECOUNT',
            'PRI RECOUNT',
            'GEN RUNOFF RECOUNT',
            'PRI RUNOFF RECOUNT',
            ]

        invalid_names = [value for value in values if value not in valid_names]

        output = list()
        output.append('------------\n')
        output.append('SPECIAL CHECK\n\n')

        output.append('------\n')
        output.append('UNRECOGNIZED STAGE VALUES:\n')
        if not invalid_names:
            output.append('    No Problems Found :) \n')
        else:
            for invalid_name in invalid_names:
                output.append(f'    {invalid_name}\n')
        output.append('------\n\n')

        if verbose:
            print('\nCompleted unrecognized values query.', flush=True)
            print('------\n', flush=True)

        fields = ['precinct', 'office', 'party_detailed', 'county_name', 'candidate', 'mode',
                  'district', 'special', 'date']
        self.build_attribute_map(data, output, fields, verbose=verbose)

        with open(filename, 'a+', encoding='utf-8') as f:
            f.writelines(output)
