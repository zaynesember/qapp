"""
Module for special cleaning tools.
"""

import pandas as pd

from .. import field, fileio

DataFrame = pd.core.frame.DataFrame
Series = pd.core.series.Series


class Special(field.Field):
    _allowed_values = '|'.join([
        'TRUE',
        'FALSE',
        ])

    # DEFAULT_SIMILARITIES comes from field.Field
    DEFAULT_TEXT_CHECKS = {
        # special can only take a few select values
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
            print('*Starting unrecognized values query for special...', flush=True)
        fileio.make_dir_if_needed(filename)

        output = list()
        output.append('------------\n')
        output.append('SPECIAL CHECK\n\n')

        fields = ['precinct', 'office', 'party_detailed', 'county_name', 'candidate', 'mode',
                  'district', 'stage', 'date']
        self.build_attribute_map(data, output, fields, verbose=verbose)

        with open(filename, 'a+', encoding='utf-8') as f:
            f.writelines(output)
