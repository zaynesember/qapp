"""
Module for party_detailed cleaning tools.
"""
import pathlib
import pandas as pd

from enum import Enum
from .. import miscellaneous, field, fileio

DataFrame = pd.core.frame.DataFrame
Series = pd.core.series.Series


class Party_detailed(field.Field):
    DEFAULT_TEXT_CHECKS = {
        **field.Field.DEFAULT_TEXT_CHECKS,
        **{
            # These party names must be standardized
            'INCORRECTLY STANDARDIZED PARTY NAMES':
                '|'.join([
                    r'^DEMOCRATIC$',
                    r'^G(\.)?O(\.)?P(\.)?$',
                    ]),
            }
        }

    class _just_party_d_similarities(Enum):
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

    DEFAULT_SIMILARITIES = miscellaneous.merge_enums('PARTY_D_SIMILARITIES',
                                                     _just_party_d_similarities,
                                                     miscellaneous.EMPTY_ENUM,)

    def check_special(self, data: DataFrame,
                      filename: str = None,
                      overwrite: bool = True,
                      verbose: bool = True):
        if filename is None:
            filename = self._default_output_file
        if verbose:
            print('------', flush=True)
            print('*Starting candidate with multiple parties check...', flush=True)

        issues = False

        fileio.make_dir_if_needed(filename)

        output = list()
        output.append('------------\n')
        output.append('SPECIAL CHECK\n\n')

        output.append('------\n')
        output.append('CANDIDATES WITH MULTIPLE PARTIES:\n')

        if 'candidate' not in data:
            output.append('Unable to report candidate with multiple parties: candidate field '
                          'missing.')
        else:
            candidate_parties = data.groupby(['candidate'])['party_detailed'].unique()
            bad_candidates = dict()
            for (candidate, parties) in candidate_parties.items():
                if len(parties) > 1:
                    bad_candidates[candidate] = parties

            if not bad_candidates:
                output.append('   No Problems Found :) \n')
            else:
                for (candidate, parties) in bad_candidates.items():
                    output.append(f'    {candidate}: {parties}\n')
                issues = True
            output.append('------\n\n')

        if verbose:
            print('\nCompleted candidate with multiple parties query.', flush=True)
            print('------\n', flush=True)

        with open(filename, 'a+', encoding='utf-8') as f:
            f.writelines(output)

        if issues:
            summary_file = str(pathlib.Path(rf'{self._base}/SUMMARY.txt'))
            name_to_print = filename.replace(self._base+'/','')
            with open(summary_file, 'a+', encoding='utf-8') as f:
                f.writelines("SPECIAL CHECK found potential issues in "+\
                             name_to_print+"\n")
