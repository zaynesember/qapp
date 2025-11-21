"""
Module for county_name cleaning tools.
"""

from enum import Enum
import pathlib
import pandas as pd

from .. import miscellaneous, field, fileio

DataFrame = pd.core.frame.DataFrame
Series = pd.core.series.Series

class County_name(field.Field):
    class _just_county_name_similarities(Enum):
        COUNTY = {
            'COUNTY',
            'CTY',
            }

    DEFAULT_SIMILARITIES = miscellaneous.merge_enums('COUNTY_NAME_SIMILARITIES',
                                                     field.Field.DEFAULT_SIMILARITIES,
                                                     _just_county_name_similarities)

    def check_special(self, data: DataFrame,
                      filename: str = None,
                      overwrite: bool = True,
                      verbose: bool = True):
        if filename is None:
            filename = self._default_output_file
        if verbose:
            print('*Checking county_name to county_fips relations...', flush=True)
        fileio.make_dir_if_needed(filename)

        output = list()
        output.append('------------\n')
        output.append('SPECIAL CHECK\n\n')

        if 'county_fips' not in data.columns:
            output.append('county_fips column is not present, so checks could not performed.')
        else:
            df_name_to_fips = data.groupby(['county_name'])['county_fips'].unique()
            df_fips_to_names = data.groupby(['county_fips'])['county_name'].unique()
            name_to_fips = dict()
            fips_to_names = dict()

            for (name, fips) in df_name_to_fips.items():
                if name not in name_to_fips:
                    name_to_fips[name] = list()
                for f in fips.tolist():
                    name_to_fips[name].append(f)

            for (fips, names) in df_fips_to_names.items():
                if fips not in fips_to_names:
                    fips_to_names[fips] = list()
                for n in names.tolist():
                    fips_to_names[fips].append(n)

            issues = False

            output.append('------\n')
            output.append('IRREGULAR COUNTY NAME TO FIPS RELATIONS\n')
            irregulars_ntf = [(name, fips) for (name, fips) in name_to_fips.items()
                              if len(fips) > 1]
            if not irregulars_ntf:
                output.append('    No Problems Found :) \n')
            else:
                issues = True
                for bad_name, bad_fips in irregulars_ntf:
                    output.append(f'    {bad_name}: {bad_fips}\n')
            output.append('------\n\n')

            output.append('------\n')
            output.append('IRREGULAR COUNTY FIPS TO NAMES RELATIONS\n')
            irregulars_ftn = [(fips, names) for (fips, names) in fips_to_names.items()
                              if len(names) > 1]
            if not irregulars_ftn:
                output.append('    No Problems Found :) \n')
            else:
                issues = True
                for bad_fips, bad_names in irregulars_ftn:
                    output.append(f'    {bad_fips}: {bad_names}\n')
            output.append('------\n\n')

            output.append('------\n')
            output.append('ALL COUNTY NAME, COUNTY FIPS PAIRS\n')
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

            with open(filename, 'a+', encoding='utf-8') as f:
                f.writelines(output)

            if issues:
                summary_file = str(pathlib.Path(rf'{self._base}/SUMMARY.txt'))
                name_to_print = filename.replace(self._base+'/','')
                with open(summary_file, 'a+', encoding='utf-8') as f:
                    f.writelines("SPECIAL CHECK found potential issues in "+\
                                 name_to_print+"\n")

            if verbose:
                print('\nChecked county name to fips relations...', flush=True)
                print('------\n', flush=True)
