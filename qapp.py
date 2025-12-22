#!/usr/bin/env python3
"""QAPP CLI.

By default this runs the refactored QA engine (qa_core).

Use --legacy to run the original legacy engine (sbaltz) which emits the
legacy text outputs (e.g., stage1_columns.txt, stage1_field_*.txt) under
output/qa/<input_stem>/.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="qapp", add_help=True)
    parser.add_argument("csv_path", help="Path to input CSV")
    parser.add_argument(
        "--legacy",
        action="store_true",
        help="Run the legacy sbaltz engine (writes output/qa/<input_stem>/ text reports)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    args = _parse_args(argv)
    csv_path = Path(args.csv_path)

    # Ensure repo root is on sys.path when invoked from elsewhere.
    repo_root = Path(__file__).resolve().parent
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    if args.legacy:
        # The legacy engine expects to import modules as `src.*` (or
        # `electioncleaner.src.*`). Add `legacy/` to sys.path so `src` resolves
        # to `legacy/src` when running from repo root.
        legacy_root = repo_root / "legacy"
        if str(legacy_root) not in sys.path:
            sys.path.insert(0, str(legacy_root))

        # Import lazily so normal runs don't pull in legacy deps/side effects.
        from src.qa import do as legacy_do

        legacy_do(str(csv_path))
        return 0

    from qa_core.runner import run_qa

    run_qa(str(csv_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
