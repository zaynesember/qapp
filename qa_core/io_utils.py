"""
io_utils.py — File loading and normalization utilities

Original QA engine by sbaltz.
Refactored and extended by Zayne (2025).
"""

from __future__ import annotations
import pandas as pd
import pathlib
import logging
from qa_core import config


def detect_delimiter(path: pathlib.Path) -> str:
    """Infer delimiter based on extension or simple sniffing."""
    if path.suffix.lower() == ".tsv":
        return "\t"
    if path.suffix.lower() == ".csv":
        return ","
    with open(path, "r", encoding="utf-8") as f:
        head = f.readline()
    return "\t" if "\t" in head else ","


def load_data(path: pathlib.Path) -> pd.DataFrame:
    """Load dataset and normalize missing values."""
    delim = detect_delimiter(path)
    df = pd.read_csv(path, delimiter=delim, dtype=str, na_values=config.MISSING_TOKENS)
    df = df.fillna(config.EMPTY_RECORD)
    logging.info(f"Loaded {path.name} with {len(df):,} rows.")
    return df
