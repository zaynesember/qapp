from setuptools import setup, find_packages
from os import path

from .src import dependencies

here = path.abspath(path.dirname(__file__))
with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
      name='medslcleaner',
      version='0.4.10',
      description='Tools for cleaning election returns',
      long_description=long_description,
      url='https://github.mit.edu/MEDSL/medslCleanR2/',
      author='MEDSL',
      author_email='mitelectionlab@mit.edu',
      classifiers=[
          'Development Status :: 1 - Planning',
          'Intended Audience :: Developers of election return cleaners',
          'Topic :: Software Development :: Build Tools',
          'License :: MIT License',
          'Programming Language :: Python :: 3',
          'Programming Language :: Python :: 3.7',
          'Programming Language :: Python :: 3.8',
          'Programming Language :: Python :: 3.9'],
      keywords='elections cleaner tools development',
      package_dir={'': 'src'},
      packages=find_packages(where='src'),
      python_requires='>=3.7, <4',
      install_requires=dependencies.packages,
      extras_require=dict(),
      package_data=dict(),
      entry_points=dict(),
      project_urls={
          'Home page': 'http://electionlab.mit.edu',
      },
)
