import pandas as pd

from typing import List, Set

DataFrame = pd.core.frame.DataFrame
Series = pd.core.series.Series

__all__ = (
    'check_original_dataset',
    'select_cleaned_dataset_columns',
    'sort_cleaned_dataset',
    'check_cleaned_dataset',
    'inspect_cleaned_dataset',
    )

_expected_dataset_columns = ["precinct", "office", "party_detailed", "party_simplified", "mode",
                             "votes", "county_name", "county_fips", "jurisdiction_name",
                             "jurisdiction_fips", "candidate", "district", "magnitude",
                             "dataverse", "year", "stage", "state", "special", "writein",
                             "state_po", "state_fips", "state_cen", "state_ic", "date",
                             "readme_check"]
_expected_dataset_columns_2 = _expected_dataset_columns + ['municipality']


def check_original_dataset(data: DataFrame, expected_columns: Set[str] = None,
                           county_column: str = None, expected_counties: int = None) -> None:
    """
    Perform the following checks on the dataset:
    1. The dataset has exactly all expected columns (not necessarily in the same order).
    2. The dataset has the exact number of counties as expected (if given).

    Parameters
    ----------
    data : DataFrame
        Dataverse to check.
    expected_columns : Set[str], optional.
        Columns expected in the dataset. The default is None, which is then converted to an
        empty set.
    county_column : str, optional
        Name of the county column in the dataframe. The default is None.
    expected_counties : int, optional
        Number of counties expected in the dataset. The default is None.

    Raises
    ------
    KeyError
        If county_column is given but it is not a column of the dataframe.
    ValueError
        If exactly one of county_column or expected_counties is set but the other one is not.
    AssertionError
        If any of the checks fail.

    Returns
    -------
    None.

    """

    # # Assert correct column headers
    if expected_columns is None:
        expected_columns = set()
    actual_columns = set(data.columns)
    err = (f'Expected dataframe have columns {sorted(expected_columns)}, '
           f'found it had columns {sorted(actual_columns)}.')
    assert (expected_columns == actual_columns), err

    if county_column is None and expected_counties is not None:
        err = ('Expected `county_columns` and `expected_counties` be both simultaneously set or '
               'not set, found `county_columns` was not set but `expected_counties` was.')
        raise ValueError(err)
    if county_column is not None and expected_counties is None:
        err = ('Expected `county_columns` and `expected_counties` be both simultaneously set or '
               'not set, found `expected_counties` was not set but `county_columns` was.')
        raise ValueError(err)

    if county_column is not None:
        if county_column not in data.columns:
            err = (f'Expected county column {county_column} be in the dataframe columns, found it '
                   f'was not.')
            raise KeyError(err)

        # Assert correct number of counties
        actual_counties = len(data[county_column].unique())
        err = (f"Data has wrong number of counties: expected {expected_counties}, "
               f"got {actual_counties}")
        assert expected_counties == actual_counties, err

    print("All checks for original data passed.")


def select_cleaned_dataset_columns(data: DataFrame, ignore_nonexistent: bool,
                                   columns: List[str] = None) -> DataFrame:
    """
    Reshape the dataset so that it only has the given columns. If any column in columns is not
    in the dataframe's columns, this raises a ValueError if ignore_nonexistent is True and
    ignores the column otherwise.
    This does not mutate the original dataframe.

    Parameters
    ----------
    data : DataFrame
        Dataset to select.
    ignore_nonexistent : bool
        Whether to ignore columns that do not exist in the dataframe.
    columns : List[str], optional
        Columns to select. The default is None, which is then converted to the standard dataset
        columns according to MEDSL standards.

    Raises
    ------
    ValueError
        If ignore_nonexistent is False and some column in columns is not a column in the dataframe.

    Returns
    -------
    DataFrame
        Reshaped dataset.

    """

    if columns is None:
        if 'municipality' not in data.columns:
            columns = _expected_dataset_columns
        else:
            columns = _expected_dataset_columns_2

    existing_columns = [column for column in columns if column in data.columns]
    nonexisting_columns = [column for column in columns if column not in data.columns]

    if not ignore_nonexistent and nonexisting_columns:
        err = (f'Expected columns {nonexisting_columns} be in the cleaned dataset, found they '
               f'were not.')
        raise ValueError(err)
    if ignore_nonexistent:
        columns = existing_columns

    return data[columns].copy()


def sort_cleaned_dataset(data: DataFrame) -> DataFrame:
    """
    Perform a stable sort of the dataset based on the given columns. If multiple columns are given,
    columns that appear later are used to break ties that happen with earlier columns.
    This does not mutate the original dataframe.

    Parameters
    ----------
    data : DataFrame
        Dataset to sort.

    Raises
    ------
    ValueError
        If any of the columns to sort by is not a column of the dataset.

    Returns
    -------
    DataFrame
        Sorted dataset.

    """

    columns = ['county_name', 'jurisdiction_name', 'precinct', 'stage', 'special',
               'office', 'district', 'party_detailed', 'candidate']

    nonexisting_columns = [column for column in columns+['dataverse'] if column not in data.columns]

    if nonexisting_columns:
        err = (f'Expected columns {nonexisting_columns} be in the cleaned dataset, found they '
               f'were not.')
        raise ValueError(err)

    data = data.sort_values(columns, kind='mergesort')
    dataverses = ['PRESIDENT', 'SENATE', 'HOUSE', 'STATE', 'LOCAL', '']
    data = data.sort_values(
        'dataverse', kind='mergesort',
        key=lambda series: [dataverses.index(dataverse) for dataverse in series]
        )
    data = data.reset_index(drop=True)
    return data


def check_cleaned_dataset(data: DataFrame, expected_counties: int = None,
                          expected_jurisdictions: int = None) -> None:
    """
    Perform the following checks on the dataset:
    1. The dataset has exactly all expected columns.
    2. The dataset has the exact number of counties as expected (if given).
    3. The dataset has the exact number of jurisdictions as expected (if given).

    Parameters
    ----------
    data : DataFrame
        Dataverse to check.
    expected_counties : int, optional
        Number of counties expected in the dataset. The default is None.
    expected_jurisdictions : int, optional
        Number of jurisdictions expected in the dataset. The default is None.

    Raises
    ------
    AssertionError
        If any of the checks fail.

    Returns
    -------
    None.

    """

    # Assert correct column headers
    actual_columns = data.columns
    if 'municipality' not in actual_columns:
        expected_columns = _expected_dataset_columns
    else:
        expected_columns = _expected_dataset_columns_2

    err = f"Data has wrong columns: expected {expected_columns}, got {actual_columns}."
    assert set(expected_columns) == set(actual_columns), err

    # Assert correct number of counties
    if expected_counties is not None:
        actual_counties = len(data['county_name'].unique())
        err = (f"Data has wrong number of counties: expected {expected_counties}, "
               f"got {actual_counties}.")
        assert expected_counties == actual_counties, err

    # Assert correct number of jurisdictions
    if expected_jurisdictions is not None:
        actual_jurisdictions = len(data['jurisdiction_name'].unique())
        err = (f"Data has wrong number of jurisdictions: expected {expected_jurisdictions}, "
               f"got {actual_jurisdictions}.")
        assert expected_jurisdictions == actual_jurisdictions, err
    print("All checks for final data passed.")


def inspect_cleaned_dataset(data: DataFrame) -> None:
    """
    Print reports for the following:
    1. Unique values in each column.
    2. Statistics for votes.
    3. Office per dataverses.

    Parameters
    ----------
    data : DataFrame
        Dataverse to inspect.

    Returns
    -------
    None

    """

    # Individual field inspection
    print("\n\n=============================================================\n\n")
    print("INDIVIDUAL FIELD INSPECTION")
    for column in data:
        print(column)
        print("")
        print(data[column].unique())
        print("\n\n----------------\n\n")

    # Vote inspection
    print("\n\n=============================================================\n\n")
    print("VOTE INSPECTION")
    if 'votes' in data.columns:
        print(data['votes'].describe())  # check for oddities (numeric, no missing values, etc.)
    else:
        print('`votes` column is not present in the cleaned dataset, so no inspection of votes '
              'may be performed.')

    # Dataverse inspection
    print("\n\n=============================================================\n\n")
    print("DATAVERSE INSPECTION")
    if 'office' not in data.columns:
        print('`office` column is not present in the cleaned dataset, so no inspection of '
              'dataverse may be performed.')
    elif 'dataverse' not in data.columns:
        print('`dataverse` column is not present in the cleaned dataset, so no inspection of '
              'dataverse may be performed.')
    else:
        valid_dataverses = ["PRESIDENT", "SENATE", "HOUSE", "STATE", "LOCAL", ""]
        for dataverse in valid_dataverses:
            if dataverse == "":
                print('(DATAVERSE EMPTY)')
            else:
                print(dataverse)
            print(data['office'][data['dataverse'] == dataverse].unique())
            print("\n------------------\n")
        invalid_dataverse = data[~data['dataverse'].isin(valid_dataverses)]
        if not invalid_dataverse.empty:
            print('INVALID DATAVERSES')
            print(data[['dataverse', 'office']].sort_values(['dataverse', 'office']))
            print("\n------------------\n")
