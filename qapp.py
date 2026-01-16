#!/usr/bin/env python3
"""QAPP CLI.

By default this runs the refactored QA engine (qa_core) and outputs an Excel report.

Use --legacy to run the original legacy engine (sbaltz) which emits the
legacy text outputs (e.g., stage1_columns.txt, stage1_field_*.txt) under
output/qa/<input_stem>/.

Use --output to control output format: 'excel' (default), 'legacy', or 'both'.

Use --checks to specify which checks to run (comma-separated list of check keys).
Use --list-checks to see available check keys.
Use --filter-columns to run only checks that apply to specific columns.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="qapp", add_help=True)
    parser.add_argument("csv_path", nargs="?", help="Path to input CSV")
    parser.add_argument(
        "--legacy",
        action="store_true",
        help="Run the legacy sbaltz engine (writes output/qa/<input_stem>/ text reports)",
    )
    parser.add_argument(
        "--output",
        choices=["excel", "legacy", "both"],
        default="excel",
        help="Output format: 'excel' (default), 'legacy', or 'both'",
    )
    parser.add_argument(
        "--checks",
        type=str,
        default=None,
        help="Comma-separated list of check keys to run (e.g., 'columns,fields,duplicates')",
    )
    parser.add_argument(
        "--filter-columns",
        type=str,
        default=None,
        help="Comma-separated list of column names to filter checks by",
    )
    parser.add_argument(
        "--list-checks",
        action="store_true",
        help="List available check keys and exit",
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Launch the graphical user interface",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    args = _parse_args(argv)

    # Ensure repo root is on sys.path when invoked from elsewhere.
    repo_root = Path(__file__).resolve().parent
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    # Handle --list-checks
    if args.list_checks:
        from qa_core import config
        print("Available checks:")
        print("-" * 60)
        for key, info in config.AVAILABLE_CHECKS.items():
            cols = ", ".join(info.get("columns", [])) or "(all columns)"
            print(f"  {key:25s} - {info['label']}")
            print(f"                            Columns: {cols}")
        return 0

    # Handle --gui
    if args.gui:
        from gui import main as gui_main
        gui_main()
        return 0

    # Require csv_path for non-GUI, non-list modes
    if not args.csv_path:
        print("Error: csv_path is required unless using --list-checks or --gui")
        return 1

    csv_path = Path(args.csv_path)

    # Handle legacy-only mode (--legacy flag)
    if args.legacy:
        # Detect state from filename (token before first underscore, uppercased)
        state_code = csv_path.stem.split("_")[0].upper()
        
        # Create output directory: output/<STATE>/legacy/
        output_dir = repo_root / "output" / state_code / "legacy"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # The legacy engine expects to import modules as `src.*` (or
        # `electioncleaner.src.*`). Add `legacy/` to sys.path so `src` resolves
        # to `legacy/src` when running from repo root.
        legacy_root = repo_root / "legacy"
        if str(legacy_root) not in sys.path:
            sys.path.insert(0, str(legacy_root))

        # Import lazily so normal runs don't pull in legacy deps/side effects.
        from src.qa import qa_all
        from src.fileio import quick_load
        
        print(f"Running legacy QA engine, output to: {output_dir}")
        data = quick_load(str(csv_path))
        qa_all(str(csv_path), data, base=str(output_dir))
        return 0

    # Modern engine (handles excel, legacy, or both via output_mode)
    from qa_core.runner import run_qa, OUTPUT_EXCEL, OUTPUT_LEGACY, OUTPUT_BOTH

    include_checks = None
    if args.checks:
        include_checks = set(c.strip() for c in args.checks.split(","))
    elif args.filter_columns:
        from qa_core import config
        cols = [c.strip() for c in args.filter_columns.split(",")]
        include_checks = set(config.get_checks_for_columns(cols))

    # Map output argument to mode constant
    output_mode_map = {"excel": OUTPUT_EXCEL, "legacy": OUTPUT_LEGACY, "both": OUTPUT_BOTH}
    output_mode = output_mode_map.get(args.output, OUTPUT_EXCEL)
    
    run_qa(str(csv_path), include_checks=include_checks, output_mode=output_mode)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
