from . import fileio

import numpy as np
import pandas as pd

DataFrame = pd.core.frame.DataFrame
Series = pd.core.series.Series

def load_file(filename: str = None) -> DataFrame:
    filename, _ = fileio.detect_file(filename, 'mode')

    data = fileio.quick_load(filename).reset_index(drop=True)
    return data, filename


def fix_column_names(data: DataFrame) -> DataFrame:
    renames = {
        'party': 'party_detailed',
        'jurisdiction': 'jurisdiction_name',
        'county': 'county_name',
        }
    data = data.rename(
        mapper=renames,
        axis=1,
        )
    return data


def fix_column_characters(data: DataFrame) -> DataFrame:
    for column in data.columns:
        if data.dtypes[column] in [np.int64, np.int32, int]:
            data[column] = fix_column_characters_int(data[column])
        elif data.dtypes[column] in [np.float64]:
            data[column] = fix_column_characters_float(data[column])
        else:
            values = data[~data[column].isna()][column].unique()
            for value in values:
                if not isinstance(value, str):
                    err = (f'Invalid value {value} in column {column}.')
                    raise RuntimeError(err)
            data[column] = fix_column_characters_str(data[column])

    return data


def fix_column_characters_int(series: Series) -> Series:
    return series


def fix_column_characters_float(series: Series) -> Series:
    return series


def fix_column_characters_str(series: Series) -> Series:
    series = series.fillna(value='').str.strip().str.upper()
    return series


def fix_column_variable_precinct(data: DataFrame) -> DataFrame:
    if 'precinct' not in data.columns:
        return data

    # No particular changes for precinct
    return data


def fix_column_variable_office(data: DataFrame) -> DataFrame:
    if 'office' not in data.columns:
        return data

    replacements = {
        '^PRESIDENT$': 'US PRESIDENT',
        }

    data['office'] = data['office'].replace(replacements, regex=True)

    return data


def fix_column_variable_party_detailed(data: DataFrame) -> DataFrame:
    if 'party_detailed' not in data.columns:
        return data

    replacements = {
        '^DEMOCRATIC$': 'DEMOCRAT',
        }
    data['party_detailed'] = data['party_detailed'].replace(replacements, regex=True)

    return data


def fix_column_variable_party_simplified(data: DataFrame) -> DataFrame:
    if 'party_simplified' not in data.columns:
        non_replacements = {
            'DEMOCRAT',
            'REPUBLICAN',
            'LIBERTARIAN',
            'NONPARTISAN',
            '',
            }
        data['party_simplified'] = data['party_detailed'].where(
            data['party_detailed'].isin(non_replacements),
            other='OTHER',
            )
        return data

    replacements = {
        '^DEMOCRATIC$': 'DEMOCRAT',
        }
    data['party_simplified'] = data['party_simplified'].replace(replacements, regex=True)
    return data


def fix_column_variable_mode(data: DataFrame) -> DataFrame:
    if 'mode' not in data.columns:
        return data

    return data


def fix_column_variable_votes(data: DataFrame) -> DataFrame:
    if 'votes' not in data.columns:
        return data

    return data


def fix_column_variable_county_name(data: DataFrame) -> DataFrame:
    if 'county_name' not in data.columns:
        return data

    return data


def fix_column_variable_county_fips(data: DataFrame) -> DataFrame:
    if 'county_fips' not in data.columns:
        return data

    return data


def fix_column_variable_jurisdiction_name(data: DataFrame) -> DataFrame:
    if 'jurisdiction_name' not in data.columns:
        return data

    return data


def fix_column_variable_jurisdiction_fips(data: DataFrame) -> DataFrame:
    if 'jurisdiction_fips' not in data.columns:
        return data

    return data


def fix_column_variable_candidate(data: DataFrame) -> DataFrame:
    if 'candidate' not in data.columns:
        return data

    return data


def fix_column_variable_district(data: DataFrame) -> DataFrame:
    if 'district' not in data.columns:
        return data

    return data


def fix_column_variable_dataverse(data: DataFrame) -> DataFrame:
    if 'dataverse' not in data.columns:
        return data

    return data


def fix_column_variable_year(data: DataFrame) -> DataFrame:
    if 'year' not in data.columns:
        return data

    return data


def fix_column_variable_stage(data: DataFrame) -> DataFrame:
    if 'stage' not in data.columns:
        return data

    return data


def fix_column_variable_state(data: DataFrame) -> DataFrame:
    if 'state' not in data.columns:
        return data

    return data


def fix_column_variable_special(data: DataFrame) -> DataFrame:
    if 'special' not in data.columns:
        return data

    return data


def fix_column_variable_writein(data: DataFrame) -> DataFrame:
    if 'writein' not in data.columns:
        return data

    return data


def fix_column_variable_state_po(data: DataFrame) -> DataFrame:
    if 'state_po' not in data.columns:
        return data

    return data


def fix_column_variable_state_fips(data: DataFrame) -> DataFrame:
    if 'state_fips' not in data.columns:
        return data

    return data


def fix_column_variable_state_cen(data: DataFrame) -> DataFrame:
    if 'state_cen' not in data.columns:
        return data

    return data


def fix_column_variable_state_ic(data: DataFrame) -> DataFrame:
    if 'state_ic' not in data.columns:
        return data

    return data


def fix_column_variable_date(data: DataFrame) -> DataFrame:
    if 'date' not in data.columns:
        return data

    return data


def fix_column_variable_readme_check(data: DataFrame) -> DataFrame:
    if 'readme_check' not in data.columns:
        return data

    return data


def fix_column_variable_magnitude(data: DataFrame) -> DataFrame:
    if 'magnitude' not in data.columns:
        return data

    return data


def save_file(data: DataFrame, original_filename: str = None):
    filename = original_filename.replace('.csv', '-autoadapted.csv')
    fileio.save_cleaned_dataset(data, filename, save_zip=False)


def do(filename: str = None) -> None:
    if filename is None:
        err = ('Expected filename.')
        raise RuntimeError(err)

    print('Starting the MEDSL automated adapter of old primary and general election precinct '
          'results...')
    print(f'*Loading file {filename}...')
    raw_data, filename = load_file(filename=filename)
    print(f'Loaded file {filename}...')
    data = raw_data.copy()

    print('*Fixing column names...')
    data = fix_column_names(data)
    print('Fixed column names.')

    print('*Fixing column character values...')
    data = fix_column_characters(data)
    print('Fixed column character values...')

    print('*Fixing column values...')
    data = fix_column_variable_precinct(data)
    data = fix_column_variable_office(data)
    data = fix_column_variable_party_detailed(data)
    data = fix_column_variable_party_simplified(data)
    data = fix_column_variable_mode(data)
    data = fix_column_variable_votes(data)
    data = fix_column_variable_county_name(data)
    data = fix_column_variable_county_fips(data)
    data = fix_column_variable_jurisdiction_name(data)
    data = fix_column_variable_jurisdiction_fips(data)
    data = fix_column_variable_candidate(data)
    data = fix_column_variable_district(data)
    data = fix_column_variable_dataverse(data)
    data = fix_column_variable_year(data)
    data = fix_column_variable_stage(data)
    data = fix_column_variable_state(data)
    data = fix_column_variable_special(data)
    data = fix_column_variable_writein(data)
    data = fix_column_variable_state_po(data)
    data = fix_column_variable_state_fips(data)
    data = fix_column_variable_state_cen(data)
    data = fix_column_variable_state_ic(data)
    data = fix_column_variable_date(data)
    data = fix_column_variable_readme_check(data)
    data = fix_column_variable_magnitude(data)
    print('Fixed column values.')

    save_file(data, original_filename=filename)
