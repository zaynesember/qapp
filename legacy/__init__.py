import sys

# Check system version before anything
if not (sys.version_info.major == 3 and sys.version_info.minor >= 7):
    err = ('Python 3.7 or higher is required. '
           'You are using Python %d.%d.' % (sys.version_info.major, sys.version_info.minor))
    raise RuntimeError(err)

import pathlib

# As we cannot guarantee the Python version is at least 3.7 preruntime,
# we cannot use f-strings here!

print('*Loading election cleaner module...')

# Jupyter Notebook support
_folder = str(pathlib.Path(str(pathlib.Path.cwd()) + '/qa_engine'))
if _folder not in sys.path:
    sys.path.append(_folder)
    sys.path.append(str(pathlib.Path(_folder + '/src')))

from .src import *

__all__ = src.__all__

print('Loaded election cleaner module.')
