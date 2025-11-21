"""
Module for readme_check cleaning tools.
"""

import pathlib
import pandas as pd

from .. import field, miscellaneous

DataFrame = pd.core.frame.DataFrame
Series = pd.core.series.Series

class Readme_check(field.Field):
    _allowed_values = '|'.join([
        'TRUE',
        'FALSE',
        ]        )
    # DEFAULT_SIMILARITIES comes from field.Field
    DEFAULT_TEXT_CHECKS = {
        # special can only take a few select values
        'UNRECOGNIZED VALUES':
        rf'^(?!({_allowed_values})$).*',
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

        if verbose:
            print('*Starting README existence check...', flush=True)

        # This is done in a function so as to use return to avoid too many nested if elses
        def _readme_existence():
            issues = False

            if 'year' not in data:
                issues = True
                return(issues,'Unable to report on README existence: year column not found.')
            if 'state_po' not in data:
                issues = True
                return(issues,'Unable to report on README existence: state_po column not found.')

            years = set(miscellaneous.obtain(column=data['year'], intended_type=str))
            state_pos = set(miscellaneous.obtain(column=data['state_po'], intended_type=str))
            if len(years) > 1:
                issues = True
                return(issues,'Unable to report on README existence: too many years found.')
            if len(state_pos) > 1:
                issues = True
                return(issues,'Unable to report on README existence: too many state_pos found.')

            year = years.pop()
            state_po = state_pos.pop()
            readme_location1 = str(pathlib.Path(f'{self._precinct_base}/{year}/{state_po}/'
                                                f'README.md'))
            readme_location2 = str(pathlib.Path(f'{self._precinct_base}/precinct/{state_po}/'
                                                f'README.md'))

            readme_exists = (pathlib.Path(readme_location1).exists() or
                             pathlib.Path(readme_location2).exists())
            readme_location = (readme_location1 if pathlib.Path(readme_location1).exists() else
                               readme_location2)
            values = miscellaneous.obtain(column=data['readme_check'], intended_type=str)
            all_values = set(values)

            if all_values not in [{'TRUE'}, {'FALSE'}, {'TRUE', 'FALSE'}]:
                issues = True
                return (issues, 'Unable to report on README existence: unrecognized/too many '+\
                        'values found in the readme_check column.')


            if all_values in ({'TRUE', 'FALSE'}, {'TRUE'}):
                if readme_exists:
                    return (issues,\
                            f'*Expected there to be a README.md (`readme_check` TRUE), and found '
                            f'{readme_location}.')
                else:
                    issues = True
                    return (issues,\
                            f'*Expected there to be a README.md (`readme_check` TRUE), but could '
                            f'not find {readme_location1} nor {readme_location2}.')
            if readme_exists:
                issues = True
                return (issues,\
                        f'*Expected there not to be a README.md (`readme_check` FALSE), but could '
                        f'find {readme_location}.')
            issues = True
            return (issues,\
                    f'*Expected there not to be a README.md (`readme_check` FALSE), and could not '
                    f'find {readme_location1} nor {readme_location2}.')

        (issues, report) = _readme_existence()

        output.append('------\n')
        output.append('README EXISTENCE\n')
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

        print('Completed README existence check', flush=True)
        print('------\n', flush=True)
