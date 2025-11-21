"""
Module for state_cen cleaning tools.
"""

import pathlib
import pandas as pd

from .. import field, fileio, miscellaneous
from . import state

DataFrame = pd.core.frame.DataFrame
Series = pd.core.series.Series

class State_cen(field.Field):
    DEFAULT_TEXT_CHECKS = {
        # Only allow 0-9
        'UNRECOGNIZED CHARACTERS': r'[^0-9]+',
        # Only allow values exactly 2 digits long
        'WRONG CEN LENGTH': r'(^.$)|(^.{2}.)',
        # Only allow numbers that do not start with digit 0
        'UNRECOGNIZED LEADING ZEROS': r'^0',
        }

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

        if verbose:
            print('*Starting correct state cen for state check...', flush=True)
        fileio.make_dir_if_needed(filename)
        cen_values = miscellaneous.obtain(column=data['state_cen'], intended_type=str)
        state_codes_location = str(pathlib.Path(f'{self._precinct_base}/help-files/'
                                                f'merge_on_statecodes.csv'))

        def _state_code():
            issues = False
            
            if len(cen_values) > 1:
                issues = True
                return (issues,\
                        'Unable to report on correct state cen for state check: multiple '
                        'state_cen values found.')
            if 'state' not in data:
                issues = True
                return (issues,\
                        'Unable to report on correct state cen for state check attributes: state '
                        'field missing.')
            if not pathlib.Path(state_codes_location).exists():
                issues = True
                return (issues,\
                        f'Unable to report on correct state cen for state check attributes: state '
                        f'code file {state_codes_location} missing.')
            state_values = miscellaneous.obtain(column=data['state'], intended_type=str)
            if len(cen_values) > 1:
                issues = True
                return (issues,\
                        'Unable to report on correct state cen for state check: multiple state '
                        'values found.')

            cen_value = cen_values[0]
            state_value = state_values[0]
            try:
                expected_cen = state.State.get_state_code(state_codes_location, state_value,
                                                          'state_cen')
            except KeyError as exc:
                issues = True
                return (issues,\
                        f'Unable to report on correct state cen for state check: {exc}.')

            return (issues,\
                    f'*Expected state cen code {expected_cen} for {state_value}, '
                    f'found {cen_value}.')

        (issues, report) = _state_code()
        if verbose:
            print('\nCompleted unrecognized values query.', flush=True)

        output.append('------\n')
        output.append('STATE CEN FOR STATE CHECK:\n')
        output.append(f'    {report}\n')
        output.append('------\n\n')

        with open(filename, 'a+', encoding='utf-8') as f:
            f.writelines(output)
        
        if issues:
            summary_file = str(pathlib.Path(rf'{self._base}/SUMMARY.txt'))
            name_to_print = filename.replace(self._base+'/','')
            with open(summary_file, 'a+', encoding='utf-8') as f:
                f.writelines("SPECIAL CHECK found potential issues in "+\
                             name_to_print+"\n")
