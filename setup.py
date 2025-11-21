from setuptools import setup, find_packages

setup(
    name='qa_v2',
    version='2.0.0',
    author='Zayne',
    description='Refactored MEDSL Precinct QA Engine (original by sbaltz, refactored by Zayne, 2025)',
    packages=find_packages(),
    install_requires=['pandas>=2.0.0', 'numpy>=1.25.0'],
    python_requires='>=3.8',
)
