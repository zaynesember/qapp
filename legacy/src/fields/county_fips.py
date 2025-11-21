"""
Module for county_fips cleaning tools.
"""

import pathlib
import pandas as pd
import configparser
import os

from .. import field

DataFrame = pd.core.frame.DataFrame
Series = pd.core.series.Series

_config = configparser.ConfigParser()

if not _config.read('config.ini'):
    _config.read(str(pathlib.Path(r'electioncleaner/config.ini')))

class County_fips(field.Field):
    DEFAULT_TEXT_CHECKS = {
        # Only allow 0-9
        'UNRECOGNIZED CHARACTERS': r'[^0-9\-]+',
        # Only allow values at most 5 digits long
        'FIPS TOO LONG': r'.{5}.',
        }

    SEARCH_DUPLICATES_IN_VALUES = False
    SEARCH_SIMILAR_IN_COLUMN = False

    @staticmethod
    def parse_fips_from_name(data: DataFrame,
                             fips_file: str = os.path.join(_config['Paths']['precinct_base'], 'help-files/county-fips-codes.csv')) -> Series:
        """
        Return a series containing the county fips codes associated with each row of `data`
        based on its `county_name` column.

        This does not mutate the original dataframe.

        Parameters
        ----------
        data : DataFrame
            Original dataframe.
        fips_file : str, optional
            Location of the county-fips-codes file. Defaults to
            '../../help-files/county-fips-codes.csv'

        Raises
        ------
        ValueError
            If any of the following is true:\n
            * The dataframe does not contain a `state` or `county_name` column.\n
            * The dataframe already contains a `county_fips` column.\n
            * Some county names could not be matched to some fips code, in which case a list of\
            such counties will be included with the error message.\n

        Returns
        -------
        Series
            County fips series.

        """

        fips = pd.read_csv(fips_file)

        fips['state'] = fips['state'].str.upper()

        if 'state' not in data.columns:
            err = ('Expected `state` column be in the dataframe columns, found it was not.')
            raise ValueError(err)
        if 'county_name' not in data.columns:
            err = ('Expected `county_name` column be in the dataframe columns, found it was not.')
            raise ValueError(err)
        if 'county_fips' in data.columns:
            err = ('Expected `county_fips` column not be in the dataframe columns, found it '
                   'was already a column.')
            raise ValueError(err)

        new_data = data.join(fips.set_index(['state', 'county_name']),
                             on=['state', 'county_name'], how='left')

        try:
            new_data['county_fips'] = new_data['county_fips'].astype(int, errors='raise')
        except ValueError:
            invalid_fips = -pd.to_numeric(new_data['county_fips'], errors='coerce').notnull()
            invalid_data = new_data[invalid_fips][['county_name', 'county_fips']].drop_duplicates()
            err = (f'Expected all county names be matched with integer values, found the following '
                   f'entries were not numbers:\n{invalid_data}.')
            raise ValueError(err)
        return new_data['county_fips']

    def check_special(self, data: DataFrame,
                      filename: str = None,
                      overwrite: bool = True,
                      verbose: bool = True,
                      fips_file: str = os.path.join(_config['Paths']['precinct_base'], 'help-files/county-fips-codes.csv')):

        output = list()
        output.append('------------\n')
        output.append('SPECIAL CHECK\n\n')

        if verbose:
            print('*Starting correct county fips for county check...', flush=True)

        issues = False
        fips_official = pd.read_csv(fips_file)
        fips_official['state'] = fips_official['state'].str.upper()

        empty_states = set(data[data['county_fips'] == "<<<EC: VALUE WAS EMPTY>>>"]['state'])

        report = ''
        try:
            data['county_fips'] = pd.to_numeric(data['county_fips'])
            fips_official['county_fips'] = pd.to_numeric(fips_official['county_fips'])

            df_name_to_fips = data.groupby(['county_name'])['county_fips'].unique()
            df_map = dict()
            for (name, fips) in df_name_to_fips.items():
                if name not in df_map:
                    df_map[name] = list()
                for f in fips.tolist():
                    df_map[name].append(f)
            off_sub = fips_official[fips_official['state'] == data['state'][0]]
            off_map = {}
            for name in list(off_sub["county_name"]):
                off_map[name] = list(off_sub[off_sub["county_name"] == name]["county_fips"])
            county_diffs = set(df_map.keys()).symmetric_difference(set(off_map.keys()))
            if county_diffs:
                report += 'NOTE: cannot compare all county fips because '+\
                              'some counties are excluded, or extra counties are included.\n\t'
                issues = True
            nonmatches = {}
            for name in df_map.keys():
                if name not in county_diffs:
                    if df_map[name] != off_map[name]:
                        nonmatches[name] = df_map[name]
            if nonmatches:
                report += f'The following county name <-> fips matches do not match'+\
                              f' the official mapping:\n {nonmatches}'
                issues = True            
            else:
                report = report + 'No Problems Found :)'
        except:
            issues = True
            report += 'It was not possible to cast county fips as numeric and group them'+\
                      ' with county name. This could happen due to blank values in county'+\
                      f' names or county fips in the following states: {empty_states}'

        output.append('------\n')
        output.append('COUNTY FIPS FOR COUNTY CHECK:\n')
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
