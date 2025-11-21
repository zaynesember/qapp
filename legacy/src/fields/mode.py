"""
Module for Mode cleaning tools.
"""

import pandas as pd

from .. import miscellaneous, field, fileio

DataFrame = pd.core.frame.DataFrame
Series = pd.core.series.Series


class Mode(field.Field):
    DEFAULT_SIMILARITIES = miscellaneous.GENERAL_SIMILARITIES
    # DEFAULT_TEXT_CHECKS comes from field.Field

    def check_special(self, data: DataFrame,
                      filename: str = None,
                      overwrite: bool = True,
                      verbose: bool = True):
        if filename is None:
            filename = self._default_output_file
        if verbose:
            print('*Checking mode attributes.')
        fileio.make_dir_if_needed(filename)

        output = list()
        output.append('------------\n')
        output.append('SPECIAL CHECK\n\n')
        fields = ['precinct', 'office', 'party_detailed', 'county_name', 'candidate',
                  'district', 'stage', 'special', 'date']

        mode_dict = self.build_attribute_map(data, output, fields, verbose=verbose)

        if mode_dict:
            output.append('------\n')
            output.append('IRREGULAR MODES\n')
            irregular_tuples = [modes_tuple for modes_tuple in mode_dict
                                if len(modes_tuple) > 1 and 'TOTAL' in modes_tuple]
            if not irregular_tuples:
                output.append('    No Problems Found :) \n')
            else:
                for bad_value in irregular_tuples:
                    output.append(f'    {bad_value}: {mode_dict[bad_value][0]}\n')
            output.append('------\n\n')

        with open(filename, 'a+', encoding='utf-8') as f:
            f.writelines(output)
