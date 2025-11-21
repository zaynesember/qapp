"""
report.py — Excel report generation (v3.5, concise state_codes syntax + refined highlighting)

Original QA engine by sbaltz.
Refactored and extended by Zayne (2025).
"""

from __future__ import annotations
import pandas as pd
import numpy as np
import pathlib
from typing import Dict, Any
from qa_core import config


# ---------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------

def _flatten(value: Any, show_empty_marker: bool = False) -> str:
    """Convert listlike/dict/dataframe/scalar to concise string.

    By default this returns empty strings for missing/blank inputs so that
    report cells remain blank. Set `show_empty_marker=True` only when a
    literal "<EMPTY>" marker is desired (currently the Unique sheet).
    """
    empty_marker = "<EMPTY>" if show_empty_marker else ""

    if isinstance(value, (list, tuple, set, pd.Series, np.ndarray)):
        value = list(value)
        if not value:
            return empty_marker
        normed = [empty_marker if (pd.isna(v) or str(v).strip() == "") else str(v).strip() for v in value]
        uniq = list(set(normed))
        if len(uniq) == 1:
            val = uniq[0]
            return val if len(normed) == 1 else f"{val} × {len(normed)}"
        if len(normed) > 10:
            return ", ".join(normed[:10]) + ", ..."
        return ", ".join(normed)
    if isinstance(value, dict):
        if not value:
            return empty_marker
        return "; ".join(
            f"{k}={(empty_marker if pd.isna(v) or (isinstance(v, str) and not v.strip()) else v)}"
            for k, v in value.items()
        )
    if isinstance(value, pd.DataFrame):
        return empty_marker if value.empty else f"<DATAFRAME: {value.shape[0]} rows, {value.shape[1]} cols>"
    try:
        if pd.isna(value) or (isinstance(value, str) and not value.strip()):
            return empty_marker
    except Exception:
        pass
    return str(value)


def _compress_issue_values_row(row):
    """Collapse repeated '<EMPTY>' sequences cleanly."""
    s = str(row["issue_values"]).strip()
    n = int(row.get("issues", 0) or 0)
    if not s or "<EMPTY>" not in s:
        return s
    if "×" in s:
        return s
    tokens = [t for t in s.replace("\n", ",").replace(";", ",").split(",") if t.strip()]
    non_ellipsis = [t.strip() for t in tokens if t.strip() != "..."]
    if non_ellipsis and all(t == "<EMPTY>" for t in non_ellipsis):
        return "<EMPTY>" if n <= 1 else f"<EMPTY> × {n}"
    return s


def _compact_problematic_values(row):
    """Compress repeated identical values into '<VALUE> × n' syntax."""
    s = str(row.get("issue_values", "")).strip()
    if not s or "×" in s:
        return s
    n = int(row.get("issues", 0) or 0)
    if n <= 1:
        return s
    tokens = [t.strip() for t in s.replace("\n", ",").replace(";", ",").split(",") if t.strip()]
    tokens = [t.replace(". . .", "...") for t in tokens if t != "..."]
    if not tokens:
        return s
    uniq = set(tokens)
    if len(uniq) == 1:
        val = next(iter(uniq))
        return f"{val} × {n}"
    return s


def _compress_row_ranges(row_nums, limit=10):
    """Convert list of row numbers to '1, 3-5, 7, ...'."""
    if not row_nums:
        return ""
    row_nums = sorted({int(x) for x in row_nums if str(x).isdigit()})
    if not row_nums:
        return ""
    ranges, start, prev = [], row_nums[0], row_nums[0]
    for n in row_nums[1:]:
        if n == prev + 1:
            prev = n
        else:
            ranges.append(f"{start}-{prev}" if start != prev else str(start))
            start = prev = n
    ranges.append(f"{start}-{prev}" if start != prev else str(start))
    if len(ranges) > limit:
        ranges = ranges[:limit] + ["..."]
    return ", ".join(ranges)


# ---------------------------------------------------------------------
# Excel report writer
# ---------------------------------------------------------------------

def write_excel_report(results: Dict[str, Any], path: pathlib.Path) -> None:
    """Write human-readable Excel QA report (v3.5)."""
    excluded_sections = {"statewide_totals", "duplicates_summary", "missingness", "dataset_info"}
    detected_state = results.get("detected_state", {})

    # Rename fips_checks → state_codes if present
    if "fips_checks" in results and "state_codes" not in results:
        results["state_codes"] = results.pop("fips_checks")

    with pd.ExcelWriter(path, engine="xlsxwriter") as writer:
        rows = []
        for section, content in results.items():
            if section in excluded_sections or not isinstance(content, dict):
                continue
            for check, v in content.items():
                if not isinstance(v, dict):
                    continue
                # Avoid duplicating missingness: if this is a `*_missing` check
                # coming from `field_formats` and we also have a `missingness`
                # section for the same column, skip the `field_formats` missing
                # row to reduce redundancy in the summary.
                if section == "field_formats" and isinstance(check, str) and check.endswith("_missing"):
                    col = check[: -len("_missing")]
                    if "missingness" in results and col in results["missingness"]:
                        continue

                issue_values = "" if check in ("exact_duplicates", "all_but_votes_duplicate") else _flatten(v.get("issue_values", ""))
                rows.append({
                    "section": section,
                    "check": check,
                    "issues": int(v.get("issues", 0) or 0),
                    "issue_values": issue_values,
                    "issue_row_numbers": _flatten(v.get("issue_row_numbers", "")),
                })

        # Add duplicates summary rows if not yet included
        if "duplicates" in results:
            dup_df = results["duplicates"]
            if isinstance(dup_df, pd.DataFrame) and not dup_df.empty and "dup_type" in dup_df.columns:
                existing = {(r["section"], r["check"]) for r in rows}
                for dup_type, g in dup_df.groupby("dup_type"):
                    name = "exact_duplicates" if dup_type == "exact_duplicate" else dup_type
                    if ("duplicates", name) not in existing:
                        rows.append({
                            "section": "duplicates",
                            "check": name,
                            "issues": len(g),
                            "issue_values": "",
                            "issue_row_numbers": ",".join(map(str, g.index.to_series().add(1))),
                        })

        # Remove redundant field-level duplicate check
        rows = [r for r in rows if not (r["section"] == "fields" and r["check"] == "exact_duplicates")]

        df = pd.DataFrame(rows, columns=["section", "check", "issues", "issue_values", "issue_row_numbers"])
        df["issues"] = df["issues"].fillna(0).astype(int)
        df["issue_values"] = df["issue_values"].fillna("").replace("<EMPTY>", "")
        df["issue_row_numbers"] = df["issue_row_numbers"].fillna("<EMPTY>").replace("", "<EMPTY>")
        df["issue_values"] = df.apply(_compress_issue_values_row, axis=1)

        # Apply concise value × n syntax across all relevant sections
        df["issue_values"] = df.apply(_compact_problematic_values, axis=1)

        # Compact row numbers
        def _safe_parse_rows(val):
            if not val or val in ("<EMPTY>", ""):
                return []
            return [int(x) for x in str(val).replace("...", "").replace(" ", "").split(",") if x.isdigit()]
        df["issue_row_numbers"] = df["issue_row_numbers"].apply(lambda v: _compress_row_ranges(_safe_parse_rows(v)))

        # Blank out when no issues
        mask = df["issues"] == 0
        df.loc[mask, ["issue_values", "issue_row_numbers"]] = ""

        # Rename headers for readability
        df = df.rename(columns={
            "section": "QA Section",
            "check": "Check Name",
            "issues": "Issues Found",
            "issue_values": "Problematic Values",
            "issue_row_numbers": "Row Numbers"
        })

        failed_checks = (df["Issues Found"] > 0).sum()

        # --- Detected state banner at top ---
        state_banner = pd.DataFrame([
            ["Detected State", detected_state.get("state_po", "Unknown")],
            ["State Name", detected_state.get("state_name", "")],
            ["State FIPS", detected_state.get("state_fips", "")],
            ["State IC", detected_state.get("state_ic", "")],
            ["State CEN", detected_state.get("state_cen", "")]
        ], columns=["Info", "Value"])
        # Dataset-level info (rows/columns/unique counts) if provided
        dataset_info = results.get("dataset_info", {})

        # Gather failed checks names from all dict-based sections
        # Group failed checks by section so we show one line per section
        failed_by_section: dict[str, list[str]] = {}
        for section, content in results.items():
            if isinstance(content, dict):
                for check, v in content.items():
                    try:
                        issues = int(v.get("issues", 0) or 0)
                    except Exception:
                        issues = 0
                    if issues > 0:
                        failed_by_section.setdefault(section, []).append(check)

        # Count total failed checks
        failed_checks = sum(len(v) for v in failed_by_section.values())

        # Build a compact meta table to display in QA Summary
        meta_items = []
        if dataset_info:
            meta_items.extend([
                ["Rows", str(dataset_info.get("rows", ""))],
                ["Columns", str(dataset_info.get("columns", ""))],
                ["Unique Counties", str(dataset_info.get("unique_counties", ""))],
                ["Unique Jurisdictions", str(dataset_info.get("unique_jurisdictions", ""))],
            ])

        meta_items.append(["Failed Checks", str(failed_checks)])

        # Format failed checks grouped by section; insert a blank line between sections
        if failed_by_section:
            lines = []
            for sec, checks in failed_by_section.items():
                lines.append(f"{sec}: {', '.join(checks)}")
            grouped = "\n\n".join(lines)
        else:
            grouped = ""

        meta_items.append(["Failed Check Names", grouped])

        meta_df = pd.DataFrame(meta_items, columns=["Info", "Value"])

        # Write top metadata
        state_banner.to_excel(writer, index=False, sheet_name="QA Summary", startrow=0)
        banner_end = len(state_banner) + 2
        meta_df.to_excel(writer, index=False, sheet_name="QA Summary", startrow=banner_end)

        wb = writer.book
        ws = writer.sheets["QA Summary"]

        header_fmt = wb.add_format({"bold": True, "bg_color": "#D9E1F2", "text_wrap": True})
        wrap_fmt = wb.add_format({"text_wrap": True})
        ws.set_column("A:A", 28)
        ws.set_column("B:B", 60, wrap_fmt)

        # Highlight failed checks cell if > 0
        try:
            failed_checks_val = int(failed_checks)
        except Exception:
            failed_checks_val = 0
        if failed_checks_val > 0:
            fail_fmt = wb.add_format({"font_color": "#9C0006", "bg_color": "#FFC7CE", "bold": True})
            # locate the row index for the "Failed Checks" entry in meta_items
            idx_failed = next((i for i, item in enumerate(meta_items) if item[0] == "Failed Checks"), None)
            if idx_failed is not None:
                excel_failed_row = banner_end + 1 + idx_failed
                ws.write(excel_failed_row, 1, str(failed_checks_val), fail_fmt)

        # Highlight columns mismatch against expected count from config if available
        from qa_core import config as _config
        try:
            expected_cols = len(_config.REQUIRED_COLUMNS)
            actual_cols = int(dataset_info.get("columns", 0)) if dataset_info else 0
            if actual_cols != expected_cols:
                col_fmt = wb.add_format({"font_color": "#9C0006", "bg_color": "#FFC7CE", "bold": True})
                idx_cols = next((i for i, item in enumerate(meta_items) if item[0] == "Columns"), None)
                if idx_cols is not None:
                    excel_columns_row = banner_end + 1 + idx_cols
                    ws.write(excel_columns_row, 1, str(actual_cols), col_fmt)
        except Exception:
            pass

        ws.freeze_panes(banner_end + 1, 0)

        # --- Extra sheets ---
        name_map = {
            "statewide_totals": "Vote Aggregation",
            "duplicates": "Duplicates",
            # Friendly sheet names
            "zero_vote_precincts": "Zero Votes",
            "unique_values": "Unique",
            "magnitude_offices_map": "Mag Offices",
            "offices_multiple_magnitudes": "Multi-Mag Offices",
            "stage_invalid_rows": "Stage Issues",
        }

        def _autosize_sheet(sheet_name: str, df_table: pd.DataFrame):
            """Set reasonable column widths and wrap text for a written sheet.

            Widths are based on the max length of values in each column,
            capped between 12 and 60 characters.
            """
            ws = writer.sheets.get(sheet_name)
            if ws is None:
                return
            # Basic formats
            wrap_fmt = wb.add_format({"text_wrap": True})
            min_w, max_w = 12, 60
            for i, col in enumerate(df_table.columns):
                # Compute max length from header and column values
                try:
                    vals = df_table[col].astype(str).fillna("").tolist()
                except Exception:
                    vals = [str(x) for x in df_table[col].tolist()]
                max_len = max([len(str(col))] + [len(v) for v in vals])
                # heuristic scaling
                width = min(max(max_len * 1.1, min_w), max_w)
                # set column (xlsxwriter uses 0-based indexes into letters)
                ws.set_column(i, i, width, wrap_fmt)

        # Build list of DataFrame sheets to write (including Missingness as its own sheet)
        df_sheets: list[tuple[str, pd.DataFrame]] = []

        # Convert missingness dict into a DataFrame sheet if present
        if "missingness" in results and isinstance(results["missingness"], dict):
            miss = results["missingness"]
            miss_rows = []
            for col_name, v in miss.items():
                if isinstance(v, dict):
                    miss_rows.append({
                        "Column": col_name,
                        "Missing Count": v.get("missing_count", ""),
                        "% Missing": v.get("percent_empty", ""),
                        "Alt Missing Values": v.get("alt_missing_values", ""),
                    })
                else:
                    miss_rows.append({"Column": col_name, "Missing Count": "", "% Missing": "", "Alt Missing Values": ""})
            miss_df = pd.DataFrame(miss_rows)
            df_sheets.append(("Missingness", miss_df))

        # Convert dict-based sections (that are not DataFrames) into sheets
        for section, content in results.items():
            if section in {"duplicates_summary", "missingness", "dataset_info"}:
                continue
            if isinstance(content, dict):
                # Build a DataFrame of checks for this section
                rows_sec = []
                for check, v in content.items():
                    if not isinstance(v, dict):
                        continue
                    issue_values = _flatten(v.get("issue_values", ""))
                    rows_sec.append({
                        "Check Name": check,
                        "Issues Found": int(v.get("issues", 0) or 0),
                        "Problematic Values": issue_values,
                        "Row Numbers": _flatten(v.get("issue_row_numbers", "")),
                    })
                if rows_sec:
                    sec_name = name_map.get(section, section.replace("_", " ").title())[:31]
                    df_sheets.append((sec_name, pd.DataFrame(rows_sec)))
                continue
            # If the section already contains a DataFrame, write it as-is
            if isinstance(content, pd.DataFrame) and not content.empty:
                name = name_map.get(section, section)[:31]
                df_sheets.append((name, content))

        # Write DataFrame sheets in alphabetical order
        df_sheets.sort(key=lambda x: x[0].lower())

        # --- Table of Contents on QA Summary ---
        try:
            toc_start = banner_end + len(meta_items) + 2
            ws.write(toc_start, 0, "Table of Contents", header_fmt)
            link_fmt = wb.add_format({"font_color": "#0563C1", "underline": True})
            # list each sheet with hyperlink and a short shape description
            row_idx = toc_start + 1
            for name, table in df_sheets:
                sheet_name = name[:31]
                # skip if somehow the name is the QA Summary itself
                if sheet_name == "QA Summary":
                    continue
                # internal hyperlink to sheet's A1 (no size/shape column)
                url = f"internal:'{sheet_name}'!A1"
                ws.write_url(row_idx, 0, url, link_fmt, sheet_name)
                row_idx += 1
        except Exception:
            pass
        for name, table in df_sheets:
            sheet_name = name[:31]
            table.to_excel(writer, index=False, sheet_name=sheet_name)
            _autosize_sheet(sheet_name, table)
            # Freeze header row for the Unique Values sheet for easier browsing
            try:
                if sheet_name == "Unique Values":
                    ws_uv = writer.sheets.get(sheet_name)
                    if ws_uv is not None:
                        ws_uv.freeze_panes(1, 0)
            except Exception:
                pass

    print(f"Excel report written to {path}")
