import csv
import os
import pathlib
import re
import zipfile

import pandas as pd

from typing import Set, Tuple, Union

DataFrame = pd.core.frame.DataFrame
Series = pd.core.series.Series

__all__ = (
    'save_aggregate',
    'save_county_aggregate',
    'save_contest_aggregate',
    'save_candidate_aggregate',
    'save_field',
    'convert_csv_to_excel',
    'quick_load',
    'save_cleaned_dataset',
    'simple_walk',
    )


def _check(data: DataFrame = None, expected_columns: Set[str] = None) -> None:
    """
    Check to see if all columns in `expected_columns` are columns of `data` (not necessarily the
    other way around though). If not, raise an error.

    Moreover, check to see if `filename` is empty. If so, replace it with `default_filename`.

    Parameters
    ----------
    data : DataFrame, optional
        Dataset to check. The default is None (and converted to an empty dataframe with columns
        the values in `expected_columns`).
    expected_columns : Set[str], optional
        Columns to check in `data`. The default is None (and converted to an empty set).

    Raises
    ------
    ValueError
        If any of the values in `expected_columns` is not a column of `data`.

    Returns
    -------
    None

    """

    if expected_columns is None:
        expected_columns = set()
    if data is None:
        data = pd.DataFrame(dict(
            zip(expected_columns, [[] for _ in range(len(expected_columns))])
            ))

    missing_columns = expected_columns.difference(data.columns)
    if missing_columns:
        raise ValueError(f'Expected columns {expected_columns} to appear in '
                         f'dataframe, found it was missing these columns: '
                         f'{missing_columns}.')


def _save(data: Union[DataFrame, Series] = None, filename: str = None) ->  None:
    """
    Attempt to save a dataframe or series to a CSV file such that it is encoded in utf-8,
    does not show the index, and empty strings are explicitly rendered as double quotation marks.

    If the target path for the CSV is in use, the function will halt and loop until the target
    path is no longer in use (this will typically happen if the target path already exists and
    is currently open in another appliction)

    Parameters
    ----------
    data : Union[DataFrame, Series], optional
        Data to save. The default is None (and converted to an empty dataframe).
    filename : str, optional
        Location where to save the generated CSV file. The default is None.

    Raises
    ------
    ValueError
        If `filename` is None or empty.

    Returns
    -------
    None.

    """

    if not filename:
        raise ValueError('Expected filename.')
    if data is None:
        data = pd.DataFrame()

    print(f'*Attempting to save data to {filename}...')
    while True:
        try:
            data.to_csv(filename, index=False, encoding='utf-8', quoting=csv.QUOTE_NONNUMERIC)
        except PermissionError:
            input(f'File {filename} is in use. Please close it and try again.')
        else:
            break

    print(f'File {filename} successfully generated.')


def detect_file(filename: str, mode: str) -> Tuple[str]:
    """
    Attempt to automatically detect a well-named cleaned CSV file one folder up from the
    electioncleaner folder (typically the case if there is a symlink) if given an empty `filename`.
    If a CSV was found or `filename` was not empty, create an output folder according to the
    given `mode` for which to place reports, generated CSVs, etc.

    Two types of automatic detections will be attempted:
    1. Primary elections (e.g. "D:\primary-precincts\2018\AK\2018-ak-precinct-primary.csv" and
                          "D:\primary-precincts\2018\AK\electioncleaner\" both exist and the
                          location from which the script is run is the latter folder)
    2. General elections (e.g. "D:\2018-precincts\AK\2018-ak-precinct.csv"  and
                          "D:\2018-precincts\AK\electioncleaner\" both exist and the
                          location from which the script is run is the latter folder)

    Parameters
    ----------
    filename : str
        Filename to look for. If given, this will be the detected file, and its location will be
        used in conjunction with `mode` to generate the mode folder. Otherwise, an attempt will be
        made to locate a valid CSV, and if found, its location will be used in conjunction with
        `mode` to generate the mode folder.
    mode : str
        Mode in which the function caller is being used (e.g. "qa", "aggregate", etc.)

    Raises
    ------
    RuntimeError
        If no filename was given, and it is the case the location from which the script is run is
        similar to one of the two locations given above, but a CSV could not be found.
    ValueError
        If no filename was given, and it is the case the location from which the script is run is
        not similar to one of the two locations given above.

    Returns
    -------
    filename, mode_folder
        Detected CSV file and location of the mode folder.

    """
    working_directory = str(pathlib.Path.cwd())
    # If working from a state-year primary folder
    match = re.search(r'(?P<year>[0-9]{4})(\\|\/)(?P<state>[A-Z]{2})', working_directory)
    if match:
        mode_folder = str(pathlib.Path(rf'../{mode}').resolve())
        # If not given a filename
        if filename == '':
            # Try and find valid CSV file in the parent folder
            year, state = match.group('year'), match.group('state')
            file = pathlib.Path(rf'../{year}-{state.lower()}-precinct-primary.csv').resolve()
            if not file.exists():
                file2 = pathlib.Path(rf'../{year}-{state.lower()}-precinct.csv').resolve()
                if not file2.exists():
                    err = (f'Unable to automatically detect cleaned CSV\r\n'
                           f'{str(file)} or {str(file2)}.')
                    raise RuntimeError(err)
                file = file2
            filename = str(file)

        if filename:
            return filename, mode_folder

    # If working from a year-state general folder
    match = re.search(r'(?P<year>[0-9]{4})-precincts(\\|\/)(precinct(\\|\/))?'
                      r'(?P<state>[A-Z]{2})', working_directory)
    if match:
        mode_folder = str(pathlib.Path(rf'../{mode}').resolve())
        # If not given a filename
        if filename == '':
            # Try and find valid CSV file in the parent folder
            year, state = match.group('year'), match.group('state')
            file = pathlib.Path(rf'../{year}-{state.lower()}-precinct-general.csv').resolve()
            if not file.exists():
                file2 = pathlib.Path(rf'../{year}-{state.lower()}-precinct.csv').resolve()
                if not file2.exists():
                    err = (f'Unable to automatically detect cleaned CSV\r\n'
                           f'{str(file)}')
                    raise RuntimeError(err)
                file = file2
            filename = str(file)

        if filename:
            return filename, mode_folder

    # If working from any other folder
    project_name = pathlib.Path(filename).stem
    mode_folder = rf'output/{mode}/{project_name}'

    if filename:
        return filename, mode_folder

    err = 'Expected filename as argument.'
    raise ValueError(err)


def convert_csv_to_excel(filename: str, new_filename: str = None, keep_csv: bool = True) -> str:
    """
    Convert a CSV file to a pretty Excel spreadsheet:\n
    * Column lengths are adjusted to fully render all values.\n
    * All values are rendered as an Excel table, so it is easy to filter and sort.
    * Fully empty values will be converted to EMPTY_RECORD.

    Parameters
    ----------
    filename : str
        Path to CSV file.
    new_filename : str, optional
        Path to new Excel file. The default is None, which is then converted to the same path as
        `filename`, but with `.csv` replaced with `.xlsx`.
    keep_csv : bool, optional
        If False, the input CSV file will be deleted; if True, no such action will be taken.
        The default is True.

    Raises
    ------
    ValueError
        If the data in the CSV file contains more than 25 columns.

    Returns
    -------
    str
        Path to the generated Excel spreadsheet.

    """

    if new_filename is None:
        new_filename = filename[:-4] + '.xlsx'

    print(f'*Attempting to convert CSV file to Excel spreadsheet at {new_filename}...')
    data = quick_load(filename)

    ## Following section is courtesy of
    # snl: https://stackoverflow.com/a/64866217
    def format_tbl(writer, sheet_name, df):
        outcols = df.columns
        if len(outcols) > 25:
            raise ValueError('table width out of range for current logic')
        tbl_hdr = [{'header': c} for c in outcols]
        bottom_num = len(df)+1
        right_letter = chr(65-1+len(outcols))
        tbl_corner = right_letter + str(bottom_num)

        worksheet = writer.sheets[sheet_name]
        worksheet.add_table('A1:' + tbl_corner,  {'columns': tbl_hdr})
        for idx, col in enumerate(df):  # loop through all columns
            series = df[col]
            max_len = max((
                series.astype(str).map(len).max(),  # len of largest item
                len(str(series.name))  # len of column name/header
                )) + 3  # adding a little extra space
            worksheet.set_column(idx, idx, max_len)  # set column width

    with pd.ExcelWriter(new_filename, mode='w', engine='xlsxwriter') as writer:
        sheet_name = 'Main'
        data.to_excel(writer, sheet_name=sheet_name, index=False)
        format_tbl(writer, sheet_name, data)

    if not keep_csv:
        os.remove(filename)

    print(f'File {new_filename} successfully generated.')
    return new_filename


def save_aggregate(data: DataFrame = None, filename: str = None):
    """
    Save results where votes are aggregated by: office, district, dataverse,
    party_detailed, writein, special, and mode.

    Parameters
    ----------
    data : DataFrame, optional
        Dataframe to build an aggregate from. The default is None (and
        converted to an empty dataframe).
    filename : str, optional
        Filename of created file. The default is None (and converted to
        `aggregate.csv`).

    Raises
    ------
    ValueError
        If `data` lacks any of the following columns: office, district,
        dataverse, party_detailed, writein, special, mode, votes.

    Returns
    -------
    None.

    """

    if not filename:
        filename = 'aggregate.csv'

    columns = {'office', 'district', 'dataverse', 'candidate',
               'party_detailed', 'writein', 'special', 'mode', 'votes'}
    _check(data=data, expected_columns=columns)

    aggr = data.groupby(['office', 'district', 'dataverse', 'candidate',
                         'party_detailed', 'writein', 'special',
                         'mode'])['votes']
    _save(data=aggr.sum().reset_index(), filename=filename)


def save_county_aggregate(data: DataFrame = None, filename: str = None):
    """
    Save results where votes are aggregated by: county_name, office,
    party_detailed, and candidate.

    Parameters
    ----------
    data : DataFrame, optional
        Dataframe to build an aggregate from. The default is None (and
        converted to an empty dataframe).
    filename : str, optional
        Filename of created file. The default is None (and converted to
        `aggregate_county.csv`).

    Raises
    ------
    ValueError
        If `data` lacks any of the following columns: county_name, office,
        party_detailed, candidate, votes.

    Returns
    -------
    None.

    """

    if not filename:
        filename = 'aggregate_county.csv'

    columns = {'county_name', 'office', 'party_detailed', 'candidate', 'votes'}
    _check(data=data, expected_columns=columns)

    aggr = data.groupby(['county_name', 'office', 'party_detailed',
                         'candidate'])['votes']
    _save(data=aggr.sum().reset_index(), filename=filename)


def save_contest_aggregate(data: DataFrame = None, filename: str = None):
    """
    Save results where votes are aggregated by: office, district, party_detailed,
    special, votes.

    Parameters
    ----------
    data : DataFrame, optional
        Dataframe to build an aggregate from. The default is None (and
        converted to an empty dataframe).
    filename : str, optional
        Filename of created file. The default is None (and converted to
        `aggregate_contest.csv`).

    Raises
    ------
    ValueError
        If `data` lacks any of the following columns: office, district, party_detailed,
        special, votes.

    Returns
    -------
    None.

    """

    if not filename:
        filename = 'aggregate_contest.csv'

    columns = {'office', 'district', 'party_detailed', 'special', 'votes'}
    _check(data=data, expected_columns=columns)

    aggr = data.groupby(['office', 'district', 'party_detailed',
                         'special'])['votes']
    _save(data=aggr.sum().reset_index(), filename=filename)


def save_candidate_aggregate(data: DataFrame = None, filename: str = None):
    """
    Save results where votes are aggregated by: office, district, candidate, party_detailed,
    special, votes.

    Parameters
    ----------
    data : DataFrame, optional
        Dataframe to build an aggregate from. The default is None (and
        converted to an empty dataframe).
    filename : str, optional
        Filename of created file. The default is None (and converted to
        `aggregate_candidate.csv`).

    Raises
    ------
    ValueError
        If `data` lacks any of the following columns: office, district, candidate, party_detailed,
        special, votes.

    Returns
    -------
    None.

    """

    if not filename:
        filename = 'aggregate_candidate.csv'

    columns = {'office', 'district', 'candidate', 'party_detailed', 'special', 'votes'}
    _check(data=data, expected_columns=columns)

    aggr = data.groupby(['office', 'district', 'candidate', 'party_detailed',
                         'special'])['votes']
    _save(data=aggr.sum().reset_index(), filename=filename)



def save_field(data: DataFrame = None, field: str = None, filename: str = None):
    """
    Obtain all values in a column and save in a separate file to allow for
    further inspection.

    Parameters
    ----------
    data : DataFrame, optional
        Dataframe whose column wil be saved. The default is None (and
        converted to an empty dataframe).
    field : str, optional
        Column to save. Must be a column of `data`.
    filename : str, optional
        Name of the file where to save the data. The default is None (and
        converted to {field}.txt)

    Raises
    ------
    KeyError
        If `field` is not a column of `data`.

    Returns
    -------
    None.

    """

    if data is None:
        data = pd.DataFrame({field: []})
    if field not in data.columns:
        raise KeyError(f'{field} is not a column of the dataframe.')
    if filename is None:
        filename = f'{field}.txt'
    with open(filename, 'w+', encoding='utf-8') as f:
        for item in sorted(data[field].unique()):
            f.write(f'{item}\n')
    print(f'Field data file {filename} successfully generated.')


def quick_load(filename: str):
    """
    Load a cleaned CSV file as a Pandas dataframe. Values that are exactly "" (2 double quotation
    marks) are loaded as is in the dataframe.

    Parameters
    ----------
    filename : str
        Location of the file.

    Raises
    ------
    FileNotFoundError
        If the file does not exist.

    Returns
    -------
    pd.core.frame.DataFrame
        Dataframe.

    """

    if not os.path.exists(filename):
        err = f'File {filename} does not exist.'
        raise FileNotFoundError(err)

    # Create a temporary file that can properly parse values that are exactly double quotation
    # marks, which represent the empty string in R. This file will then be deleted.
    # To parse these values, convert them to """""" (6 double quotation marks), which Pandas
    # then registers as "" (2 double quotation marks)
    temp = filename + '.tmp'
    with open(temp, 'w+', encoding='utf-8') as f_temp:
        with open(filename, 'r', encoding='utf-8') as f_og:
            line, i = f_og.readline(), 0
            while line:
                i+=1
                temp_line = re.sub('^"",', '"""""",', line)
                # We do a lookahead for the comma instead of searching for it directly so that
                # we can do consecutive double quotation mark replacements (that is, be able to
                # detect and handle ,"","",)
                temp_line = re.sub(',""(?=,)', ',""""""', temp_line)
                temp_line = re.sub(r'""\n', r'""""""\n', temp_line)
                f_temp.write(temp_line)
                line = f_og.readline()

    # Add explicit types to the following so that Pandas does not attempt to...
    dtype = {
        # ...convert all capital TRUE/FALSE values to Python's True/False
        'special': str,
        'writein': str,
        'readme_check': str,
        # ...convert fully numeric to string
        'district': str,
        'county_fips': str,
        'jurisdiction_fips': str,
        }

    data = pd.read_csv(temp, sep=',', header=0, low_memory=False, dtype=dtype)
    os.remove(temp)
    return data


def make_dir_if_needed(filename: str) -> bool:
    """
    If the directory of filename does not exist, create it and return True. Otherwise, return False.

    Parameters
    ----------
    filename : str
        Filename.

    Returns
    -------
    bool
        If the directory did not exist and was successfully created

    """

    directory = os.path.dirname(filename)
    if os.path.exists(directory):
        return False
    os.makedirs(directory)
    return True


def remove_file_if_present(filename: str) -> bool:
    """
    If the filename exists, remove it and return True. Otherwise, return False.

    Parameters
    ----------
    filename : str
        Filename.

    Returns
    -------
    bool
        If the file existed and was successfully removed

    """

    try:
        os.remove(filename)
        return True
    except OSError:
        return False


def save_cleaned_dataset(data: DataFrame, filename: str, save_zip: bool = True) -> None:
    """
    Save a cleaned dataset to filename. If the location already exists and is in use, the function
    will halt until the file is no longer in use.

    Parameters
    ----------
    data : DataFrame
        Dataframe to save.
    filename : str
        Location to save to.
    save_zip : bool, optional
        If True, a compressed ZIP file containing the CSV will be generated; if False, no such
        action will be taken. Defaults to True.

    Returns
    -------
    None

    """

    print(f'*Attempting to save cleaned data to {filename}...')
    while True:
        try:
            data.to_csv(filename, index=False, encoding='utf-8', quoting=csv.QUOTE_NONNUMERIC)
        except PermissionError:
            input(f'File {filename} is in use. Please close it and try again.')
        else:
            break
    print(f'File {filename} successfully generated.')

    if save_zip:
        zip_name = filename[:-4] + '.zip'
        print(f'*Attempting to zip cleaned data to {zip_name}...')
        while True:
            try:
                with zipfile.ZipFile(zip_name, 'w', compression=zipfile.ZIP_DEFLATED) as myzip:
                    myzip.write(filename)
            except PermissionError:
                input(f'File {zip_name} is in use. Please close it and try again.')
            else:
                break

        print(f'Zip file {zip_name} successfully generated.')


def simple_walk(raw_folder: str = 'raw') -> None:
    """
    Generator of all files within the given raw folder in the current directory.

    Parameters
    ----------
    raw_folder : str, optional
        Name of the raw folder. The default is 'raw'.

    Yields
    ------
    str
        Filename in the raw folder (just the filename, not the full directory).

    Examples
    --------
    >>> for file in simple_walk(raw_folder='raw'):
            print(file)
    AR_precinct.csv
    summary.csv
    """

    for (_, _, files) in os.walk(f'{os.getcwd()}/{raw_folder}'):
        for file in files:
            if '~' in file:
                # Prevent Excel temporary files from showing up.
                continue
            yield file
