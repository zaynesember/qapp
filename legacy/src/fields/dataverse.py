"""
Module for party_simplified cleaning tools.
"""

import re
import pathlib
import pandas as pd

from typing import Set

from .. import field

DataFrame = pd.core.frame.DataFrame
Series = pd.core.series.Series


class Dataverse(field.Field):
    DEFAULT_TEXT_CHECKS = {
        # dataverse can only take a few select values
        'UNRECOGNIZED VALUES':
        r'^(?!((PRESIDENT|SENATE|HOUSE|STATE|LOCAL|""))$).*',
        }

    def check_special(self, data: DataFrame,
                      filename: str = None,
                      overwrite: bool = True,
                      verbose: bool = True):

        if filename is None:
            filename = self._default_output_file
        if verbose:
            print('------', flush=True)
            print('*Starting dataverse to office checks...', flush=True)

        output = list()
        output.append('------------\n')
        output.append('SPECIAL CHECK\n\n')

        issues = False

        # dataverse->office map
        if 'office' not in data:
            output.append('Unable to report dataverse to office map: office field missing.\n')
            issues = True
        else:
            dto_relations = data.groupby(['dataverse'])['office'].unique()
            ofd_relations = data.groupby(['office'])['dataverse'].unique()
            ofc_relations = data.groupby(['office'])['county_name'].unique()
            dataverse_to_offices = dict(dto_relations)
            office_to_dataverses = dict(ofd_relations)
            office_to_counties = dict(ofc_relations)

            expected_office_to_dataverse = {
                'US PRESIDENT': 'PRESIDENT',
                'US SENATE': 'SENATE',
                'US HOUSE': 'HOUSE',
                'STATE SENATE': 'STATE',
                'STATE HOUSE': 'STATE',
                'GOVERNOR': 'STATE',
                'LIEUTENANT GOVERNOR': 'STATE',
                'SECRETARY OF STATE': 'STATE',
                # 'STRAIGHT TICKET': '',
                }

            # Check if an office whose dataverse is trivial is matched to a different dataverse.
            if verbose:
                print('*Starting irregular office to dataverse checks...', flush=True)
            irregular_offices = dict()
            for (dataverse, offices) in dataverse_to_offices.items():
                for office in offices:
                    # As only a few offices can be confidently mapped to a dataverse via script,
                    # not all offices that appear in offices can be checked, thus the 'continue'
                    if office not in expected_office_to_dataverse:
                        continue
                    if expected_office_to_dataverse[office] != dataverse:
                        irregular_offices[office] = dataverse

            output.append('------\n')
            output.append('OFFICES WITH IRREGULAR DATAVERSE:\n')
            if not irregular_offices:
                output.append('    No Problems Found :) \n')
            else:
                for (office, dataverse) in irregular_offices.items():
                    output.append(f'    {office}: {dataverse}\n')
                issues = True
            output.append('------\n\n')

            if verbose:
                print('\nCompleted irregular office to dataverse checks.', flush=True)
                print('------\n', flush=True)
                print('*Starting office with multiple dataverses check', flush=True)

            # Check if an office has more than one dataverse associated to it
            irregular_offices = dict()
            for (office, dataverses) in office_to_dataverses.items():
                if len(dataverses) > 1:
                    irregular_offices[office] = sorted(dataverses)

            output.append('------\n')
            output.append('OFFICES WITH MULTIPLE DATAVERSES:\n')
            if not irregular_offices:
                output.append('    No Problems Found :) \n')
            else:
                for (office, dataverse) in irregular_offices.items():
                    output.append(f'    {office}: {dataverse}\n')
                issues = True
            output.append('------\n\n')

            if verbose:
                print('Completed office with multiple dataverses checks.', flush=True)
                print('------\n', flush=True)
                print('*Building court offices to dataverse map...')

            possible_court_offices = {
                'COURT',
                'JUSTICE',
                'JUDGE',
                }

            court_offices = dict()
            for (office, dataverses) in office_to_dataverses.items():
                for name in possible_court_offices:
                    if name in office.upper():
                        court_offices[office] = dataverses
                        continue

            # Build dataverse to offices map
            output.append('------\n')
            output.append('COURT OFFICES TO DATAVERSES MAP:\n')
            if not court_offices:
                output.append('    No Problems Found :) \n')
            else:
                for (office, dataverses) in court_offices.items():
                    output.append(f'    {office}: {dataverses}\n')
                issues = True
            output.append('------\n\n')

            if verbose:
                print('Built court office to dataverses map.', flush=True)
                print('------\n', flush=True)
                print('*Building dataverse to offices map...', flush=True)

            # Build dataverse to offices map
            output.append('------\n')
            output.append('DATAVERSE TO OFFICES MAP:\n')
            for (dataverse, offices) in dataverse_to_offices.items():
                output.append(f'    {dataverse}\n')
                for office in sorted(offices):
                    output.append(f'        {office}\n')
            output.append('------\n\n')
            
            # Kirsi: Build map of office to the number of associated counties
            output.append('------\n')
            output.append('OFFICE TO ASSOCIATED # OF COUNTIES MAP:\n')
            for (office, counties) in office_to_counties.items():
                num_counties = len(counties)
                output.append(f'    {office}\n')
                output.append(f'        {num_counties} counties for this office\n')
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
            print('Built dataverse to offices map.', flush=True)
            print('------\n', flush=True)

    @staticmethod
    def parse_dataverse_from_office(office_series: Series,
                                    president: Set[str] = None,
                                    senate: Set[str] = None,
                                    house: Set[str] = None,
                                    state: Set[str] = None,
                                    empty: Set[str] = None) -> Series:
        """
        Generate a `dataverse` series based on the given `office_series`, and the different
        values associated with each possible dataverse value. 99% of the time, only `state`
        and `empty` will need to be filled out.

        Parameters
        ----------
        series : Series
            Original office series.
        president : Set[str], optional
            Set of office values that will be matched to dataverse PRESIDENT. The default is None,
            and converted to the set {'US PRESIDENT'}.
        senate : Set[str], optional
            Set of office values that will be matched to dataverse SENATE. The default is None,
            and converted to the set {'US SENATE'}.
        house : Set[str], optional
            Set of office values that will be matched to dataverse HOUSE. The default is None,
            and converted to the set {'US HOUSE'}.
        state : Set[str], optional
            Set of office values that will be matched to dataverse STATE. The default is None,
            and converted to the empty set.
        empty : Set[str], optional
            Set of office values that will be matched to dataverse "" (empty). The default is None,
            and converted to the empty set.

        Returns
        -------
        Series
            Dataverse series.

        """

        if president is None:
            president = {'US PRESIDENT'}
        if senate is None:
            senate = {'US SENATE'}
        if house is None:
            house = {'US HOUSE'}
        if state is None:
            state = set()
        if empty is None:
            empty = set()

        office_types = {
            'PRESIDENT': president,
            'SENATE': senate,
            'HOUSE': house,
            'STATE': state,
            '': empty,
            }

        def fill_dataverse(office: str) -> str:
            # Try and match office to any offices associated to the dataverse
            for (office_type, offices) in office_types.items():
                if offices and re.match('|'.join(offices), office):
                    return office_type
            # By default, any other office corresponds to a local office
            return 'LOCAL'

        return office_series.apply(fill_dataverse)
