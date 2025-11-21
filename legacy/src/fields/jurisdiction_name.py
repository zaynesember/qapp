"""
Module for jurisdiction_name cleaning tools.
"""

import pandas as pd
import pathlib
from .. import field, fileio

DataFrame = pd.core.frame.DataFrame
Series = pd.core.series.Series

class Jurisdiction_name(field.Field):
    def check_special(self, data: DataFrame,
                      filename: str = None,
                      overwrite: bool = True,
                      verbose: bool = True):
        if filename is None:
            filename = self._default_output_file
        if verbose:
            print('*Checking jurisdiction_name to jurisdiction_fips relations...', flush=True)
        fileio.make_dir_if_needed(filename)

        output = list()
        output.append('------------\n')
        output.append('SPECIAL CHECK\n\n')

        issues = False

        for column in ['jurisdiction_fips', 'county_name', 'county_fips']:
            if column not in data.columns:
                output.append(f'{column} column is not present, so checks could not performed.\n')
                break
        else:
            df_name_to_fips = data.groupby(['jurisdiction_name',
                                            'county_name',
                                            'county_fips'])['jurisdiction_fips'].unique()
            df_fips_to_names = data.groupby(['jurisdiction_fips'])['jurisdiction_name'].unique()
            name_to_fips = dict()
            fips_to_names = dict()

            for (attr, fips) in df_name_to_fips.items():
                juris_name, county_name, county_fips = attr
                if juris_name not in name_to_fips:
                    name_to_fips[juris_name] = list()
                name_to_fips[juris_name].append([county_name, county_fips] + [fips.tolist()])

            for (fips, names) in df_fips_to_names.items():
                fips_to_names[fips] = names.tolist()

            output.append('------\n')
            output.append('(POSSIBLY) IRREGULAR JURISDICTION NAME TO FIPS RELATIONS\n')
            irregulars_ntf = [(name, fips) for (name, fips) in name_to_fips.items()
                              if len(fips) > 1]
            if not irregulars_ntf:
                output.append('    No Problems Found :) \n')
            else:
                for bad_name, bad_fips in irregulars_ntf:
                    output.append(f'    {bad_name}: {bad_fips}\n')
                issues = True
            output.append('------\n\n')

            output.append('------\n')
            output.append('IRREGULAR JURISDICTION FIPS TO NAMES RELATIONS\n')
            irregulars_ftn = [(fips, names) for (fips, names) in fips_to_names.items()
                              if len(names) > 1]
            if not irregulars_ftn:
                output.append('    No Problems Found :) \n')
            else:
                for bad_fips, bad_names in irregulars_ftn:
                    output.append(f'    {bad_fips}: {bad_names}\n')
                issues = True
            output.append('------\n\n')

            output.append('------\n')
            output.append('ALL JURISDICTION NAME, JURISDICTION FIPS PAIRS\n')
            pairs = list()
            for (name, all_fips) in name_to_fips.items():
                for fips in all_fips:
                    pairs.append((name, fips))

            if not pairs:
                output.append('    No Problems Found :) \n')
            else:
                for pair in pairs:
                    output.append(f'    {pair}\n')
            output.append('------\n\n')

            if verbose:
                print('\nChecked jurisdiction name to fips relations...', flush=True)
                print('------\n', flush=True)

        with open(filename, 'a+', encoding='utf-8') as f:
            f.writelines(output)

        if issues:
            summary_file = str(pathlib.Path(rf'{self._base}/SUMMARY.txt'))
            name_to_print = filename.replace(self._base+'/','')
            with open(summary_file, 'a+', encoding='utf-8') as f:
                f.writelines("SPECIAL CHECK found potential issues in "+\
                             name_to_print+"\n")
