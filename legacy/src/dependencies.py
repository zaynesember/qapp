import importlib
import os

packages = [
    'wheel',
    'numpy',
    'pandas',
    'Levenshtein',  # 'python-Levenshtein',
    'fuzzywuzzy',
    'tqdm',
    'openpyxl',
    'xlsxwriter',
    'xlrd',
    ]


def update_dependencies_file():
    if os.path.exists('requirements.txt'):
        file = 'requirements.txt'
    elif os.path.exists('electioncleaner/requirements.txt'):
        file = 'electioncleaner/requirements.txt'
    else:
        return

    with open(file, 'w', encoding='utf-8') as f:
        for package in packages:
            f.write(package + '\n')


def update_dependencies_file_anaconda():
    # Anaconda cannot install Levenshtein through conda-install, so we manually take it out.
    if os.path.exists('requirements_conda.txt'):
        file = 'requirements_conda.txt'
    elif os.path.exists('electioncleaner/requirements_conda.txt'):
        file = 'electioncleaner/requirements_conda.txt'
    else:
        return

    with open(file, 'w', encoding='utf-8') as f:
        for package in packages:
            if package == 'Levenshtein':
                continue
            f.write(package + '\n')


def check_dependencies():
    for package in packages:
        try:
            importlib.import_module(package)
        except ModuleNotFoundError as exc:
            err = (f'{exc}. Please install all dependencies by following the instructions in '
                   f'README.md, make sure you are in the correct virtual environment if you have '
                   f'one, and try again.')
            raise ModuleNotFoundError(err)
