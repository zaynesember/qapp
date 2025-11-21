import pathlib
import pandas as pd

from . import fileio, miscellaneous

DataFrame = pd.core.frame.DataFrame
Series = pd.core.series.Series

__all__ = (
    'do',
    'aggregate_all'
    )


def do(filename: str) -> None:
    print('Starting the MEDSL automated aggregator for primary and general election precinct '
          'results cleaning...')

    filename, aggregate_folder = fileio.detect_file(filename, 'aggregate')

    print(f'*Loading data from {filename}...')
    data = fileio.quick_load(filename)
    print('Loaded data.\n')

    base = str(pathlib.Path(aggregate_folder))
    aggregate_all(data, base=base)


def aggregate_all(data: DataFrame,
                  base: str = None) -> None:
    if base is None:
        base = str(pathlib.Path('electioncleaner/output/aggregate'))
    print('*Aggregating dataset.')
    data = data.fillna(miscellaneous.EMPTY_RECORD)
    try:
        _aggregate(data, base=base)
    except KeyboardInterrupt:
        print('Canceled remaining aggregations.')

    print('All dataset aggregations done.')


def _aggregate(data: DataFrame,
               base: str = None) -> None:
    general_aggregate = str(pathlib.Path(f'{base}/aggregate1.csv'))
    fileio.make_dir_if_needed(general_aggregate)
    fileio.save_aggregate(data=data,
                          filename=general_aggregate)
    fileio.convert_csv_to_excel(general_aggregate)
    print('Saved general aggregate file.')

    contest_aggregate = str(pathlib.Path(f'{base}/aggregate2.csv'))
    fileio.make_dir_if_needed(contest_aggregate)
    fileio.save_contest_aggregate(data=data,
                                  filename=contest_aggregate)
    fileio.convert_csv_to_excel(contest_aggregate)
    print('Saved aggregate by contest file.')

    candidate_aggregate = str(pathlib.Path(f'{base}/aggregate3.csv'))
    fileio.make_dir_if_needed(candidate_aggregate)
    fileio.save_candidate_aggregate(data=data,
                                    filename=candidate_aggregate)
    fileio.convert_csv_to_excel(candidate_aggregate)
    print('Saved aggregate by candidate file.')

    county_aggregate = str(pathlib.Path(f'{base}/aggregate4.csv'))
    fileio.make_dir_if_needed(county_aggregate)
    fileio.save_county_aggregate(data=data,
                                 filename=county_aggregate)
    fileio.convert_csv_to_excel(county_aggregate)
    print('Saved aggregate by county file.')
