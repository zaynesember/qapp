"""
Module that contains the Base class for all field classes.
"""

import configparser
import pathlib
import re
import sys

from enum import Enum
from typing import Dict, List, Set, Tuple

import pandas as pd

from fuzzywuzzy import process
from tqdm import tqdm

try:
    from . import fileio, miscellaneous
except ImportError:
    from src import fileio, miscellaneous

DataFrame = pd.core.frame.DataFrame
Series = pd.core.series.Series

__all__ = (
    'Field',
    )


class Field():
    DEFAULT_SIMILARITIES = miscellaneous.EMPTY_ENUM
    DEFAULT_TEXT_CHECKS = {
        # Only allow values with no lowercase
        'LOWERCASE': r'[a-z]+',
        # Only allow values such that for symbols:
        # There are no any conseuctive symbols. The only allow consecutive symbols are the double
        # quotation marks, but only if the value is exactly ""
        'EXTRANEOUS CONSECUTIVE SYMBOLS':
            r'(?!^\"\"$)\"\"|\-\-|\'\'|  |\/\/',
        # Only allow values such that for spaces:
        # It is not the first or last character, nor followed by a space
        'EXTRANEOUS SPACES':
            r'(^ )|( $)',
    }
    TEXT_CHECKS_ALLOW_LOWERCASE = {
        # Only allow values such that for symbols:
        # There are no any conseuctive symbols
        'EXTRANEOUS CONSECUTIVE SYMBOLS':
            r'(?!^\"\"$)\"\"|\-\-|\'\'|  |\/\/',
        # Only allow values such that for spaces:
        # It is not the first or last character, nor followed by a space
        'EXTRANEOUS SPACES':
            r'(^ )|( $)',
        }
    SEARCH_DUPLICATES_IN_VALUES = True
    SEARCH_SIMILAR_IN_COLUMN = True

    def __init__(self, name: str = None,
                 base: str = None,
                 output_file: str = None,
                 precinct_base: str = None,
                 similarities: Enum = None,
                 text_checks: Enum = None,
                 search_duplicates_in_values: bool = None,
                 search_similar_in_column: bool = None,
                 ):
        if name is None:
            name = type(self).__name__.lower()
        if base is None:
            base = str(pathlib.Path(r'electioncleaner/output'))
        if output_file is None:
            output_file = str(pathlib.Path(rf'{base}/{name}/{name}.txt'))
        if precinct_base is None:
            # Set precinct base from ini
            _default_config = dict()
            _default_config['Paths'] = {
                'precinct_base': '..',
                }
            _config = configparser.ConfigParser(defaults=_default_config)
            if not _config.read('config.ini'):
                _config.read(str(pathlib.Path(r'electioncleaner/config.ini')))
            #_config.read(str(pathlib.Path(rf'{base}/config.ini')))
            # breakpoint()
            precinct_base = _config['Paths']['precinct_base']
        if similarities is None:
            similarities = self.DEFAULT_SIMILARITIES
        if text_checks is None:
            text_checks = self.DEFAULT_TEXT_CHECKS
        if search_duplicates_in_values is None:
            search_duplicates_in_values = self.SEARCH_DUPLICATES_IN_VALUES
        if search_similar_in_column is None:
            search_similar_in_column = self.SEARCH_SIMILAR_IN_COLUMN

        self._name = name
        self._base = base
        self._similarities = similarities
        self._text_checks = text_checks
        self._search_duplicates_in_values = search_duplicates_in_values
        self._search_similar_in_column = search_similar_in_column

        self._default_output_file = output_file
        self._precinct_base = precinct_base

    @staticmethod
    def _explore(values: List[str] = None,
                 search_like: Set[str] = None,
                 sensitivity: int = 90,
                 verbose: bool = True,
                 alt_exact_match: bool = False) -> Dict[str, List[Tuple[str, int]]]:
        all_matches = dict()
        values_to_search = sorted(values, key=len)

        def _iterate(pbar=None):
            for (i, value) in enumerate(values_to_search):
                condensed_value = re.sub(r'\.|,|-', '', value.strip())
                condensed_value = re.sub(r' ( )+', ' ', condensed_value)
                entries = search_like if search_like is not None else values_to_search[i+1:]

                for search_like_entry in entries:
                    # Explicitly prevent 'valid' empty strings to fuzzy match, as they raise
                    # warnings otherwise
                    if condensed_value == '""' or search_like_entry == '""':
                        match = None
                    else:
                        match = process.extract(condensed_value, [search_like_entry])
                    if not alt_exact_match and match and match[0][1] >= sensitivity:
                        all_matches[value] = match
                        continue
                    if not alt_exact_match and search_like_entry in condensed_value:
                        all_matches[value] = [(search_like_entry, None)]
                        continue
                    if alt_exact_match and condensed_value == search_like_entry:
                        all_matches[value] = [(search_like_entry, None)]
                        continue
                if pbar:
                    pbar.update(1)

        pbar = tqdm(total=len(values_to_search), file=sys.stdout) if verbose else None
        if pbar:
            with pbar:
                _iterate(pbar=pbar)
        else:
            _iterate()

        return all_matches

    def check_characters(self, values: List[str],
                         filename: str = None,
                         overwrite: bool = True,
                         text_checks: Dict[str, str] = None,
                         verbose: bool = True):
        name = self._name
        if filename is None:
            filename = str(pathlib.Path(rf'{self._base}/check_characters.txt'))
        if text_checks is None:
            text_checks = self._text_checks

        fileio.make_dir_if_needed(filename)
        if overwrite:
            fileio.remove_file_if_present(filename)
        if verbose:
            print('------', flush=True)
            print(f'*Starting character query for {name}...', flush=True)

        issues = False
        output = list()
        output.append('------------\n')
        output.append('CHARACTER CHECK\n\n')
        for (checking, regex) in text_checks.items():
            output.append('------\n')
            output.append(f'{checking}\n')
            bad_values = [value for value in values if re.search(regex, value)]
            if not bad_values:
                output.append('    No Problems Found :) \n')
            else:
                issues = True
                for bad_value in bad_values:
                    output.append(f'    {bad_value}\n')
            output.append('------\n\n')
        output.append('------------\n\n\n')

        with open(filename, 'a+', encoding='utf-8') as f:
            f.writelines(output)

        if issues:
            self._write_summary(filename, "CHARACTER CHECK")

        if verbose:
            print(f'\nSaved character query to {filename}.', flush=True)
            print('------\n', flush=True)

    @staticmethod
    def _list_has_empty(values: List[str], enum_with_empties: Enum):
        empties_set = set(enum_with_empties.EXACT_EMPTY.value)
        if set(values).intersection(empties_set):
            return True
        return False

    def _write_summary(self, filename: str = None,
                       currentCheck: str = None):
        summary_file = str(pathlib.Path(rf'{self._base}/SUMMARY.txt'))
        name_to_print = filename.replace(self._base+'/','')
        with open(summary_file, 'a+', encoding='utf-8') as f:
            f.writelines(currentCheck + " found potential issues in "+\
                         name_to_print+"\n")

    def _check_similarities_one(self, values: List[str] = None,
                                sensitivity: int = 90,
                                to_search: str = None,
                                to_search_like: Set[str] = None,
                                similarities: Enum = None,
                                verbose: bool = True,) -> Dict[str, List[Tuple[str, int]]]:
        name = self._name
        if values is None:
            values = list()
        if similarities is None:
            similarities = miscellaneous.EMPTY_ENUM
        office_names = [office_pair.name for office_pair in similarities]
        if to_search_like is None and to_search in office_names:
            underscored_name = to_search.replace(' ', '_')
            to_search_like = similarities[underscored_name].value
        if to_search is None:
            to_search = '!!! UNSPECIFIED !!!'

        if verbose:
            print(f'\n**Exploring column {name} for {to_search}...', flush=True)
        if self._list_has_empty(values, similarities) and verbose:
            print(f'WARNING: Empty values detected in {name} column!', flush=True)

        explored = self._explore(values=values,
                                 search_like=to_search_like,
                                 sensitivity=sensitivity,
                                 verbose=verbose,
                                 alt_exact_match=to_search.startswith('EXACT'))
        return explored

    def check_similarities(self, values: List[str],
                           sensitivity: int = 90,
                           filename: str = None,
                           overwrite: bool = True,
                           similarities: Enum = None,
                           search_duplicates_in_values: bool = None,
                           search_similar_in_column: bool = None,
                           verbose: bool = True,):
        name = self._name
        if filename is None:
            filename = str(pathlib.Path(f'{self._base}/similarities_{name}_{sensitivity}.txt'))
        if similarities is None:
            similarities = self._similarities
        if search_duplicates_in_values is None:
            search_duplicates_in_values = self._search_duplicates_in_values
        if search_similar_in_column is None:
            search_similar_in_column = self._search_similar_in_column

        fileio.make_dir_if_needed(filename)
        if overwrite:
            fileio.remove_file_if_present(filename)
        if verbose:
            print('------', flush=True)
            print(f'*Starting similarity query for {name}...', flush=True)
            print(f'**Exploring column {name} for PREDETERMINED PATTERNS...')

        output = list()
        output.append('------------\n')
        output.append('SIMILARITY CHECK\n\n')
        if self._list_has_empty(values, self._similarities) and verbose:
            output.append(f'WARNING: Empty values detected in {name}!\n')

        def _perform(pbar=None):
            issues = False

            for office_pair in similarities:
                # Change underscores to space from fields
                office_name = office_pair.name.replace('_', ' ')
                to_search_like = office_pair.value
                explored = self._check_similarities_one(
                    values=values,
                    sensitivity=sensitivity,
                    to_search=office_name,
                    to_search_like=to_search_like,
                    similarities=similarities,
                    verbose=False,)
                output.append('------\n')
                output.append(f'CONTAINS/IS SIMILAR TO {office_name}: \n')
                if not explored:
                    output.append('    No Problems Found :) \n')
                else:
                    issues = True
                for (value, closest_matches) in explored.items():
                    output.append(f'    {value} ||| [[{closest_matches[0][0]}]]\n')
                output.append('------\n\n')
                if pbar:
                    pbar.update(1)
            if issues:
                self._write_summary(filename, "SIMILARITY CHECK")

        pbar = tqdm(total=len(similarities), file=sys.stdout) if verbose else None
        if pbar:
            with pbar:
                _perform(pbar=pbar)
        else:
            _perform()

        if search_duplicates_in_values:
            if verbose:
                print(f'\n**Exploring column {name} for DUPLICATE WORDS WITHIN '
                      f'ENTRIES...', flush=True)
            values_to_search = values

            def _perform_duplicate(pbar=None):
                values_but_each_split = [value.split(' ') for value in
                                         values_to_search]
                values_with_duplicates = list()
                for split_value in values_but_each_split:
                    dup = {word for word in split_value
                           if split_value.count(word) > 1}
                    if dup:
                        values_with_duplicates.append((' '.join(split_value), dup))
                    if pbar:
                        pbar.update(1)

                issues = False
                output.append('------\n')
                output.append(f'VALUES IN {name} WITH DUPLICATE WORDS: \n')
                if not values_with_duplicates:
                    output.append('    No Problems Found :) \n')
                else:
                    issues = True
                for (value, duplicate_words) in values_with_duplicates:
                    output.append(f'    {value} ||| {duplicate_words}\n')
                output.append('------\n\n')
                if issues:
                    self._write_summary(filename, "DUPLICATES CHECK")

            if verbose:
                pbar = tqdm(total=len(values_to_search), file=sys.stdout)
                with pbar:
                    _perform_duplicate(pbar=pbar)
            else:
                _perform_duplicate()

        if search_similar_in_column:
            explored = self._check_similarities_one(
                values=values,
                sensitivity=sensitivity,
                to_search='SIMILAR VALUES IN COLUMN',
                to_search_like=None,
                similarities=None,
                verbose=verbose,)
            output.append('------\n')
            output.append(f'SIMILAR VALUES IN {name}: \n')
            if not explored:
                output.append('   No Problems Found :) \n')
            for (value, closest_matches) in explored.items():
                output.append(f'    {value} ||| [[{closest_matches[0][0]}]]\n')
            output.append('------\n\n')

        output.append('------------\n\n\n')
        with open(filename, 'a+', encoding='utf-8') as f:
            f.writelines(output)

        if verbose:
            print(f'\nSaved similarity query for {name} to {filename}.', flush=True)
            print('------\n', flush=True)

    def build_attribute_map(self, data: DataFrame,
                            output: List[str],
                            fields: List[str],
                            verbose: bool = True):
        name = self._name

        for field_name in fields:
            if field_name not in data:
                output.append(f'Unable to report {name} attributes: {field_name} field missing.\n')
                return dict()

        if verbose:
            print(f'*Building data structure for {name} attributes...', flush=True)
        by_field = data.groupby(fields)[name]
        fields_dict = dict()

        def _build(pbar=None):
            for (attributes, fields) in by_field:
                fields_tuple = tuple(set(fields))
                if fields_tuple not in fields_dict:
                    fields_dict[fields_tuple] = list()
                fields_dict[fields_tuple].append(attributes)
                if pbar:
                    pbar.update(1)

        if verbose:
            with tqdm(total=len(by_field.size()), file=sys.stdout) as pbar:
                _build(pbar=pbar)
            print('Built data structure.\n', flush=True)
        else:
            _build()

        if verbose:
            print(f'*Building {name} to election attributes map...')

        output.append('------\n')
        output.append(f'{name.upper()} TO ELECTION ATTRIBUTES MAP:\n')
        output.append(f'Attributes: {fields}\n')
        for (fields_tuple, attributes_list) in fields_dict.items():
            output.append(f'    {fields_tuple}\n')
            if len(attributes_list) <= 6:
                to_check = attributes_list
            else:
                to_check = (attributes_list[0:3] +
                            [f'...(skipping {len(attributes_list)-6} elements)'] +
                            attributes_list[-3:])
            for attributes in to_check:
                output.append(f'        {attributes}\n')
            output.append('\n')
        output.append('------\n\n')

        if verbose:
            print(f'Built {name} to election attributes map.', flush=True)
            print('------\n', flush=True)

        return fields_dict

    def check_special(self, data: DataFrame = None,
                      filename: str = None,
                      overwrite: bool = True,
                      verbose: bool = True,):
        """
        Custom checks. Override in children implementation.

        Parameters
        ----------
        data : pandas.core.frame.DataFrame
            Original dataframe
        filename : str
            Place to save the report for this field.
        overwrite : bool
            If True, it will remove file filename if it exists first before saving the report.
            If False, it will save the report at the end of the file's contents if it exists.
            In either case, if the file does not exist, it will create a new one.
        verbose : bool
            If True, status messages and possibly status bars will be printed to stdout. If False,
            no such output will be printed.

        Returns
        -------
        None.

        """

        # pass

    def check_unique(self, data: DataFrame = None, filename: str = None,
                     verbose: bool = True,) -> List[str]:
        if filename is None:
            filename = self._default_output_file
        if verbose:
            print('------', flush=True)
            print('*Starting uniqueness check...', flush=True)

        values = miscellaneous.obtain(column=data[self._name], intended_type=str)
        output = list()
        output.append('------\n')
        output.append(f'{self._name.upper()} UNIQUENESS CHECK:\n')

        issues = False
        if len(values) == 1:
            output.append(f'    Detected 1 {self._name}: {values[0]}\n')
        else:
            issues = True
            output.append(f'    Detected {len(values)} {self._name}s (see output below)\n')
        if issues:
            self._write_summary(filename, "UNIQUENESS CHECK")
        output.append('------\n\n')

        if verbose:
            print('Completed uniqueness query.', flush=True)
            print('------\n', flush=True)
        return output

    def check_all(self, data: DataFrame = None,
                  column: str = None,
                  sensitivity: int = 90,
                  filename: str = None,
                  overwrite: bool = True,
                  verbose: bool = True,):
        if filename is None:
            filename = self._default_output_file
        if column is None:
            column = self._name

        if column not in data:
            raise KeyError(f'{column} is not a column in the dataset.')

        if verbose:
            print(f'*Checking {self._name}. Results will be saved to {filename}...',
                  flush=True)
        fileio.make_dir_if_needed(filename)
        if overwrite:
            fileio.remove_file_if_present(filename)

        with open(filename, 'a+', encoding='utf-8') as f:
            f.write('---------------------------\n')
            f.write('---------------------------\n')
            f.write(f'{self._name.upper()} CHECK\n')
            f.write('---------------------------\n')
            f.write('---------------------------\n\n')

        filtered_values = miscellaneous.obtain(column=data[column], intended_type=str)
        try:
            self.check_characters(filtered_values,
                                  filename=filename,
                                  overwrite=False,
                                  verbose=verbose,)
        except KeyboardInterrupt:
            print('Aborted character query.')
        try:
            self.check_similarities(filtered_values,
                                    sensitivity=sensitivity,
                                    filename=filename,
                                    overwrite=False,
                                    verbose=verbose)
        except KeyboardInterrupt:
            print('Aborted similarity query.')

        try:
            self.check_special(data,
                               filename=filename,
                               overwrite=False)
        except KeyboardInterrupt:
            print('Aborted special query.')

        with open(filename, 'a+', encoding='utf-8') as f:
            f.write('---------\n')
            f.write('------\n')
            f.write('ALL VALUES:\n')
            for value in filtered_values:
                f.write(f'    {value}\n')
            f.write('------\n\n')

        if verbose:
            print(f'All checks for {self._name} done. Results were saved to {filename}.',
                  flush=True)

    def check_file_all(self, year: int = None,
                       state_abbr: str = None,
                       filename: str = None,
                       sensitivity: int = 90,
                       verbose: bool = True,):
        name = self._name
        if filename is None:
            filename = str(pathlib.Path(rf'{self._base}/{name}/{year}-{state_abbr}-{name}.txt'))
        to_load_path = pathlib.Path(rf'{self._precinct_base}/{year}/{state_abbr}/'
                                    rf'{year}-{state_abbr}-precinct-primary.csv')
        if not to_load_path.resolve().exists():
            to_load_path = pathlib.Path(rf'{self._precinct_base}/{year}/{state_abbr}/'
                                        rf'{year}-{state_abbr}-precinct-general.csv')

        to_load = str(to_load_path)

        if verbose:
            print(f'\n*Checking {to_load} for column {name}...', flush=True)

        data = fileio.quick_load(to_load)
        if verbose:
            print(f'*Identified {len(data[name].unique())} unique values...', flush=True)

        self.check_all(data=data, column=name, sensitivity=sensitivity, filename=filename)
        if verbose:
            print(f'All checks for {to_load} done!\n', flush=True)

    def check_files_all(self, sensitivity: int = 90):
        for (year, state_abbr) in fileio.AVAILABLE_DATASETS:
            self.check_file_all(year=year, state_abbr=state_abbr, sensitivity=sensitivity)
