@echo off
REM Double-click this file to launch QAPP GUI on Windows

cd /d "%~dp0"

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed.
    echo Please install Python 3.9+ from https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

REM Check if virtual environment exists
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

REM Check if required packages are installed
python -c "import pandas, xlsxwriter" >nul 2>&1
if errorlevel 1 (
    echo Required packages are not installed.
    echo.
    set /p answer="Would you like to install them now? (y/n): "
    if /i "%answer%"=="y" (
        echo Installing requirements...
        python -m pip install -r requirements.txt
        if errorlevel 1 (
            echo.
            echo ERROR: Failed to install requirements.
            pause
            exit /b 1
        )
        echo.
        echo Requirements installed successfully!
    ) else (
        echo Cannot run QAPP without required packages.
        pause
        exit /b 1
    )
)

REM Launch the GUI
python gui.py
