"""
Module that contains office cleaning tools.
"""
import pathlib
import pandas as pd

from enum import Enum
from .. import miscellaneous, field, fileio

DataFrame = pd.core.frame.DataFrame
Series = pd.core.series.Series


class Office(field.Field):
    class _just_office_similarities(Enum):
        PRESIDENT = {
            'PRESIDENT',
            'PRES',
            }

        US_SENATE = {
            'US SENATE',
            'US SENAT',
            'UNITED STATES SENAT',
            'U S SENAT',
            }

        US_HOUSE = {
            'US REP',
            'US HOUSE',
            'U S REP',
            'REPRESENTATIVE IN CONGRESS',
            'REP IN CONGRESS'
            }

        STATE_SENATE = {
            'STATE SENATOR',
            'STATE SENATE',
            'SENATOR OF',
            'SENATE OF',
            'SENATOR IN',
            'SENATE IN',
            'UPPER CHAMBER',
            }

        STATE_HOUSE = {
            'STATE REP',
            'STATE HOUSE',
            'STATE ASSEMBLY',
            'HOUSE OF DELEGATES',
            'LOWER CHAMBER',
            'REPRESENTATIVE POSITION',
            'REPRESENTATIVE IN',
            'REPRESENTATIVE TO',
            }

        GOVERNOR = {
            'GOV',
            }

        LIEUTENANT_GOVERNOR = {
            'LT GOV',
            'LIEUTENANT GOV',
            }

        SECRETARY_OF_STATE = {
            'SECRETARY OF STATE',
            'SEC OF STATE',
            'STATE SEC',
            }

        AUDITOR = {
            'AUDITOR',
            }

        RECORDER = {
            'RECORDER',
            }

        TREASURER = {
            'TREASURER',
            }

        CORONER = {
            'CORONER',
            }

        SURVEYOR = {
            'SURVEYOR',
        }

        RECORDER_OF_DEEDS = {
            'DEED',
        }

        REGISTER_OF_WILL = {
            'WILL'
        }

        COMMISSIONER_OR_COMMITTEE = {
            'COMM',
            }

        MEMBER = {
            'MEMBER',
        }

        SECRETARY = {
            'SECRETARY',
        }

        ADMINISTRATOR = {
            'ADMINISTRATOR',
            }

        ASSESSOR = {
            'ASSESSOR',
            }

        SUPERVISOR = {
            'SUPERVISOR'
            }

        COLLECTOR = {
            'COLLECTOR',
        }

        INSPECTOR = {
            'INSPECTOR',
        }

        EXECUTIVE = {
            'EXECUTIVE'
            }

        CHIEF = {
            'CHIEF'
            }

        SUPERINTENDENT = {
            'SUPERINTENDENT'
            'SUPT',
            'SUP OF',
            }

        COMPTROLLER = {
            'COMPTROLLER'
            }

        DIRECTOR = {
            'DIRECTOR'
            }

        REGISTER = {
            'REGISTER',
        }

        SHERIFF = {
            'SHERIFF',
            }

        CONSTABLE = {
            'CONSTABLE',
            }

        ATTORNEY = {
            'ATTORNEY',
            }

        SUPREME_COURT = {
            'SUPREME COURT',
            'SUP COURT',
            }

        SUPERIOR_COURT = {
            'SUPERIOR COURT',
            'SUP COURT',
            }

        CIRCUIT_COURT = {
            'CIRCUIT COURT',
            'CIRCUIT',
            }

        DISTRICT_COURT = {
            'DISTRICT COURT',
            }

        APPELLATE_COURT = {
            'APPELLATE COURT',
            'COURT OF APPEAL',
            'APPEAL',
            }

        JUSTICE_OF_THE_PEACE = {
            'JUSTICE OF THE PEACE',
            'JP',
            }

        JUDGE = {
            'JUDGE',
            'JD',
            }

        CLERK = {
            'CLERK',
        }

        BAILIFF = {
            'BAILIF',
        }

        MAGISTRATE = {
            'MAGISTRATE',
        }

        INTENDENT = {
            'INTENDENT',
            }

        MAYOR = {
            'MAYOR',
            }

        COUNCIL = {
            'COUNCIL',
            }

        CHAIR = {
            'CHAIR',
        }

        DELEGATE = {
            'DELEGATE',
        }

        ALDERMAN = {
            'ALDER',
        }

        MODERATOR = {
            'MODERATOR',
        }

        SERGEANT = {
            'SERGEANT',
        }

        MARSHALL = {
            'MARSHAL',
        }

        AUTHORITY = {
            'AUTHORITY',
        }

        REGENT = {
            'REGENT',
            }

        UNIVERSITY = {
            'UNIVERSITY',
            'COLLEGE',
        }

        HOSPITAL_DISTRICT = {
            'HOSPITAL',
            }

        MEDICAL_DISTRICT = {
            'MEDICAL',
        }

        SCHOOL_DISTRICT = {
            'SCHOOL',
            'EDUCATION',
            }

        TV_DISTRICT = {
            'TV',
            'TELEVISION',
            }

        FIRE_DISTRICT = {
            'FIRE',
            }

        DEVELOPMENT_DISTRICT = {
            'DEVELOPMENT',
        }

        CONSERVATION_DISTRICT = {
            'CONSERVATION',
        }

        IMPROVEMENT_DISTRICT = {
            'IMPROVEMENT',
        }

        UTILITY_DISTRICT = {
            'UTILITY'
        }

        NAVIGATION_DISTRICT = {
            'NAVIGATION',
        }

        BOARD = {
            'BOARD'
            }

        TRUSTEE = {
            'TRUSTEE',
            }

        ASSISTANT = {
            'ASSISTANT',
        }

        STRAIGHT_TICKET = {
            'STRAIGHT TICKET',
            'TICKET',
            }

    DEFAULT_TEXT_CHECKS = {
        **field.Field.DEFAULT_TEXT_CHECKS,
        **{
            # 'PRESIDENT' is an invalid name and checked for separately as it is a very common
            # mistake.
            'INCORRECTLY NAMED PRESIDENT (MUST BE US PRESIDENT)':
                r'^PRESIDENT$',
            }
        }
    DEFAULT_SIMILARITIES = miscellaneous.merge_enums('OFFICE_SIMILARITIES',
                                                     _just_office_similarities,
                                                     miscellaneous.GENERAL_SIMILARITIES,)

    def check_special(self, data: DataFrame,
                      filename: str = None,
                      overwrite: bool = True,
                      verbose: bool = True):
        if filename is None:
            filename = self._default_output_file
        if verbose:
            print('------', flush=True)
            print('*Starting candidate with multiple offices check...', flush=True)
        issues = False
        
        fileio.make_dir_if_needed(filename)

        output = list()
        output.append('------------\n')
        output.append('SPECIAL CHECK\n\n')

        output.append('------\n')
        output.append('CANDIDATES WITH MULTIPLE OFFICES:\n')

        if 'candidate' not in data:
            output.append('Unable to report candidate with multiple offices: candidate field '
                          'missing.\n')
            issues = True
        else:
            candidate_offices = data.groupby(['candidate'])['office'].unique()
            bad_candidates = dict()
            for (candidate, offices) in candidate_offices.items():
                if len(offices) > 1:
                    bad_candidates[candidate] = offices

            if not bad_candidates:
                output.append('    No Problems Found :) \n')
            else:
                for (candidate, offices) in bad_candidates.items():
                    output.append(f'    {candidate}: {offices}\n')
                issues = True
            output.append('------\n\n')

        if verbose:
            print('\nCompleted candidate with multiple offices query.', flush=True)
            print('------\n', flush=True)

        with open(filename, 'a+', encoding='utf-8') as f:
            f.writelines(output)

        if issues:
            summary_file = str(pathlib.Path(rf'{self._base}/SUMMARY.txt'))
            name_to_print = filename.replace(self._base+'/','')
            with open(summary_file, 'a+', encoding='utf-8') as f:
                f.writelines("SPECIAL CHECK found potential issues in "+\
                             name_to_print+"\n")
