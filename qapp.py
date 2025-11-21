#!/usr/bin/env python3
"""
Entry point for QAPP (Quality Assurance for the Precinct Project)

Usage:
    python qapp.py <PATH_TO_CSV>
"""
import sys
from pathlib import Path

# Make qa_core importable when running from the top-level qapp directory
sys.path.append(str(Path(__file__).resolve().parent))

from qa_core.runner import run_qa  # correct entry point

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python qapp.py <PATH_TO_CSV>")
        sys.exit(1)
    data_path = sys.argv[1]
    run_qa(data_path)
