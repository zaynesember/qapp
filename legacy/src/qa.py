import pathlib
import pandas as pd
import os
import datetime

from . import checker, fileio, miscellaneous

DataFrame = pd.core.frame.DataFrame
Series = pd.core.series.Series

__all__ = (
    'do',
    'qa_all',
    'qa_stage1',
    'qa_check_columns',
    'qa_check_fields',
    'wrap_summary'
    )


def do(filename: str) -> None:
    print('Starting the MEDSL automated QA checker for primary and general election precinct '
          'results cleaning...')

    filename, qa_folder = fileio.detect_file(filename, 'qa')

    print(f'*Loading data from {filename}...')
    data = fileio.quick_load(filename)
    print('Loaded data.\n')

    base = str(pathlib.Path(qa_folder))
    qa_all(filename, data, base=base)


def qa_all(filename: str,
           data: DataFrame,
           base: str = None) -> None:
    if base is None:
        base = str(pathlib.Path('electioncleaner/output/qa'))
    print('*Starting QA checks for dataset.')
    data = data.fillna(miscellaneous.EMPTY_RECORD)
    try:
        qa_stage1(filename, data, base=base)
    except KeyboardInterrupt:
        print('Canceled remaining QA checks.')

    print('All QA checks for dataset done.')


def qa_stage1(filename: str,
              data: DataFrame,
              base: str = None) -> None:
    if base is None:
        base = str(pathlib.Path('electioncleaner/output/qa'))
    print('------------------')
    print('*Starting Stage 1 of QA for dataset.')
    data = data.fillna(miscellaneous.EMPTY_RECORD)
    init_summary(base)
    qa_check_columns(data, base=base, overwrite=True)
    qa_check_fields(data, base=base, overwrite=True)
    qa_check_duplicates(data, base=base, overwrite=True)
    wrap_summary(filename, base=base)
    print('All Stage 1 QA checks for dataset done.')
    print('------------------')

def qa_check_columns(data: DataFrame,
                     base: str = None,
                     filename: str = None,
                     overwrite: bool = True) -> None:
    if base is None:
        base = str(pathlib.Path('electioncleaner/output/qa'))
    if filename is None:
        filename = str(pathlib.Path(f'{base}/stage1_columns.txt'))
    fileio.make_dir_if_needed(filename)
    if overwrite:
        fileio.remove_file_if_present(filename)

    print("FILE NAME: " + filename)

    print('------------')
    print(f'*Checking dataset columns. Results will be saved to {filename}')
    expected_columns = {
        'precinct', 'office', 'party_detailed', 'party_simplified', 'mode',
        'votes', 'county_name', 'county_fips', 'jurisdiction_name',
        'jurisdiction_fips', 'candidate', 'district', 'magnitude', 'dataverse',
        'year', 'stage', 'state', 'special', 'writein', 'state_po', 'state_fips',
        'state_cen', 'state_ic', 'date',
        }
    actual_columns = set(data.columns)

    issues = False
    expected_not_in_actual = expected_columns.difference(actual_columns)
    actual_not_in_expected = actual_columns.difference(expected_columns)

    with open(filename, 'a+', encoding='utf-8') as f:
        if not expected_not_in_actual.union(actual_not_in_expected):
            f.write('*Dataset has exactly all expected columns\n')
        if expected_not_in_actual:
            issues = True
            f.write(f'*Dataset lacks expected columns {expected_not_in_actual}\n')
        if actual_not_in_expected:
            issues = True
            f.write(f'*Dataset has extraneous columns {actual_not_in_expected}\n')
        if issues:
            print(filename)
            write_summary(filename,"COLUMN CHECK",True,base)
    print(f'Checked dataset columns. Results were saved to {filename}')
    print('------------\n')


def qa_check_fields(data: DataFrame,
                    base: str = None,
                    filename: str = None,
                    overwrite: bool = True,
                    similarity_sensitivity: int = 90) -> None:
    if base is None:
        base = str(pathlib.Path('electioncleaner/output/qa'))
    if filename is None:
        filename = str(pathlib.Path(rf'{base}/stage1_field_{{field}}.txt'))
    fileio.make_dir_if_needed(filename)
    if overwrite:
        fileio.remove_file_if_present(filename)

    print('------------')
    print(f'*Checking dataset fields. Results will be saved to {filename} for each field.')
    data = data.fillna(miscellaneous.EMPTY_RECORD)
    for (field_name, module_class) in checker.get_fields_to_modules().items():
        print('---------')
        fielder = module_class(base=base)
        field_filename = filename.format(field=field_name)

        if field_name not in data:
            fileio.remove_file_if_present(field_filename)
            with open(field_filename, 'a+', encoding='utf-8') as f:
                f.write(f'*Dataset does not have column {field_name}.\n')
            print(f'*Dataset does not have column {field_name}, so it will be skipped.')
            continue

        fielder.check_all(data=data,
                          column=field_name,
                          filename=field_filename,
                          overwrite=overwrite,
                          sensitivity=similarity_sensitivity)
        print('---------\n')
    print('All dataset fields checked.')
    print('------------\n')

def qa_check_duplicates(data: DataFrame,
                     base: str = None,
                     filename: str = None,
                     overwrite: bool = True) -> None:
    if base is None:
        base = str(pathlib.Path('electioncleaner/output/qa'))
    if filename is None:
        filename = str(pathlib.Path(f'{base}/stage1_duplicates.txt'))
    fileio.make_dir_if_needed(filename)
    if overwrite:
        fileio.remove_file_if_present(filename)
    print('------------')
    print(f'*Checking for duplicate rows. Results will be saved to '+\
            'stage1_duplicates.txt. \n')
    summary_file = str(pathlib.Path(f'{base}/SUMMARY.txt'))
    numDups = sum(data.duplicated())
    if numDups:
        dupIndices = list(data[data.duplicated()].index)
        with open(filename, 'a+', encoding='utf-8') as f:
            f.write(f'*There are {numDups} exactly duplicated rows,'+\
                    f' in indices {dupIndices}.\n')
        with open(summary_file, 'a+', encoding='utf-8') as f:
            f.write("DUPLICATES CHECK found duplicated rows.\n")
    dfNoVotes = data.drop(["votes"], axis = 1)
    numNearDups = sum(dfNoVotes.duplicated())
    if numNearDups:
        nearDupIndices = list(dfNoVotes[dfNoVotes.duplicated()].index)
        with open(filename, 'a+', encoding='utf-8') as f:
            f.write(f'*There are {numNearDups} rows that are duplicated '+\
               'or duplicated except for the vote totals. Each '+\
               'candidate/precinct combo needs to have only one unique '+\
               f'vote total. The problems are in rows {nearDupIndices} \n')
        with open(summary_file, 'a+', encoding='utf-8') as f:
            f.write("DUPLICATES CHECK found nearly duplicated rows.\n")
    if (not numDups) and (not numNearDups):
        with open(filename, 'a+', encoding='utf-8') as f:
            f.write(f'*No duplicated or near-duplicated rows found.\n')
    print(f'Finished checking for duplicate rows.')
    print('------------')


def qa_check_zero_vote_precincts(data: DataFrame,
                     base: str = None,
                     filename: str = None,
                     overwrite: bool = True) -> None:
    if base is None:
        base = str(pathlib.Path('electioncleaner/output/qa'))
    if filename is None:
        filename = str(pathlib.Path(f'{base}/stage1_zero_vote_precincts.txt'))
    fileio.make_dir_if_needed(filename)
    if overwrite:
        fileio.remove_file_if_present(filename)
    print('------------')
    print(f'*Checking for precincts with zero votes. Results will be saved to '+\
            'stage1_zero_vote_precincts.txt. \n')
    summary_file = str(pathlib.Path(f'{base}/SUMMARY.txt'))

    precincts = data.groupby(['county_fips','jurisdiction_fips','precinct','office','district']).agg(sum)[['votes']]
    zero_vote_precincts = precincts[precincts['votes']==0].reset_index()
    numZVP = len(zero_vote_precincts)
    if numZVP > 0:
        with open(filename, 'a+', encoding='utf-8') as f:
            f.write(f'*There are {numZVP} [county_fips,jurisdiction_fips,precinct,office,district] '+\
                    'combinations with zero votes. Add the following code to end of your script '+\
                    'to remove violations (code in Python): \n' +\
                    '''
# where df is your cleaned dataset
def drop_zero_vote_precincts(df):
    precincts = df.groupby(['county_fips',
                            'jurisdiction_fips',
                            'precinct',
                            'office',
                            'district']).agg(sum)[['votes']]

    zero_vote_precincts = precincts[precincts['votes']==0].reset_index()
    # combos that contain only zero vote rows
    zero_vote_precincts = list(zip(zero_vote_precincts['county_fips'],
                                    zero_vote_precincts['jurisdiction_fips'],
                                    zero_vote_precincts['precinct'],
                                    zero_vote_precincts['office'],
                                    zero_vote_precincts['district']))
    drop_index = []
    from tqdm import tqdm as tqdm
    print("Dropping zero vote precincts.")
    for combo in tqdm(zero_vote_precincts):
        county = combo[0]
        juris = combo[1]
        precinct = combo[2]
        office = combo[3]
        district = combo[4]
        to_drop = list(df[((df['county_fips']==county)&
                                (df['jurisdiction_fips']==juris)&
                                (df['precinct']==precinct)&
                                (df['office']==office)&
                                (df['district']==district))].index)
        drop_index = drop_index + to_drop
    noZVP_df=df.drop(drop_index)
    return noZVP_df
df = drop_zero_vote_precincts([Name of cleaned dataset])
\n
                    ''')
        with open(summary_file, 'a+', encoding='utf-8') as f:
            f.write("ZERO VOTE PRECINCTS CHECK found violations.\n")
    else:
        with open(filename, 'a+', encoding='utf-8') as f:
            f.write(f'*No zero vote precincts found.\n')
    print(f'Finished checking for zero vote precinct rows.')
    print('------------')

#Functions to handle the summary document
def init_summary(base: str = None):
    if base is None:
        base = str(pathlib.Path('electioncleaner/output/qa'))
    summary_file = str(pathlib.Path(f'{base}/SUMMARY.txt'))
    fileio.make_dir_if_needed(summary_file)
    date = datetime.datetime.now().strftime("%Y-%m-%d")
    startTime = datetime.datetime.now().strftime("%I:%M:%S")
    with open(summary_file, 'w+', encoding='utf-8') as f:
        f.writelines("~ "+summary_file+" on "+date+", begun at "+startTime+" ~\n\n")

def write_summary(filename: str = None,
                  currentCheck: str = None,
                  startNew: bool = True,
                  base: str = None):
    summary_file = str(pathlib.Path(f'{base}/SUMMARY.txt'))
    name_to_print = filename.replace(base+'/','')
    with open(summary_file, 'a+', encoding='utf-8') as f:
        f.writelines(currentCheck + " found potential issues in "+\
                     name_to_print+"\n")

def wrap_summary(filename: str = None,
                 base: str = None):
    summary_file = str(pathlib.Path(f'{base}/SUMMARY.txt'))
    reminders = '\n ***REMINDERS:*** \n'+\
                '*REMEMBER TO CHECK votes.txt \n'+\
                '*LOOK THROUGH the candidate names\n'
    with open(summary_file, 'a+', encoding='utf-8') as f:
        f.writelines(reminders)
        f.close()
    archive_folder = str(pathlib.Path(f'{base}/../ARCHIVE/'))
    archive_file = archive_folder+'/SUMMARY_'+\
        datetime.datetime.now().strftime("%Y%m%d_%I%M%S")+'.txt'
    fileio.make_dir_if_needed(archive_file)
    os.popen('cp '+summary_file+' '+archive_file)
