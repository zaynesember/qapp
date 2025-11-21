import sys

if not (sys.version_info.major == 3 and sys.version_info.minor >= 7):
    err = ('Python 3.7 or higher is required. '
           'You are using Python %d.%d.' % (sys.version_info.major, sys.version_info.minor))
    raise RuntimeError(err)

from src import aggregate

if __name__ == '__main__':
    filename = ' '.join(sys.argv[1:])
    aggregate.do(filename)
