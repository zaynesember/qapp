# MEDSL Election Cleaner

Python tools for cleaning election returns.

Requires Python 3.7+.

## Installation

1. Clone or download this repository.
  - If you will use the election cleaner tools as a Python library, move the electioncleaner folder (not the repository folder) to the folder containing your state cleanup code and rename the election cleaner folder to `electioncleaner` if needed. Alternatively, you may place the repository folder anywhere you want and create a symlink in your state project folder to it (essentially a shortcut) as follows:
    - On Windows: in PowerShell, do
	```
	New-Item -ItemType Junction -Path "directory\to\your\state\project\electioncleaner" -Target "directory\where\you\placed\the\electioncleaner\folder"
	```

	For example

	```
	New-Item -ItemType Junction -Path "D:\MIT\MEDSL\2020-precincts\precinct\AK\electioncleaner" -Target "D:\MIT\MEDSL\medslCleanR2\Python\electioncleaner"
	```

    - On Mac/Linux: in your Terminal, do
	```
	ln -s "directory/where/you/placed/the/electioncleaner/folder" "directory/to/your/state/project/electioncleaner"
	```

	For example
	```
	ln -s "/Users/user/MIT/MEDSL/medslCleanR2/Python/electioncleaner" "/Users/user/MIT/MEDSL/2020-precincts/precinct/AK/electioncleaner"
	```
  - If you will use the election cleaner mostly independent of any particular state project, you may place the electioncleaner folder (not the repository folder) anywhere you want (downloads or documents folder are fine, as long as you remember where it is).
2. Install the latest version of Python. **Python 2 will not work**.
  - You can download Python from its official website [here](https://www.python.org/downloads/). If you already have Python installed, check that your Python version satisfies the version requirement listed above.
  - If prompted during the installation to add `python` as a PATH environment variable, accept this option. You may see this option appear on the very first screen during the installation process.  
3. If you are on Windows and do not have Visual Studio or Visual C++ 14 installed, install Visual Studio Build Tools 2019.
  - You may download Build Tools from its official website [here](https://visualstudio.microsoft.com/thank-you-downloading-visual-studio/?sku=BuildTools&rel=16).
  - On installation, when prompted to select components to install, choose "C++ build Tools" under the Workloads tab, and select the optional items "MSVC v142 - VS 2019 C++ x64/x86 build tools" and "Windows 10 SDK (10.0.18362.0)". If higher number versions of these are available, select those instead.
  - You may need to restart your computer after the installation is complete.
4. In your console (PowerShell, Command Prompt, Terminal, etc.), change directory to the electioncleaner folder.
5. Install all dependencies by typing in the following in console:
  ```
  python -m pip install --upgrade pip
  ```
  
  and after that,
  
  ```
  python -m pip install --user -r requirements.txt
  ```
6. If you want to use the electioncleaner with conda, there is one additional step.
  - Open `Anaconda Prompt (anaconda3)` and change directory to the electioncleaner folder. If you typically use a custom environment, activate it now.
  - In the console, type
  ```
  conda update --all
  ```
  
  then, 
  ```
  conda install -c conda-forge fuzzywuzzy
  ```  
  
  and finally
  ```
  conda install --file requirements_conda.txt
  ``` 
  
  - If prompted to proceed at any point, type Y and push Enter.
  
## Run the QA checker in console

1. Open `config_sample.ini` with Notepad or your favorite text editor, perform the following changes, then save.
  - Change the `precinct_base` value to the location of your `primary-precincts` base folder (the one with these folders: `2016`, `2018`, `help-files`, etc.) or `2020-precincts` base folder (the one with these folders: `county`, `demo`, `help-files`, etc.). Do not include trailing slashes.
2. Rename `config_sample.ini` to `config.ini`.
3. In your console (PowerShell, Command Prompt, Terminal, etc.), change directory to the folder containing this README file.
4. Type in the following (include quotation marks around the path) in console:
  ```
  python qa.py "complete/path/to/the/csv/file/to/QA/check.csv"
  ```
  
  - If your election cleaner folder is in a state folder, you may just run `python qa.py` and not include the path to the CSV file to check, provided that file is in your state folder and called `year-po-precinct-primary.csv` or `year-po-precinct-general.csv` (e.g. `2016-ak-precinct-primary.csv`).
  
5. Let the script run to completion.
  - You will find reports for all fields in the folder `output/qa/name-of-the-file-that-was-checked/`. If you just ran `python qa.py`, you will find those reports in a newly created folder `qa` in your state folder.
  - If one particular test takes too long, you may push Ctrl+C or Cmd+C to skip the test.
  - Clicking on your console while the script is running may cause it to halt. If you find yourself in that situation, push Enter to continue.
