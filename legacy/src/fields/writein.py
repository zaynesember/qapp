"""
Module for writein cleaning tools.
"""

import pandas as pd
import pathlib

from .. import miscellaneous, field, fileio

DataFrame = pd.core.frame.DataFrame
Series = pd.core.series.Series

class Writein(field.Field):
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
            print('*Starting unrecognized name query for special...', flush=True)
        fileio.make_dir_if_needed(filename)
        values = miscellaneous.obtain(column=data['special'], intended_type=str)

        issues = False

        valid_names = [
            'TRUE',
            'FALSE',
            ]

        invalid_names = [value for value in values if value not in valid_names]

        output = list()
        output.append('------------\n')
        output.append('SPECIAL CHECK\n\n')

        output.append('------\n')
        output.append('UNRECOGNIZED WRITEIN VALUES:\n')
        if not invalid_names:
            output.append('    No Problems Found :)\n')
        else:
            for invalid_name in invalid_names:
                output.append(f'    {invalid_name}\n')
            issues = True
        output.append('------\n\n')

        if verbose:
            print(f'\nSaved unrecognized simplified query to {filename}.', flush=True)
            print('------\n', flush=True)
            print('*Checking writein to candidate relations...', flush=True)

        # Writein to candidate map
        if 'writein' not in data:
            output.append('Unable to check writein to candidate relations: candidate field '
                          'missing.')
            issues = True
        else:
            if verbose:
                print('*Checking candidates with multiple writein values...', flush=True)
            ctw_relations = data.groupby(['candidate'])['writein'].unique()
            bad_candidates = dict()

            for (candidate, writeins) in ctw_relations.items():
                if len(writeins) > 1:
                    bad_candidates[candidate] = writeins

            output.append('------\n')
            output.append('CANDIDATES WITH MULTIPLE WRITEIN VALUES:\n')
            if not bad_candidates:
                output.append('    No Problems Found :) \n')
            else:
                for (candidate, writeins) in bad_candidates.items():
                    output.append(f'    {candidate}: {writeins}\n')
                issues = True
            output.append('------\n\n')

            if verbose:
                print('\nChecked candidates with multiple writein values...', flush=True)
                print('------\n', flush=True)
                print('*Checking candidates where a writein tag appears irregularly...', flush=True)

            wtc_relations = data.groupby(['writein'])['candidate'].unique()
            if not ('TRUE' in wtc_relations or 'FALSE' in wtc_relations):
                if verbose:
                    print('Unable to check writein to candidate relations: no TRUE or FALSE '
                          'values found in column.')
                    issues = True
            else:
                bad_candidates = dict()
                if 'TRUE' in wtc_relations:
                    writeins = wtc_relations['TRUE']
                    # The only valid candidate names are
                    # 1. WRITEIN (if no candidate name was provided)
                    # 2. A normal candidate without the words WRITE or W/I (if one was provided)
                    for candidate in writeins:
                        candidate = candidate.upper()
                        if candidate == 'WRITEIN':
                            continue
                        if 'WRITE' in candidate or 'W/I' in candidate:
                            bad_candidates[candidate] = 'TRUE'
                if 'FALSE' in wtc_relations:
                    not_writeins = wtc_relations['FALSE']
                    # Only candidate names that do not have WRITE or W/I are valid (as those cases
                    # should have writein TRUE)
                    for candidate in not_writeins:
                        candidate = candidate.upper()
                        if 'WRITE' in candidate or 'W/I' in candidate:
                            bad_candidates[candidate] = 'FALSE'

                output.append('------\n')
                output.append('(POSSIBLY) CANDIDATES WITH IRREGULARLY PLACED WRITEIN WITHIN THE '
                              'NAME:\n')
                if not bad_candidates:
                    output.append('   No Problems Found :) \n')
                else:
                    for (candidate, writein) in bad_candidates.items():
                        output.append(f'    {candidate}: {writein}\n')
                    issues = True
                output.append('------\n\n')

        if verbose:
            print('\nChecked candidates where a writein tag appears irregularly...', flush=True)
            print('------\n', flush=True)
            print('\nChecking writein candidates with no votes...', flush=True)

        writeins_no_votes = sorted(
            data[(data['writein']=='TRUE') & (data['votes']==0)]['candidate'].unique()
            )
        writeins_no_votes = [value for value in writeins_no_votes if value not in {
            'WRITEIN',
            'SCATTER'
            }]

        output.append('------\n')
        output.append('WRITEIN CANDIDATES THAT APPEAR SOMEWHERE HAVING 0 VOTES.\n')
        if not writeins_no_votes:
            output.append('   No Problems Found :) \n')
        else:
            for candidate in writeins_no_votes:
                output.append(f'    {candidate}\n')
            issues = True
        output.append('------\n\n')

        if verbose:
            print('\nChecked writein candidates with no votes...', flush=True)
            print('------\n', flush=True)

        with open(filename, 'a+', encoding='utf-8') as f:
            f.writelines(output)

        if issues:
            summary_file = str(pathlib.Path(rf'{self._base}/SUMMARY.txt'))
            name_to_print = filename.replace(self._base+'/','')
            with open(summary_file, 'a+', encoding='utf-8') as f:
                f.writelines("SPECIAL CHECK found potential issues in "+\
                             name_to_print+"\n")
