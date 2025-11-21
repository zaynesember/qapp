"""
Module for party_simplified cleaning tools.
"""

from enum import Enum
import pathlib
import pandas as pd

from .. import miscellaneous, field, fileio

DataFrame = pd.core.frame.DataFrame
Series = pd.core.series.Series


class Party_simplified(field.Field):
    class _just_party_s_similarities(Enum):
        DEMOCRAT = {
            'DEM',
            }

        REPUBLICAN = {
            'REP',
            }

        GREEN = {
            'GRE',
            'GRN',
            }

        LIBERTARIAN = {
            'LIB',
            }

        INDEPENDENT = {
            'IND',
            }

        OTHER = {
            'OTH',
            }

        NO_PARTY = {
            'NO',
            'NP',
            'NONPARTISAN',
            }

        PARTY = {
            'PARTY',
            'PARTISAN',
            'POLITICAL',
            'PREFERS',
            }

    DEFAULT_SIMILARITIES = miscellaneous.merge_enums('PARTY_S_SIMILARITIES',
                                                     _just_party_s_similarities,
                                                     miscellaneous.EMPTY_ENUM,)

    def check_special(self, data: DataFrame,
                      filename: str = None,
                      overwrite: bool = True,
                      verbose: bool = True):
        values = miscellaneous.obtain(column=data['party_simplified'], intended_type=str)

        if filename is None:
            filename = self._default_output_file
        if verbose:
            print('------', flush=True)
            print('*Starting unrecognized name query for party_simplified...', flush=True)

        issues = False

        fileio.make_dir_if_needed(filename)
        valid_names = {
            'DEMOCRAT',
            'REPUBLICAN',
            'LIBERTARIAN',
            'OTHER',
            'NONPARTISAN',
            '""',
            }

        invalid_names = [value for value in values if value not in valid_names]

        output = list()
        output.append('------------\n')
        output.append('SPECIAL CHECK\n\n')

        output.append('------\n')
        output.append('UNRECOGNIZED SIMPLIFIED PARTY NAMES:\n')
        if not invalid_names:
            output.append('   No Problems Found :) \n')
        else:
            for invalid_name in invalid_names:
                output.append(f'    {invalid_name}\n')
            issues = True
        output.append('------\n\n')

        if verbose:
            print('Completed unrecognized name query.', flush=True)
            print('------\n', flush=True)
            print('*Building party_simplified to party_detailed map...', flush=True)

        # Party_simplified->Party_detailed map
        if 'party_detailed' not in data:
            output.append('Unable to report party_simplified to party_detailed map: party_detailed '
                          'field missing.\n')
        else:
            output.append('------\n')
            output.append('PARTY SIMPLIFIED TO PARTY DETAILED MAP:\n')
            relations = data.groupby(['party_simplified'])['party_detailed'].unique()
            for (party_simplified, parties_detailed) in relations.items():
                output.append(f'    {party_simplified}: {parties_detailed}\n')
            output.append('------\n\n')

        if verbose:
            print('Built party_simplified to party_detailed map.', flush=True)
            print('------\n', flush=True)

        with open(filename, 'a+', encoding='utf-8') as f:
            f.writelines(output)

        if issues:
            summary_file = str(pathlib.Path(rf'{self._base}/SUMMARY.txt'))
            name_to_print = filename.replace(self._base+'/','')
            with open(summary_file, 'a+', encoding='utf-8') as f:
                f.writelines("SPECIAL CHECK found potential issues in "+\
                             name_to_print+"\n")
