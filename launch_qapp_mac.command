#!/bin/bash
# Double-click this file to launch QAPP GUI

# Change to the script's directory
cd "$(dirname "$0")"

# Check if Python is available
if ! command -v python3 &> /dev/null && ! command -v python &> /dev/null; then
    echo "ERROR: Python is not installed."
    echo "Please install Python 3.9+ from https://www.python.org/downloads/"
    echo ""
    read -p "Press Enter to close..."
    exit 1
fi

# Use python3 if available, otherwise python
PYTHON_CMD="python3"
if ! command -v python3 &> /dev/null; then
    PYTHON_CMD="python"
fi

# Check if virtual environment exists and activate it
if [ -d ".venv" ]; then
    source .venv/bin/activate
    PYTHON_CMD="python"
fi

# Check if required packages are installed
$PYTHON_CMD -c "import pandas, xlsxwriter" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "Required packages are not installed."
    echo ""
    read -p "Would you like to install them now? (y/n): " answer
    if [ "$answer" = "y" ] || [ "$answer" = "Y" ]; then
        echo "Installing requirements..."
        $PYTHON_CMD -m pip install -r requirements.txt
        if [ $? -ne 0 ]; then
            echo ""
            echo "ERROR: Failed to install requirements."
            read -p "Press Enter to close..."
            exit 1
        fi
        echo ""
        echo "Requirements installed successfully!"
    else
        echo "Cannot run QAPP without required packages."
        read -p "Press Enter to close..."
        exit 1
    fi
fi

# Launch the GUI
$PYTHON_CMD gui.py
